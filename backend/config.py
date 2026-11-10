import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID", "").strip()
GOOGLE_SHEET_TAB_NAME = os.getenv("GOOGLE_SHEET_TAB_NAME", "Leads").strip() or "Leads"
MAPS_SCRAPER_API_URL = os.getenv("MAPS_SCRAPER_API_URL", "http://127.0.0.1:8080").rstrip("/")
API_KEY = os.getenv("API_KEY", "")
_db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/leadforge")
DATABASE_URL = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1) if _db_url.startswith("postgresql://") and not _db_url.startswith("postgresql+asyncpg://") else _db_url
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
MAX_BODY_SIZE = int(os.getenv("MAX_BODY_SIZE", "1048576"))
# One Maps search query is limited to a practical maximum of about 120 results.
MAX_RESULTS_PER_QUERY = 120
