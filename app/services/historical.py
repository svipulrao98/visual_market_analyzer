"""Historical data service."""

from datetime import datetime
from typing import List, Dict
from loguru import logger

from app.database.connection import get_db_pool
from app.database.models import TickDataQueries, CandleQueries
from app.brokers import get_broker


class HistoricalDataService:
    """Service for managing historical data."""

    @staticmethod
    async def backfill_historical_data(
        instrument_token: int,
        from_date: datetime,
        to_date: datetime,
        interval: str = "1m",
    ) -> int:
        """
        Backfill historical candle data from broker.

        Args:
            instrument_token: Instrument token
            from_date: Start date
            to_date: End date
            interval: Candle interval

        Returns:
            Number of candles inserted
        """
        try:
            broker = get_broker()
            candles = await broker.fetch_historical(
                instrument_token, from_date, to_date, interval
            )

            if not candles:
                logger.warning(f"No historical data found for {instrument_token}")
                return 0

            # Convert candles to tick format and insert
            pool = await get_db_pool()
            ticks = []

            for candle in candles:
                # Create a tick for the candle close
                tick = (
                    candle["time"],
                    instrument_token,
                    candle["close"],
                    candle["volume"],
                    candle.get("open_interest", 0),
                    None,  # bid_price
                    None,  # ask_price
                    None,  # bid_qty
                    None,  # ask_qty
                )
                ticks.append(tick)

            await TickDataQueries.bulk_insert_ticks(pool, ticks)
            logger.info(
                f"Backfilled {len(ticks)} candles for instrument {instrument_token}"
            )

            # Refresh continuous aggregates for the backfilled time range
            logger.info("Refreshing continuous aggregates...")
            await CandleQueries.refresh_continuous_aggregates(pool, from_date, to_date)
            logger.info("Continuous aggregates refreshed")

            return len(ticks)

        except Exception as e:
            logger.error(f"Failed to backfill historical data: {e}")
            raise

    @staticmethod
    async def get_candles(
        instrument_token: int, interval: str, from_date: datetime, to_date: datetime
    ) -> List[Dict]:
        """
        Get candle data from database.

        Args:
            instrument_token: Instrument token
            interval: Candle interval (1m, 5m, 15m)
            from_date: Start date
            to_date: End date

        Returns:
            List of candle dictionaries
        """
        try:
            pool = await get_db_pool()
            candles = await CandleQueries.get_candles(
                pool, instrument_token, interval, from_date, to_date
            )
            return candles

        except Exception as e:
            logger.error(f"Failed to get candles: {e}")
            return []

    @staticmethod
    async def get_tick_data(
        instrument_token: int, from_date: datetime, to_date: datetime
    ) -> List[Dict]:
        """
        Get raw tick data from database.

        Args:
            instrument_token: Instrument token
            from_date: Start date
            to_date: End date

        Returns:
            List of tick dictionaries
        """
        try:
            pool = await get_db_pool()
            ticks = await TickDataQueries.get_ticks_range(
                pool, instrument_token, from_date, to_date
            )
            return ticks

        except Exception as e:
            logger.error(f"Failed to get tick data: {e}")
            return []
