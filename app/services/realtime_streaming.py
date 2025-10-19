"""Real-time market data streaming service."""

import asyncio
from datetime import datetime
from typing import Dict, List
from loguru import logger

from app.brokers import get_broker
from app.services.data_ingestion import data_ingestion_service
from app.database.connection import get_db_pool


class RealtimeStreamingService:
    """Manages real-time WebSocket streaming from broker."""

    def __init__(self):
        self.is_running = False
        self.streaming_task = None
        self.broker = None

    async def get_instruments_to_stream(self) -> List[int]:
        """Get instruments that should be streamed (from backfill_status)."""
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT bs.instrument_token, bs.last_backfilled_date
                FROM backfill_status bs
                JOIN instruments i ON i.token = bs.instrument_token
                WHERE bs.candle_count > 0
                    AND i.segment IN ('INDICES', 'NSE', 'NFO-FUT')
                ORDER BY bs.last_backfilled_date DESC
                LIMIT 500  -- Kite WebSocket limit
                """
            )
            tokens = [row["instrument_token"] for row in rows]
            logger.info(f"Found {len(tokens)} instruments to stream")
            return tokens

    async def tick_handler(self, tick_data: Dict):
        """Handle incoming tick data."""
        try:
            # Store in database via ingestion service
            await data_ingestion_service.handle_tick(tick_data)
        except Exception as e:
            logger.error(f"Error handling tick: {e}")

    async def start_streaming(self):
        """Start the real-time streaming service."""
        if self.is_running:
            logger.warning("Streaming already running")
            return

        logger.info("🚀 Starting real-time streaming service...")

        # Get instruments to stream
        instruments = await self.get_instruments_to_stream()
        if not instruments:
            logger.warning("No instruments to stream. Run backfill first.")
            return

        # Connect to broker WebSocket
        try:
            self.broker = get_broker()
            await self.broker.connect_websocket(instruments, self.tick_handler)
            self.is_running = True
            logger.info(f"✅ Streaming {len(instruments)} instruments")
        except Exception as e:
            error_msg = str(e).lower()
            # Don't treat market closed as an error
            if "1006" in error_msg or "connection" in error_msg:
                logger.info(f"WebSocket connection closed (markets may be closed)")
            else:
                logger.error(f"Failed to start streaming: {e}")
            self.is_running = False
            raise

    async def stop_streaming(self):
        """Stop the streaming service."""
        if not self.is_running:
            return

        logger.info("Stopping real-time streaming...")
        try:
            if self.broker:
                await self.broker.disconnect_websocket()
            self.is_running = False
            logger.info("✓ Streaming stopped")
        except Exception as e:
            logger.error(f"Error stopping streaming: {e}")

    async def auto_streaming_loop(self):
        """
        Automatic streaming loop with reconnection.
        - Starts streaming on app startup
        - Auto-reconnects on failure
        - Updates instrument list every hour
        - Handles market closed gracefully
        """
        logger.info("🔄 Auto-streaming service started")

        retry_delay = 60  # Start with 1 minute
        max_retry_delay = 600  # Max 10 minutes

        while True:
            try:
                # Start streaming
                await self.start_streaming()

                # Reset retry delay on successful connection
                retry_delay = 60

                # Keep alive and periodically refresh instrument list
                refresh_interval = 3600  # 1 hour
                elapsed = 0

                while self.is_running:
                    await asyncio.sleep(60)  # Check every minute
                    elapsed += 60

                    # Refresh instrument list every hour
                    if elapsed >= refresh_interval:
                        logger.info("Refreshing streaming instrument list...")
                        instruments = await self.get_instruments_to_stream()
                        # Check if instrument count changed significantly (>10%)
                        current_count = len(
                            getattr(self.broker, "_subscribed_instruments", []) or []
                        )
                        if (
                            instruments
                            and abs(len(instruments) - current_count)
                            > current_count * 0.1
                        ):
                            logger.info(
                                f"Instrument count changed ({current_count} → {len(instruments)}), restarting stream..."
                            )
                            await self.stop_streaming()
                            break  # Will restart in outer loop
                        elapsed = 0

            except Exception as e:
                error_msg = str(e).lower()

                # Check if it's a connection closed error (markets closed)
                if (
                    "1006" in error_msg
                    or "connection" in error_msg
                    or "closed" in error_msg
                ):
                    logger.info(
                        f"WebSocket closed (likely markets closed). "
                        f"Will retry in {retry_delay} seconds..."
                    )
                else:
                    logger.error(f"Streaming error: {e}")

                await self.stop_streaming()

                # Wait before reconnecting with exponential backoff
                await asyncio.sleep(retry_delay)

                # Increase retry delay (exponential backoff)
                retry_delay = min(retry_delay * 2, max_retry_delay)

    async def start_auto_streaming(self):
        """Start the auto-streaming background service."""
        if self.streaming_task and not self.streaming_task.done():
            logger.warning("Auto-streaming already running")
            return

        self.streaming_task = asyncio.create_task(self.auto_streaming_loop())
        logger.info("✓ Auto-streaming service initialized")


# Global instance
realtime_service = RealtimeStreamingService()
