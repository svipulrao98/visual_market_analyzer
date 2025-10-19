"""Instrument management service."""
from typing import List, Dict, Optional
from loguru import logger

from app.database.connection import get_db_pool
from app.database.models import Instrument, InstrumentQueries
from app.brokers import get_broker


class InstrumentService:
    """Service for managing instruments."""
    
    @staticmethod
    async def sync_instruments_from_broker() -> int:
        """
        Sync instruments from broker API to database.
        
        Returns:
            Number of instruments synced
        """
        try:
            broker = get_broker()
            instruments = await broker.get_instruments()
            
            pool = await get_db_pool()
            count = 0
            
            for inst_data in instruments:
                try:
                    instrument = Instrument(**inst_data)
                    await InstrumentQueries.insert_instrument(pool, instrument)
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to insert instrument {inst_data.get('symbol')}: {e}")
            
            logger.info(f"Synced {count} instruments from broker")
            return count
            
        except Exception as e:
            logger.error(f"Failed to sync instruments: {e}")
            raise
    
    @staticmethod
    async def get_instrument_by_token(token: int) -> Optional[Dict]:
        """Get instrument by token."""
        try:
            pool = await get_db_pool()
            return await InstrumentQueries.get_instrument_by_token(pool, token)
        except Exception as e:
            logger.error(f"Failed to get instrument: {e}")
            return None
    
    @staticmethod
    async def get_all_instruments(limit: int = 1000, offset: int = 0) -> List[Dict]:
        """Get all instruments with pagination."""
        try:
            pool = await get_db_pool()
            return await InstrumentQueries.get_all_instruments(pool, limit, offset)
        except Exception as e:
            logger.error(f"Failed to get instruments: {e}")
            return []
    
    @staticmethod
    async def search_instruments(query: str, limit: int = 50) -> List[Dict]:
        """Search instruments by symbol or exchange."""
        try:
            pool = await get_db_pool()
            return await InstrumentQueries.search_instruments(pool, query, limit)
        except Exception as e:
            logger.error(f"Failed to search instruments: {e}")
            return []

