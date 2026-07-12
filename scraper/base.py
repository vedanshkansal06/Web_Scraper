from abc import ABC, abstractmethod
from database.redis_client import RedisConnection

class DataRetriever(ABC):
    
    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    async def data_fetch(self, query: str, chapter: str, conn: RedisConnection) -> None:
        pass