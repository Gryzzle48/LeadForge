import os
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dotenv import load_dotenv

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
# Load backend/.env no matter which directory the server was started from.
# Existing environment variables (Railway, shell) are left as they are.
load_dotenv(os.path.join(_BACKEND_DIR, ".env"))
load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_SHEET_SHARE_EMAIL = os.getenv("GOOGLE_SHEET_SHARE_EMAIL", "").strip()
API_KEY = os.getenv("API_KEY", "")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
MAX_BODY_SIZE = int(os.getenv("MAX_BODY_SIZE", "1048576"))


def normalize_database_url(url: str) -> tuple[str, dict]:
    """Return an asyncpg URL and connect args.

    Railway sometimes hands out postgres:// and ?sslmode=require. asyncpg
    rejects both the postgres scheme and the sslmode query parameter, which
    makes the API start and then fail every database call.
    """
    url = (url or "").strip()
    connect_args: dict = {"timeout": 5}
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if "://" in url:
        scheme, rest = url.split("://", 1)
        if scheme == "postgresql":
            url = "postgresql+asyncpg://" + rest
    parsed = urlparse(url)
    query = {}
    sslmode = None
    ssl_flag = None
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered == "sslmode":
            sslmode = value
        elif lowered == "channel_binding":
            continue
        elif lowered == "ssl":
            ssl_flag = value
        else:
            query[key] = value
    needs_ssl = bool(sslmode and sslmode.lower() not in ("disable", "allow", ""))
    if ssl_flag and ssl_flag.lower() in ("require", "true", "1"):
        needs_ssl = True
    if needs_ssl:
        connect_args["ssl"] = True
    return urlunparse(parsed._replace(query=urlencode(query))), connect_args


_raw_db = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/leadforge",
)
DATABASE_URL, DB_CONNECT_ARGS = normalize_database_url(_raw_db)
