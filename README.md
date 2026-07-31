# HSN Web Scraper API

A robust, asynchronous microservice built with **FastAPI** designed to fetch, aggregate, and cache GST metadata and Harmonized System of Nomenclature (HSN) codes from highly dynamic web sources. 

This API employs a highly resilient **Cascading Fallback Scraper Engine** built upon **Playwright** and a dual-layer caching strategy (**Redis** and **MongoDB**) to ensure high availability, speed, and fault tolerance against fragile web sources, layout changes, or bot protections.

## Key Features

- **High-Speed Caching**: Uses Redis to store recent queries and serve repeated requests in milliseconds, skipping the resource-intensive scraping process.
- **Long-term Persistence**: Persists historical scraped data in MongoDB for long-term lookups.
- **Cascading Fallback Scraper Engine**: Dynamically degrades from a Primary scraper (Registerkaro) to Secondary (Piceapp with fuzzy matching) and Tertiary (Credlix) scrapers if a target fails or blocks the request.
- **Concurrency Management**: Uses Redis distributed locks (`setnx`) to prevent launching multiple headless browser instances for identical concurrent requests.
- **Data Validation**: Strict request and response data validation using Pydantic.
- **Asynchronous & Headless**: Fully async using `motor`, `aioredis`, and `playwright` for lightning-fast performance.

## Tech Stack

- **Framework**: FastAPI (Python 3.9+)
- **Browser Automation**: Playwright (Chromium)
- **Primary Cache**: Redis
- **Database**: MongoDB (Motor AsyncIO Driver)
- **Data Validation**: Pydantic
- **Fuzzy Matching**: RapidFuzz

## System Workflow

1. **API Request**: The user sends a search query to the FastAPI endpoint (`/api/v1/search`).
2. **Cache Check (Redis)**: Checks Redis for a cached response. If found, returns instantly.
3. **Database Check (MongoDB)**: On a cache miss, checks MongoDB for historical data.
4. **Scraper Activation**: If no data is found, triggers the Scraper Engine.
5. **Fallback Sequence**: Attempts Primary Scraper -> Secondary Scraper -> Tertiary Scraper.
6. **Data Persistence**: Successfully scraped data is saved back to Redis and MongoDB before returning to the user.

## Prerequisites

- **Python** 3.9 or higher
- **Redis Server** running locally (port 6379) or accessible via network.
- **MongoDB Server** running locally (port 27017) or accessible via network.

## Installation

1. **Clone the repository** (or navigate to the project directory):
   ```bash
   cd "HSN scraper service"
   ```

2. **Create and activate a virtual environment** (optional but recommended):
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install fastapi uvicorn pydantic pydantic-settings motor redis playwright rapidfuzz
   ```

4. **Install Playwright Chromium browser**:
   ```bash
   playwright install chromium
   ```

## Configuration

Rename the provided `.env.txt` to `.env` or create a new `.env` file in the root directory:

```env
SCRAPER_HEADLESS=True
MONGO_URI=mongodb://localhost:27017/
MONGO_DB_NAME=hsn_scraper_db
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
```

## Running the Application

Start the FastAPI server using `uvicorn`:

```bash
python main.py
# OR
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API will be available at:
- **Swagger UI documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## API Usage

### Search HSN Code

**Endpoint**: `POST /api/v1/search`

**Request Body**:
```json
{
  "query": "smartphones",
  "chapter": "ALL",
  "page": 1,
  "per_page": 10
}
```

**cURL Example**:
```bash
curl -X 'POST' \
  'http://localhost:8000/api/v1/search' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "query": "smartphones",
  "chapter": "ALL",
  "page": 1,
  "per_page": 10
}'
```

**Response**:
```json
{
  "success": true,
  "message": "Data retrieved successfully.",
  "data": {
    "scraper_status": "completed",
    "total_results": 1,
    "current_page": 1,
    "per_page": 10,
    "results": [
      {
        "hsn_code": "8517",
        "description": "Smartphones...",
        "gst_rate": "18%",
        "metadata": {
          "ministry": null,
          "cgst": "9%",
          "sgst": "9%",
          "igst": "18%",
          "cess": "0%"
        }
      }
    ]
  }
}
```

## Error Handling

The API uses custom standardized HTTP exceptions:
- **400 Bad Request** (`ValidationException`): Invalid input constraints (e.g., chapter not valid).
- **404 Not Found** (`NotFoundException`): Valid queries yield no results across databases and active scrapers.
- **409 Conflict** (`ConflictException`): Triggered gracefully to manage duplicate concurrent requests relying on cache polling.
- **500 Internal Server Error** (`InternalServerException`): When the scraper factory is exhausted (all fallback nodes fail) or critical infrastructure (Redis/Mongo) disconnects.
