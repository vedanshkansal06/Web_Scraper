from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

from config.constants import ScraperStatus

class ScraperRequest(BaseModel):
    query: str = Field(..., title="Query", description="The query string to search for HSN codes.", min_length=1, max_length=50)
    chapter: Optional[str] = Field("ALL", title="Chapter", description="The chapter number for the HSN code.")
    page: Optional[int] = Field(1, title="Page", description="The page number for pagination.", ge=1)
    per_page: Optional[int] = Field(10, title="Per Page", description="The number of results per page.", ge=1, le=100)

    @field_validator("query")
    @classmethod
    def clean_query(cls, value: str) -> str:
        return value.lower().strip()[:50]
    
class ScrapingResultItemMetadata(BaseModel):
    ministry: Optional[str] = Field(None, title="Ministry", description="The ministry associated with the HSN code.")
    cgst: Optional[str] = Field(None, title="CGST", description="The Central Goods and Services Tax associated with the HSN code.")
    sgst: Optional[str] = Field(None, title="SGST", description="The State Goods and Services Tax associated with the HSN code.")
    igst: Optional[str] = Field(None, title="IGST", description="The Integrated Goods and Services Tax associated with the HSN code.")
    cess: Optional[str] = Field(None, title="CESS", description="The CESS associated with the HSN code.")

class ScrapingResultItem(BaseModel):
    hsn_code: str = Field(..., title="HSN Code", description="The Harmonized System of Nomenclature (HSN) code.")
    description: str = Field(..., title="Description", description="The description associated with the HSN code.")
    gst_rate: Optional[str] = Field(None, title="GST Rate", description="The Goods and Services Tax (GST) rate associated with the HSN code.")
    metadata: Optional[ScrapingResultItemMetadata] = Field(None, title="Metadata", description="Additional metadata associated with the HSN code.")

class ResponseData(BaseModel):
    scraper_status: ScraperStatus = Field(default=ScraperStatus.COMPLETED, title="Scraper Status", description="The status of the scraper.")
    total_results: int = Field(..., title="Total Results", description="The total number of results found for the query.")
    current_page: int = Field(..., title="Current Page", description="The current page number.")
    per_page: int = Field(..., title="Per Page", description="The number of results per page.")
    results: List[ScrapingResultItem] = Field(..., title="Results", description="The list of scraping result items.")

class ScraperResponse(BaseModel):
    success: bool = Field(..., title="Success", description="Indicates whether the scraping operation was successful.")
    message: str = Field(..., title="Message", description="An optional message providing additional information about the scraping operation.")
    data: ResponseData = Field(..., title="Data", description="The data containing the scraping results and metadata.")