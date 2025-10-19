"""Database initialization script."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.connection import init_db, close_db, get_db_pool
from loguru import logger


async def initialize_database():
    """Initialize database and verify schema."""
    try:
        logger.info("Initializing database connection...")
        await init_db()
        
        pool = await get_db_pool()
        
        # Verify tables exist
        async with pool.acquire() as conn:
            # Check instruments table
            result = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'instruments'
                )
            """)
            
            if result:
                logger.info("✓ Instruments table exists")
            else:
                logger.error("✗ Instruments table not found")
            
            # Check tick_data hypertable
            result = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'tick_data'
                )
            """)
            
            if result:
                logger.info("✓ Tick data table exists")
                
                # Verify it's a hypertable
                is_hypertable = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM timescaledb_information.hypertables 
                        WHERE hypertable_name = 'tick_data'
                    )
                """)
                
                if is_hypertable:
                    logger.info("✓ Tick data is a hypertable")
                else:
                    logger.warning("✗ Tick data is not a hypertable")
            else:
                logger.error("✗ Tick data table not found")
            
            # Check continuous aggregates
            result = await conn.fetch("""
                SELECT view_name 
                FROM timescaledb_information.continuous_aggregates
            """)
            
            if result:
                logger.info(f"✓ Found {len(result)} continuous aggregates:")
                for row in result:
                    logger.info(f"  - {row['view_name']}")
            else:
                logger.warning("✗ No continuous aggregates found")
            
            # Check compression policy
            result = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM timescaledb_information.compression_settings
                    WHERE hypertable_name = 'tick_data'
                )
            """)
            
            if result:
                logger.info("✓ Compression policy configured")
            else:
                logger.warning("✗ Compression policy not found")
            
            # Check retention policy
            result = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM timescaledb_information.jobs
                    WHERE proc_name = 'policy_retention'
                )
            """)
            
            if result:
                logger.info("✓ Retention policy configured")
            else:
                logger.warning("✗ Retention policy not found")
        
        logger.info("Database initialization complete!")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(initialize_database())

