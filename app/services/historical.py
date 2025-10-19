"""Historical data service.

NOTE: Candle fetching has been moved to app/services/candle_service.py
This service now only handles raw tick data queries.
"""

from datetime import datetime
from typing import List, Dict
from loguru import logger

from app.database.connection import get_db_pool
from app.database.models import TickDataQueries


class HistoricalDataService:
    """Service for managing historical tick data."""

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
