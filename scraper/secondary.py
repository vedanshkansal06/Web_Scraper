import asyncio
import json
from typing import Optional
from rapidfuzz import fuzz, process
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from common.logger import logger
from common.exceptions import InternalServerException
from config.settings import settings
from config.constants import RedisConstants, ScraperNames, ScraperBaseURLs, ScrapingURLs
from schemas.hsn_models import ScrapingResultItem, ScrapingResultItemMetadata
from database.redis_client import RedisConnection
from scraper.base import DataRetriever
from utils.keys import get_cache_key

class SecondaryScraper(DataRetriever):
    def __init__(self):
        self.main_page_url: str = ScrapingURLs.SECONDARY_SCRAPER_URL.value
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.cache_expiry_secs: int = RedisConstants.CACHE_EXPIRY_SECS.value
        self.redis_max_items: int = RedisConstants.MAX_TIMES.value
        self.num_data_pages: int = 20
        self.fuzzy_threshold = 70

    def get_name(self):
        return ScraperNames.SECONDARY_SCRAPER_NAME.value


    async def __scrape_main_page(self, query: str, chapter: str) -> set[str]:
        page: Optional[Page] = None

        try:
            if self.context is None:
                raise RuntimeError("Browser context not initialized")
            page = await self.context.new_page()
        except Exception as e:
            logger.warning(f"{self.__class__.__name__} __scrape_main_page: {str(e)}")
            raise InternalServerException("Fallback Failed")
        
        try: 
            await page.goto(self.main_page_url, timeout = 10000, wait_until="domcontentloaded")
        except Exception as e:
            logger.warning(f"Error navigating to {self.main_page_url}: {str(e)}")
            raise InternalServerException("Fallback Failed")

        if chapter and chapter != "ALL":
            tables = await page.locator("table.w-full").all()

            chapter_found = False

            for table in tables:
                trs = await table.locator("tbody >> tr").all()
                for tr in trs:
                    link_tag = tr.locator("a >> nth=0")
                    link_text = await link_tag.text_content()
                    if link_text:
                        if link_text.split(" ")[-1] == chapter:
                            chapter_found = True
                            break
            
                if chapter_found: 
                    break
            
            if not chapter_found:
                return set()
            
        else:
            input = page.get_by_placeholder("Search by HSN Code or Description...")
            await input.type(query, delay= 500)
            await asyncio.sleep(1)
            await input.press("Enter")

        await page.wait_for_selector("div.card-hsn", timeout = 10000)
        hsn_cards = await page.locator("div.card-hsn").all()

        links = []
        for hsn_card in hsn_cards:
            try:
                link_tag = hsn_card.locator("a >> nth=0")
                link = await link_tag.get_attribute("href", timeout = 10000)
                if link is not None:
                    links.append(ScraperBaseURLs.SECONDARY_SCRAPER_BASE_URL.value + link)
            except Exception as e:
                logger.warning(f"Link Not Found in Card: {str(e)}")
                continue
                
        unique_links: set[str] = set()
        for link in links:
            if len(unique_links) < self.num_data_pages:
                unique_links.add(link)
            else:
                break

        return unique_links

    async def __scrape_data_page(self, link: str, query: str) -> list[ScrapingResultItem]:
        page: Optional[Page] = None
        try:
            if self.context is None:
                raise RuntimeError("Browser context not initialized")
            page = await self.context.new_page()
            await page.goto(link, timeout= 10000)
            await page.wait_for_selector("table.HSNCodeTable_table_ug684", timeout=10000)
        except Exception as e:
            logger.debug(f"{self.__class__.__name__}: __scrape_data_page: {e}")
            if page:
                await page.close()
            return []

        tables = await page.locator("table.table-auto").all()
        results = []

        for table in tables:
            trs = await table.locator("tr").all()

            for tr in trs[1:]:
                try:
                    # HSN Code
                    hsn_code = await tr.locator("td >> nth =0 >> a >> nth=0").text_content()
                    if hsn_code:
                        hsn_code = hsn_code.strip()
                    else: continue

                    # Description
                    description = await tr.locator("td >> nth=1").text_content()
                    if description:
                        description = description.strip()
                    else: continue

                    _, score, _ = process.extractOne(query.lower(), [description.lower()], scorer = fuzz.partial_ratio)
                    if score < self.fuzzy_threshold:
                        continue

                    # GST
                    gst = await tr.locator("td >> nth=2").text_content()
                    if gst:
                        gst = gst.strip()
                    
                    results.append(ScrapingResultItem(
                        hsn_code= hsn_code,
                        description = description,
                        gst_rate = gst,
                        metadata = ScrapingResultItemMetadata(
                            ministry=None,
                            cgst=None,
                            sgst=None,
                            igst=None,
                            cess=None
                        )
                    ))
                except Exception as e:
                    logger.debug(f"{self.__class__.__name__}: __scrape_data_page :skipping row")
                    continue

        await page.close()
        return results
    
    async def __redis_store(self, conn: RedisConnection, query: str, chapter: str, results: list[ScrapingResultItem]):
        
        query_cache_key = get_cache_key(query, chapter)

        redis_client = await conn.get_client()

        for result in results:
            try:
                cuurent_num_items = await redis_client.llen(query_cache_key)
                if cuurent_num_items < self.redis_max_items:
                    await redis_client.rpush(query_cache_key, json.dumps(result.model_dump(exclude_none = False)))
                    await redis_client.expire(name = query_cache_key, time = self.cache_expiry_secs)

            except Exception as e:
                logger.warning(f"Redis Write failed: {str(e)}")
                raise InternalServerException("Fallback Failed")
            
    async def data_fetch(self, query: str, chapter: str, conn: RedisConnection) -> None:
        async with async_playwright() as p:
            try: 
                self.browser = await p.chromium.launch(headless = settings.scraper_headless)
                self.context = await self.browser.new_context()

                links = await self.__scrape_main_page(query, chapter)

                for link in links:
                    results = await self.__scrape_data_page(link, query)
                    await self.__redis_store(conn = conn, query = query, chapter = chapter, results = results)
                    await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"{self.get_name} fetch operation failed {e}")
                return
            
            finally:
                if self.browser:
                    await self.browser.close()