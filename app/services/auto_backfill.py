"""Background service to auto-fill gaps for recently accessed instruments."""

import asyncio
import asyncpg
from datetime import datetime, timedelta, timezone
from typing import Set
from loguru import logger

from app.brokers import get_broker
from app.services.candle_service import CandleService
from app.database.connection import get_db_pool

# Track recently accessed instruments
recent_instruments: Set[int] = set()
last_backfill: dict = {}


def track_instrument(instrument_token: int):
    """Track an instrument for auto-backfill."""
    recent_instruments.add(instrument_token)
    logger.debug(f"Tracking instrument {instrument_token} for auto-backfill")


async def get_all_tradable_instruments() -> list:
    """Get ALL tradable instruments from database."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT token, segment
            FROM instruments 
            WHERE segment IN ('INDICES', 'NSE', 'NFO-FUT')
                AND symbol NOT LIKE '%-SG'  -- Exclude government securities
                AND symbol NOT LIKE '%-SM'  -- Exclude special category
            ORDER BY 
                CASE segment 
                    WHEN 'INDICES' THEN 1
                    WHEN 'NFO-FUT' THEN 2
                    WHEN 'NSE' THEN 3
                    ELSE 4
                END,
                token
        """
        )
        return [row["token"] for row in rows]


async def should_backfill(instrument_token: int) -> bool:
    """Check if instrument needs backfilling."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT last_backfilled_date, last_backfilled_to
            FROM backfill_status
            WHERE instrument_token = $1
            """,
            instrument_token,
        )

        if not row:
            return True  # Never backfilled

        last_backfilled = row["last_backfilled_date"]
        last_to = row["last_backfilled_to"]
        now = datetime.now(timezone.utc)

        # Backfill if last backfill was > 6 hours ago
        if (now - last_backfilled) > timedelta(hours=6):
            return True

        # Also backfill if last_to is not recent (> 1 hour old)
        if (now - last_to) > timedelta(hours=1):
            return True

        return False


async def update_backfill_status(
    instrument_token: int, from_date: datetime, to_date: datetime, candle_count: int
):
    """Update backfill tracking."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO backfill_status 
                (instrument_token, last_backfilled_date, last_backfilled_from, last_backfilled_to, candle_count, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (instrument_token) 
            DO UPDATE SET
                last_backfilled_date = $2,
                last_backfilled_from = $3,
                last_backfilled_to = $4,
                candle_count = $5,
                updated_at = $6
            """,
            instrument_token,
            datetime.now(timezone.utc),
            from_date,
            to_date,
            candle_count,
            datetime.now(timezone.utc),
        )


async def auto_backfill_service():
    """
    Background service that auto-fills gaps for tracked instruments.
    Runs every 5 minutes.
    """
    logger.info("🔄 Auto-backfill service started")

    # Wait for database to be ready
    await asyncio.sleep(5)

    # Create broker instance ONCE (reuses cached token)
    try:
        broker = get_broker()
        service = CandleService(broker)
        logger.info("✓ Broker instance initialized")
    except Exception as e:
        logger.error(f"Failed to initialize broker: {e}")
        return

    while True:
        try:
            # Ensure DB pool is available
            pool = await get_db_pool()
            if not pool or pool._closing:
                logger.warning("Database pool not ready, waiting...")
                await asyncio.sleep(60)
                continue

            # Get ALL tradable instruments from DB
            instruments_to_check = await get_all_tradable_instruments()
            if not instruments_to_check:
                logger.warning("No tradable instruments found in database")
                await asyncio.sleep(60)
                continue

            logger.info(f"Found {len(instruments_to_check)} total tradable instruments")

            now = datetime.now(timezone.utc)

            logger.info(f"🔍 Checking {len(instruments_to_check)} instruments for gaps")

            for token in instruments_to_check:
                try:
                    # Check if pool is still valid
                    pool = await get_db_pool()
                    if not pool or pool._closing:
                        logger.warning("Database pool closing, stopping backfill cycle")
                        break

                    # Check if backfill is needed (using DB tracking)
                    needs_backfill = await should_backfill(token)
                    if not needs_backfill:
                        logger.debug(f"⏭️  Skipping {token} - recently backfilled")
                        continue

                    # Backfill last 7 days for 1m candles
                    from_date = now - timedelta(days=7)
                    to_date = now

                    logger.info(f"📥 Backfilling {token} for last 7 days")

                    # Get candles - fills gaps, stores as ticks
                    # Continuous aggregates auto-create: 1m → 5m → 15m → 1h → 1d
                    candles = await service.get_candles(token, from_date, to_date, "1m")

                    # Update DB tracking
                    await update_backfill_status(
                        token, from_date, to_date, len(candles)
                    )

                    logger.info(
                        f"✅ Backfill complete: {token} ({len(candles)} candles)"
                    )
                    logger.info(
                        f"   Timeframes available: 1m, 5m, 15m, 1h, 1d (via aggregates)"
                    )

                    # Rate limit: 2 seconds between instruments
                    await asyncio.sleep(2)

                except asyncpg.exceptions.InterfaceError as e:
                    if "pool is closing" in str(e):
                        logger.warning("Database pool closing, stopping backfill cycle")
                        break
                    logger.error(f"❌ Database error for {token}: {e}")
                except Exception as e:
                    logger.error(f"❌ Error backfilling {token}: {e}")
                    import traceback

                    logger.error(traceback.format_exc())

        except Exception as e:
            logger.error(f"Auto-backfill service error: {e}")
            import traceback

            logger.error(traceback.format_exc())

        # Wait before next cycle
        logger.info("💤 Waiting 5 minutes before next backfill cycle")
        await asyncio.sleep(10)  # 5 minutes


async def start_auto_backfill():
    """Start the auto-backfill background service."""
    asyncio.create_task(auto_backfill_service())
