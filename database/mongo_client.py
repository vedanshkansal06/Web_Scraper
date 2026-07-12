from typing import Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from config.settings import settings
from common.logger import logger

class MongoDBConnection:
    _mongo_client: Optional["AsyncIOMotorClient[Any]"] = None
    _db: Optional["AsyncIOMotorDatabase[Any]"] = None

    @classmethod
    def get_db(cls) -> Optional["AsyncIOMotorDatabase[Any]"]:
        if cls._mongo_client is None:
            try:
                logger.info("Initializing MongoDB client...")
                cls._mongo_client = AsyncIOMotorClient(settings.mongo_uri)
                cls._db = cls._mongo_client[settings.mongo_db_name]

            except Exception as e:
                logger.error(f"Error initializing MongoDB client: {e}")
                raise e
            
        return cls._db
    
    @classmethod
    def get_collection(cls, collection_name: str = "hsn_cache") -> Optional["AsyncIOMotorCollection[Any]"]:
        db = cls.get_db()
        if db is None:
            return None
        return db[collection_name]
    
    @classmethod
    async def close_client(cls):
        if cls._mongo_client is not None:
            logger.info("Closing MongoDB client...")
            cls._mongo_client.close()
            cls._mongo_client = None
        