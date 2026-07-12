import sys
import asyncio
import uvicorn

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from services.scraper_services import ScraperService
from database.mongo_client import MongoDBConnection
from database.redis_client import RedisConnection
from schemas.hsn_models import ScraperResponse, ScraperRequest
from config.constants import URLs
from common.logger import logger
from common.exceptions import APIException
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Databases...")

    try:
        MongoDBConnection.get_db()
        logger.info("MongoDb initialized successfully...")
    except Exception as e:
        logger.error(f"MongoDB failed to initialize: {str(e)}.")

    try:
        await redis_conn.get_client()
        logger.info("Redis is initialized...")
    except Exception as e:
        logger.error("Redis Failed to initialize: {str(e)}.")

    yield

    logger.info("API shutting down...")
    await MongoDBConnection.close_client()
    await redis_conn.close_client()
    logger.info("Database disconnected successfully.")

app = FastAPI(
    title = "HSN Scraper API",
    description = "A service for scraping and caching HSN codes.",
    version = "1.0.0",
    lifespan = lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*"],
    allow_credentials = True,
    allow_methods = ["*"],
    allow_headers = ["*"]
)

scraper_service = ScraperService()
redis_conn = RedisConnection()

@app.exception_handler(APIException)
async def api_exception_handler(request, exception: APIException):
    return JSONResponse(
        status_code = exception.status_code,
        content = exception.detail
    )

@app.get("/health")
async def health_check():
    return await scraper_service.get_health(redis_conn)

@app.post(f"{URLs.base_v1.value}/search", response_model = ScraperResponse)
async def search_hsn(request: ScraperRequest):
    try:
        scraper_status, response_data = await scraper_service.get_results(
            query = request.query,
            chapter = request.chapter or "ALL",
            page = request.page or 1,
            per_page = request.per_page or 10,
            conn = redis_conn
        )

        return ScraperResponse(
            success = True,
            message = "Data retrieved successfully.",
            data = response_data
        )
    except APIException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in search: {str(e)}")
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = "Am unexcepted internal server error occured."
        )        
if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    uvicorn.run("main:app", host = "0.0.0.0", port = 8000)