"""Data ingestion service with buffering."""
import asyncio
from datetime import datetime
from typing import List, Dict
from loguru import logger

from app.database.connection import get_db_pool
from app.database.models import TickDataQueries
from app.config import settings


class DataIngestionService:
    """Service for ingesting and buffering tick data."""
    
    def __init__(self):
        self.buffer: List[tuple] = []
        self.buffer_size = settings.tick_buffer_size
        self.flush_interval = settings.flush_interval_seconds
        self._lock = asyncio.Lock()
        
        logger.info(f"Data ingestion service initialized (buffer_size={self.buffer_size})")
    
    async def handle_tick(self, tick_data: Dict):
        """
        Buffer incoming tick data.
        
        Args:
            tick_data: Dictionary containing tick information
        """
        async with self._lock:
            # Convert to tuple for bulk insert
            tick_tuple = (
                tick_data.get('time', datetime.now()),
                tick_data.get('instrument_token'),
                tick_data.get('ltp'),
                tick_data.get('volume'),
                tick_data.get('open_interest'),
                tick_data.get('bid_price'),
                tick_data.get('ask_price'),
                tick_data.get('bid_qty'),
                tick_data.get('ask_qty')
            )
            
            self.buffer.append(tick_tuple)
            
            # Auto-flush if buffer is full
            if len(self.buffer) >= self.buffer_size:
                await self._flush_buffer_internal()
    
    async def flush_buffer(self):
        """Manually flush buffer (public method)."""
        async with self._lock:
            await self._flush_buffer_internal()
    
    async def _flush_buffer_internal(self):
        """Internal flush method (assumes lock is held)."""
        if not self.buffer:
            return
        
        try:
            pool = await get_db_pool()
            await TickDataQueries.bulk_insert_ticks(pool, self.buffer)
            
            count = len(self.buffer)
            self.buffer.clear()
            logger.debug(f"Flushed {count} ticks to database")
            
        except Exception as e:
            logger.error(f"Failed to flush buffer: {e}")
            # Keep buffer for retry
    
    async def start_flush_loop(self):
        """Periodically flush buffer."""
        logger.info("Starting periodic flush loop")
        
        try:
            while True:
                await asyncio.sleep(self.flush_interval)
                await self.flush_buffer()
        except asyncio.CancelledError:
            logger.info("Flush loop cancelled")
            await self.flush_buffer()  # Final flush
        except Exception as e:
            logger.error(f"Error in flush loop: {e}")


# Global service instance
data_ingestion_service = DataIngestionService()

