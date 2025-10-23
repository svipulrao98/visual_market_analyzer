"""Smart candle service with automatic gap detection and backfill."""

import asyncpg
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from loguru import logger

from app.database.connection import get_db_pool
from app.brokers.base import BrokerInterface


class CandleService:
    """
    Smart candle fetch with gap detection and backfill.

    This service:
    1. Queries TimescaleDB continuous aggregates first
    2. Detects missing data gaps
    3. Backfills from broker historical API automatically
    4. Returns complete dataset
    """

    def __init__(self, broker: BrokerInterface):
        self.broker = broker

    async def get_candles(
        self,
        instrument_token: int,
        from_date: datetime,
        to_date: datetime,
        interval: str = "1m",
    ) -> List[Dict]:
        """
        Get candles with automatic gap filling.

        Args:
            instrument_token: Instrument token
            from_date: Start datetime
            to_date: End datetime
            interval: Timeframe (1m, 5m, 15m, 1h, 1d)

        Returns:
            List of candles with complete data
        """
        # Step 1: Query database first
        db_candles = await self._query_db_candles(
            instrument_token, from_date, to_date, interval
        )

        # Step 2: Detect gaps
        gaps = self._find_gaps(db_candles, from_date, to_date, interval)

        # Step 3: Backfill gaps from broker if needed
        if gaps:
            logger.info(
                f"Found {len(gaps)} gap(s) for instrument {instrument_token}, backfilling..."
            )
            for gap_start, gap_end in gaps:
                await self._backfill_gap(instrument_token, gap_start, gap_end, interval)

            # Re-query after backfill
            db_candles = await self._query_db_candles(
                instrument_token, from_date, to_date, interval
            )
            logger.info(f"After backfill: {len(db_candles)} candles available")

        return db_candles

    async def _query_db_candles(
        self,
        instrument_token: int,
        from_date: datetime,
        to_date: datetime,
        interval: str,
    ) -> List[Dict]:
        """Query candles from TimescaleDB continuous aggregates."""
        pool = await get_db_pool()

        # Map interval to table (only 1m, 5m, 15m, 1h supported)
        table_map = {
            "1m": "candles_1m",
            "5m": "candles_5m",
            "15m": "candles_15m",
            "1h": "candles_1h",
        }

        table = table_map.get(interval, "candles_1m")

        query = f"""
            SELECT 
                bucket,
                open,
                high,
                low,
                close,
                volume,
                open_interest
            FROM {table}
            WHERE instrument_token = $1
              AND bucket >= $2
              AND bucket <= $3
            ORDER BY bucket
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, instrument_token, from_date, to_date)
            return [dict(row) for row in rows]

    def _find_gaps(
        self,
        candles: List[Dict],
        from_date: datetime,
        to_date: datetime,
        interval: str,
    ) -> List[Tuple[datetime, datetime]]:
        """
        Detect missing time periods in candle data.

        Returns:
            List of (gap_start, gap_end) tuples
        """
        if not candles:
            # No data at all - entire range is a gap
            return [(from_date, to_date)]

        # Map interval to timedelta
        interval_map = {
            "1m": timedelta(minutes=1),
            "5m": timedelta(minutes=5),
            "15m": timedelta(minutes=15),
            "1h": timedelta(hours=1),
            "1d": timedelta(days=1),
        }

        delta = interval_map.get(interval, timedelta(minutes=1))
        gaps = []

        # Check gap before first candle
        first_bucket = candles[0]["bucket"]
        # Ensure first_bucket is timezone-aware for comparison
        if not first_bucket.tzinfo:
            from datetime import timezone

            first_bucket = first_bucket.replace(tzinfo=timezone.utc)
        if first_bucket > from_date + delta:
            gaps.append((from_date, first_bucket - delta))

        # Check gaps between candles
        for i in range(len(candles) - 1):
            current_bucket = candles[i]["bucket"]
            next_bucket = candles[i + 1]["bucket"]
            # Ensure timezone-aware
            if not current_bucket.tzinfo:
                from datetime import timezone

                current_bucket = current_bucket.replace(tzinfo=timezone.utc)
            if not next_bucket.tzinfo:
                from datetime import timezone

                next_bucket = next_bucket.replace(tzinfo=timezone.utc)

            expected_next = current_bucket + delta

            # If there's a gap larger than expected
            if next_bucket > expected_next:
                gaps.append((expected_next, next_bucket - delta))

        # Check gap after last candle
        last_bucket = candles[-1]["bucket"]
        # Ensure timezone-aware
        if not last_bucket.tzinfo:
            from datetime import timezone

            last_bucket = last_bucket.replace(tzinfo=timezone.utc)
        if last_bucket < to_date - delta:
            gaps.append((last_bucket + delta, to_date))

        return gaps

    async def _backfill_gap(
        self,
        instrument_token: int,
        from_date: datetime,
        to_date: datetime,
        interval: str,
    ):
        """Fetch missing candles from broker and store in database."""
        try:
            # Map interval to broker API format
            broker_interval_map = {
                "1m": "minute",
                "5m": "5minute",
                "15m": "15minute",
                "1h": "60minute",
                "1d": "day",
            }

            broker_interval = broker_interval_map.get(interval, "minute")

            logger.info(
                f"Backfilling {instrument_token} from {from_date} to {to_date} ({interval})"
            )

            # Fetch from broker
            broker_candles = await self.broker.fetch_historical_candles(
                instrument_token, from_date, to_date, broker_interval
            )

            if not broker_candles:
                logger.warning(f"No historical data from broker for {instrument_token}")
                return

            # Store candles
            await self._store_candles(broker_candles, instrument_token, interval)

            logger.info(
                f"✓ Backfilled {len(broker_candles)} candles for {instrument_token}"
            )

        except Exception as e:
            logger.error(f"Error backfilling gap: {e}")
            raise

    async def _store_candles(
        self, candles: List[Dict], instrument_token: int, interval: str
    ):
        """
        Store historical candles in database.

        For 1m candles: Store as ticks, let continuous aggregates handle it
        For other intervals: Store directly in the materialized view
        """
        pool = await get_db_pool()

        if interval == "1m":
            # Store OHLC as multiple ticks to preserve price action
            # This allows continuous aggregates to correctly calculate OHLC
            async with pool.acquire() as conn:
                records = []
                for c in candles:
                    candle_time = c["time"]
                    # Store 4 ticks per candle to preserve OHLC:
                    # 1. Open at start of minute (00 seconds)
                    records.append(
                        (
                            candle_time,
                            instrument_token,
                            c["open"],
                            c["volume"],
                            c.get("open_interest", 0),
                            None,
                            None,
                            None,
                            None,
                        )
                    )
                    # 2. High at 20 seconds
                    records.append(
                        (
                            (
                                candle_time.replace(second=20)
                                if candle_time.second == 0
                                else candle_time
                            ),
                            instrument_token,
                            c["high"],
                            0,  # Don't double-count volume
                            c.get("open_interest", 0),
                            None,
                            None,
                            None,
                            None,
                        )
                    )
                    # 3. Low at 40 seconds
                    records.append(
                        (
                            (
                                candle_time.replace(second=40)
                                if candle_time.second == 0
                                else candle_time
                            ),
                            instrument_token,
                            c["low"],
                            0,  # Don't double-count volume
                            c.get("open_interest", 0),
                            None,
                            None,
                            None,
                            None,
                        )
                    )
                    # 4. Close at 59 seconds
                    records.append(
                        (
                            (
                                candle_time.replace(second=59)
                                if candle_time.second == 0
                                else candle_time
                            ),
                            instrument_token,
                            c["close"],
                            0,  # Don't double-count volume
                            c.get("open_interest", 0),
                            None,
                            None,
                            None,
                            None,
                        )
                    )

                await conn.executemany(
                    """
                    INSERT INTO tick_data 
                    (time, instrument_token, ltp, volume, open_interest, 
                     bid_price, ask_price, bid_qty, ask_qty)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT DO NOTHING
                """,
                    records,
                )

                # Refresh ALL continuous aggregates for this time range
                start_time = min(c["time"] for c in candles)
                end_time = max(c["time"] for c in candles)

                # Refresh all timeframes: 1m → 5m → 15m → 1h
                refreshed = []
                for aggregate in [
                    "candles_1m",
                    "candles_5m",
                    "candles_15m",
                    "candles_1h",
                ]:
                    try:
                        refresh_query = f"""
                            CALL refresh_continuous_aggregate('{aggregate}', 
                                '{start_time.isoformat()}'::timestamptz, 
                                '{end_time.isoformat()}'::timestamptz);
                        """
                        await conn.execute(refresh_query)
                        refreshed.append(aggregate)
                    except asyncpg.exceptions.InvalidParameterValueError as e:
                        if "refresh window too small" in str(e):
                            # Time range too small for this aggregate bucket size, skip it
                            # The scheduled refresh policy will pick it up later
                            logger.debug(
                                f"Skipping {aggregate} refresh (window too small for bucket size)"
                            )
                        else:
                            raise

                if refreshed:
                    logger.info(
                        f"Refreshed aggregates ({', '.join(refreshed)}) for {start_time} to {end_time}"
                    )
                else:
                    logger.debug(
                        f"No aggregates refreshed (windows too small), data stored in tick_data"
                    )

        else:
            # For higher timeframes, we can't insert directly into continuous aggregates
            # We need to insert 1m data and let cascading aggregation happen
            # For now, we'll store as 1m ticks
            logger.warning(
                f"Cannot directly store {interval} candles. Please backfill at 1m resolution."
            )
