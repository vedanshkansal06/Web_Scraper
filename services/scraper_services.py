import json
import asyncio
from typing import Tuple
from common.exceptions import InternalServerException, ValidationException
from common.logger import logger
from config.constants import ScraperNames, RedisConstants, ScraperStatus
from schemas.hsn_models import ResponseData, ScrapingResultItem
from database.mongo_client import MongoDBConnection
from database.redis_client import RedisConnection
from scraper.scraper_factory import ScraperFactory
from utils.keys import get_cache_key, get_register_key

class ScraperService:
    def __init__(self) -> None:
        self.cache_expiry_secs = RedisConstants.CACHE_EXPIRY_SECS.value

    async def get_health(self, conn: RedisConnection) -> dict:
        try:
            redis_client = await conn.get_client()
            await redis_client.ping()
            return {"message": "HSN Scraper Service is Working."}
        except Exception as e:
            logger.warning(f"{self.__class__.__name__}: get health : Redis is offline : {str(e)}")
            return {"message": "HSN Scraper Service is Currently Unavailable."}
        
    def __validate_query(self, query: str) -> str:
        query = query.lower().strip()[:50]
        if not query:
            raise ValidationException("Query Cannot be Accepted")
        return query
    
    def __validate_chapter(self, chapter: str) -> str:
        chapter = chapter.strip().upper()
        if chapter == "ALL":
            return chapter
        
        if chapter.isdigit():
            if len(chapter) == 1:
                chapter = "0" + chapter
            if 1 <= int(chapter) <= 99 and len(chapter) == 2:
                return chapter
            
        raise ValidationException("Chapter Cannot be Accepted")
    
    async def get_results(self,
    query: str, 
    chapter: str, 
    page: int, 
    per_page: int, 
    conn: RedisConnection
    ) -> Tuple[ScraperStatus, ResponseData]: #type: ignore
        query = self.__validate_query(query)
        chapter = self.__validate_chapter(chapter)

        query_cache_key = get_cache_key(query, chapter)
        query_registry_key = get_register_key(query, chapter)

        redis_client = await conn.get_client()
        try:
            await redis_client.ping()
        except Exception as e:
            logger.warning(f"Redis is offline.")
            raise InternalServerException("Redis Offline")
        
        async def fetch_paginated_results():
            redis_lower_limit = per_page * (page - 1)
            redis_upper_limit = redis_lower_limit + per_page - 1

            await redis_client.expire(name = query_cache_key, time = self.cache_expiry_secs)

            cached = await redis_client.lrange(query_cache_key, redis_lower_limit, redis_upper_limit)
            deserialized_results = [ScrapingResultItem.model_validate_json(item) for item in cached]
            total_results = await redis_client.llen(query_cache_key)

            scraper_status = (ScraperStatus.RUNNING if await redis_client.exists(query_registry_key) else ScraperStatus.COMPLETED)

            return scraper_status, ResponseData(
                scraper_status = scraper_status,
                total_results = total_results,
                current_page = page,
                per_page = per_page,
                results = deserialized_results
            )
        
        if await redis_client.exists(query_cache_key):
            return await fetch_paginated_results()
        
        mongo_col = MongoDBConnection.get_collection("hsn_cache")
        if mongo_col is not None:
            mongo_docs = await mongo_col.find({"description": {"$regex": query, "$options": "i"}}).to_list(length = 100)
            if mongo_docs:
                logger.info(f"Found {query} in MongoDB, pushing yo Redis")
                for doc in mongo_docs:
                    doc.pop('_id', None)
                    result_item = ScrapingResultItem(**doc)
                    await redis_client.rpush(query_cache_key, result_item.model_dump_json(exclude_none = False))
                    await redis_client.expire(query_cache_key, self.cache_expiry_secs)
                    return await fetch_paginated_results()
                
        if await redis_client.setnx(query_registry_key, 1):
            logger.info(f"Starting new scraping task for {query}: {chapter}")
            await redis_client.expire(query_registry_key, 180)
            task = asyncio.create_task(self.__run_scraper(query, chapter, conn))
            task.add_done_callback(
                lambda t: logger.error(t.exception()) if t.exception() else None
            )

        max_wait = 60
        poll_interval = 1
        min_results_required = 30

        for _ in range(max_wait):
            total_results, scraper_running = await asyncio.gather(
                redis_client.llen(query_cache_key),
                redis_client.exists(query_registry_key)
            )

            if total_results >= min_results_required or (not scraper_running and total_results > 0):
                return await fetch_paginated_results()
            
            if not scraper_running and total_results == 0:
                break

            await asyncio.sleep(poll_interval)

        if await redis_client.llen(query_cache_key) > 0:
            return await fetch_paginated_results()
        
        scraper_status = (ScraperStatus.RUNNING if await redis_client.exists(query_registry_key) else ScraperStatus.COMPLETED)

        return scraper_status, ResponseData(
            scraper_status = scraper_status,
            total_results = 0,
             current_page = 1,
             per_page = per_page,
             results = []
        )

    async def __run_scraper(self, query: str, chapter: str, conn: RedisConnection) -> None:
        query_cache_key = get_cache_key(query, chapter)
        query_registry_key = get_register_key(query, chapter)
        redis_client = await conn.get_client()

        try: 
            scraper_names =[
                ScraperNames.PRIMARY_SCRAPER_NAME.value,
                ScraperNames.SECONDARY_SCRAPER_NAME.value,
                ScraperNames.TERTIARY_SCRAPER_NAME.value
            ]

            all_scrapers_failed = True

            for scraper_name in scraper_names:
                try:
                    scraper_instance = ScraperFactory.get_scraper(scraper_name)
                    await scraper_instance.data_fetch(query, chapter, conn)

                    all_scrapers_failed = False
                    current_num_items = await redis_client.llen(query_cache_key)

                    if current_num_items > 0:
                        mongo_col = MongoDBConnection.get_collection("hsn_cache")
                        if mongo_col is not None:
                            cached = await redis_client.lrange(query_cache_key, 0, -1)
                            docs = [json.loads(item) for item in cached]
                            if docs:
                                await mongo_col.insert_many(docs)
                        
                        break
                except Exception as e:
                    logger.warning(f"Scraper {scraper_name} failed: {str(e)}")
                    continue

            if all_scrapers_failed:
                raise InternalServerException("All Scrapers Failed to Run")
            
        finally:
            await redis_client.delete(query_registry_key)