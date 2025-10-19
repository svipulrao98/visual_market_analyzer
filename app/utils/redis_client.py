"""Redis client management."""
import redis.asyncio as redis
from typing import Optional
from loguru import logger
from app.config import settings


class RedisClient:
    """Redis client wrapper."""
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
    
    async def connect(self):
        """Connect to Redis."""
        try:
            self._client = await redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self._client.ping()
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            logger.info("Redis disconnected")
    
    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        if not self._client:
            await self.connect()
        return await self._client.get(key)
    
    async def set(self, key: str, value: str, ex: Optional[int] = None):
        """Set key-value pair with optional expiration."""
        if not self._client:
            await self.connect()
        await self._client.set(key, value, ex=ex)
    
    async def delete(self, key: str):
        """Delete key."""
        if not self._client:
            await self.connect()
        await self._client.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self._client:
            await self.connect()
        return await self._client.exists(key) > 0
    
    async def hset(self, name: str, key: str, value: str):
        """Set hash field."""
        if not self._client:
            await self.connect()
        await self._client.hset(name, key, value)
    
    async def hget(self, name: str, key: str) -> Optional[str]:
        """Get hash field."""
        if not self._client:
            await self.connect()
        return await self._client.hget(name, key)
    
    async def hgetall(self, name: str) -> dict:
        """Get all hash fields."""
        if not self._client:
            await self.connect()
        return await self._client.hgetall(name)


# Global Redis client instance
redis_client = RedisClient()

