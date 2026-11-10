import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID", "").strip()
GOOGLE_SHEET_TAB_NAME = os.getenv("GOOGLE_SHEET_TAB_NAME", "Leads").strip() or "Leads"
GOOGLE_CSE_API_KEY = os.getenv("GOOGLE_CSE_API_KEY", "").strip()
GOOGLE_CSE_CX = os.getenv("GOOGLE_CSE_CX", "").strip()
API_KEY = os.getenv("API_KEY", "")
_db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/leadforge")
DATABASE_URL = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1) if _db_url.startswith("postgresql://") and not _db_url.startswith("postgresql+asyncpg://") else _db_url
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
MAX_BODY_SIZE = int(os.getenv("MAX_BODY_SIZE", "1048576"))
# Places API Text Search pageSize is capped at 20. Larger searches are covered by
# scanning overlapping map circles and stopping at the campaign's max_results.
MAX_RESULTS_PER_QUERY = 20
SEARCH_RADIUS_METERS = 50000
OVERLAP_FACTOR = 0.7
