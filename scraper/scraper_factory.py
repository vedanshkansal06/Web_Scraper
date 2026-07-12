from common.exceptions import InternalServerException
from scraper.base import DataRetriever
from scraper.primary import PrimaryScraper
from scraper.secondary import SecondaryScraper
from scraper.tertiary import TertiaryScraper

class ScraperFactory:
    @staticmethod
    def get_scraper(scraper_name: str) -> DataRetriever:
        if scraper_name == "registerkaro":
            return PrimaryScraper()
        elif scraper_name == "piceapp":
            return SecondaryScraper()
        elif scraper_name == "credlix":
            return TertiaryScraper()
        else:
            raise InternalServerException("Unknown Scraper Type.")