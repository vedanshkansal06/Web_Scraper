import asyncio
import json
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from common.logger import logger
from common.exceptions import InternalServerException
from config.settings import settings
from config.constants import RedisConstants, ScraperNames, ScraperBaseURLs, ScrapingURLs
from schemas.hsn_models import ScrapingResultItem, ScrapingResultItemMetadata
from database.redis_client import RedisConnection
from scraper.base import DataRetriever
from utils.keys import get_cache_key

class PrimaryScraper(DataRetriever):
    def __init__(self):
        self.main_page_url: str = ScrapingURLs.PRIMARY_SCRAPER_URL.value
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.cache_expiry_secs: int = RedisConstants.CACHE_EXPIRY_SECS.value
        self.redis_max_items: int = RedisConstants.MAX_TIMES.value
        self.num_data_pages: int = 20

    def get_name(self) -> str:
        return ScraperNames.PRIMARY_SCRAPER_NAME.value
    
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
            await page.goto(self.main_page_url, timeout = 10000)
        except Exception as e:
            logger.warning(f"Error navigating to {self.main_page_url}: {str(e)}")
            raise InternalServerException("Fallback Failed")
        
        if chapter and chapter != "ALL":
            await page.locator("select#hsn-finder-chapter").select_option(value=chapter)

        await page.locator("input#hsn-finder-description").type(query, delay = 200)
        await page.wait_for_selector("div#FinderResults_grid__JO9ip", timeout=10000)

        try:
            await page.wait_for_selector("button.FinderResults_loadMoreBtn_GWzCI", timeout= 5000)
            button = page.locator("button.FinderResults_loadMoreBtn_GWzCI")
            while(button):
                await button.click(timeout = 5000)
                await page.wait_for_selector("button.FinderResults_loadMoreBtn_GWzCI", timeout= 5000)
                button = page.locator("button.FinderResults_loadMoreBtn_GWzCI")
        except Exception:
            logger.debug(f"{self.__class__.__name__}: no more load buttons.")
            pass

        link_container = page.locator("div.FinderResults_grid__JO9ip")
        link_tags = await link_container.locator("a.FinderResultCard_card_OfpDm").all()

        links = [await link_tag.get_attribute("href") for link_tag in link_tags]
        links = [ScraperBaseURLs.PRIMARY_SCRAPER_BASE_URL.value + link for link in links if link is not None]

        unique_links:set[str] = set()
        for link in links:
            if len(unique_links) < self.num_data_pages:
                unique_links.add(link) 
            else:
                break
        
        return unique_links

    async def __scrape_data_page(self, link: str) -> list[ScrapingResultItem]:
        page: Optional[Page] = None
        try:
            if self.context is None:
                raise RuntimeError("Browser context not initialized")
            page = await self.context.new_page()
            await page.goto(link, timeout= 10000)
            await page.wait_for_selector("table.HSNCodeTable_table_ug684", timeout=10000)
        except Exception as e:
            logger.debug(f"{self.__class__.__name__}: __scrape_data_page: {str(e)}")
            if page:
                await page.close()
            return []

        table = page.locator("table.HSNCodeTable_table_ug684")
        trs = await table.locator("tr").all()
        results = []
        for tr in trs[1:]:
            try:
                tds = await tr.locator("th, td").all()

                # HSN Code
                hsn_code = await tds[0].text_content()
                if hsn_code:
                    hsn_code = hsn_code.replace("Primary", "")
                else: continue
                
                # Description
                description = await tds[1].text_content()
                if description:
                    description = description.strip()
                else: continue

                # GST
                gst = await tds[2].text_content()
                if gst:
                    gst = gst.strip()

                # CGST
                cgst = await tds[3].text_content()
                if cgst:
                    cgst = cgst.strip()

                # SGST
                sgst = await tds[4].text_content()
                if sgst:
                    sgst = sgst.strip()

                # IGST
                igst = await tds[5].text_content()
                if igst:
                    igst = igst.strip()

                # CESS
                cess = await tds[6].text_content()
                if cess:
                    cess = cess.strip()

                results.append(ScrapingResultItem(
                    hsn_code = hsn_code,
                    description = description,
                    gst_rate = gst,
                    metadata= ScrapingResultItemMetadata(
                        ministry= None,
                        cgst= cgst,
                        sgst= sgst,
                        igst= igst,
                        cess= cess
                    )
                ))

            except Exception as e:
                logger.debug(f"{self.__class__.__name__}: __scrape_data_page: skipping row")
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
                raise InternalServerException("Redis Write Failed")

    async def data_fetch(self, query: str, chapter: str, conn: RedisConnection) -> None:
        async with async_playwright() as p:
            try: 
                self.browser = await p.chromium.launch(headless = settings.scraper_headless)
                self.context = await self.browser.new_context()

                links = await self.__scrape_main_page(query, chapter)

                for link in links:
                    results = await self.__scrape_data_page(link)
                    await self.__redis_store(conn = conn, query = query, chapter = chapter, results = results)
                    await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"{self.get_name} fetch operation failed {e}")
                return
            
            finally:
                if self.browser:
                    await self.browser.close()

