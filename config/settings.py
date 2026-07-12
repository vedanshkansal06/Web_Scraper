from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    scraper_headless: bool = True

    # MongoDB
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "hsn_scraper_db"

    # Redis 
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()