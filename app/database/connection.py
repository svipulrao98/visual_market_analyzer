"""Database connection management."""
import asyncpg
from typing import Optional
from loguru import logger
from app.config import settings


class DatabasePool:
    """Database connection pool manager."""
    
    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Create database connection pool."""
        try:
            self._pool = await asyncpg.create_pool(
                settings.database_url,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            logger.info("Database pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise
    
    async def disconnect(self):
        """Close database connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("Database pool closed")
    
    def get_pool(self) -> asyncpg.Pool:
        """Get the connection pool."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized. Call connect() first.")
        return self._pool


# Global database pool instance
db_pool = DatabasePool()


async def init_db():
    """Initialize database connection."""
    await db_pool.connect()


async def close_db():
    """Close database connection."""
    await db_pool.disconnect()


async def get_db_pool() -> asyncpg.Pool:
    """Get database connection pool."""
    return db_pool.get_pool()

