from enum import Enum

class ScraperStatus(Enum):
    RUNNING = "running"
    COMPLETED = "completed"

class ScrapingURLs(Enum):
    PRIMARY_SCRAPER_URL = "https://www.registerkaro.in/tools-calculators/hsn-code-finder"
    SECONDARY_SCRAPER_URL = "https://piceapp.com/hsn-code/"
    TERTIARY_SCRAPER_URL = "https://www.credlix.com/hsn-code"

class ScraperBaseURLs(Enum):
    PRIMARY_SCRAPER_BASE_URL = "https://www.registerkaro.in"
    SECONDARY_SCRAPER_BASE_URL = "https://piceapp.com"
    TERTIARY_SCRAPER_BASE_URL = "https://www.credlix.com"

class ScraperNames(Enum):
    PRIMARY_SCRAPER_NAME = "registerkaro"
    SECONDARY_SCRAPER_NAME = "piceapp"
    TERTIARY_SCRAPER_NAME = "credlix"

class RedisConstants(Enum):
    CACHE_EXPIRY_SECS = 86400 # 24 hours in seconds
    MAX_TIMES = 500

class URLs(Enum):
    base_v1 = "/api/v1"