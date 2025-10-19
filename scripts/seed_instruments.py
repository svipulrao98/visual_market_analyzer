"""Seed instruments from broker."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.connection import init_db, close_db
from app.services.instruments import InstrumentService
from loguru import logger


async def seed_instruments():
    """Fetch and seed instruments from broker."""
    try:
        logger.info("Connecting to database...")
        await init_db()
        
        logger.info("Syncing instruments from broker...")
        count = await InstrumentService.sync_instruments_from_broker()
        
        logger.info(f"Successfully synced {count} instruments!")
        
    except Exception as e:
        logger.error(f"Failed to seed instruments: {e}")
        raise
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(seed_instruments())

