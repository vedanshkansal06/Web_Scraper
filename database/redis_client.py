from typing import Optional
from redis import asyncio as aioredis
from config.settings import settings
from common.logger import logger

class RedisConnection:
    _redis_client: Optional[aioredis.Redis] = None

    @classmethod
    async def get_client(cls) -> aioredis.Redis:
        if cls._redis_client is None:
            logger.info("Initializing Redis client...")
            cls._redis_client = aioredis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                socket_timeout=5.0,
                retry_on_timeout=True,
                decode_responses=True
            )
        return cls._redis_client
    
    @classmethod
    async def close_client(cls):
        if cls._redis_client is not None:
            logger.info("Closing Redis client...")
            await cls._redis_client.close()
            cls._redis_client = None
        