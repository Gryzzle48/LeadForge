import asyncio
import logging
import re
from urllib.parse import urlparse

import aiohttp

from ..config import GOOGLE_CSE_API_KEY, GOOGLE_CSE_CX

logger = logging.getLogger(__name__)

CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
INSTAGRAM_RE = re.compile(
    r"https?://(?:www\.)?instagram\.com/[A-Za-z0-9._]+/?",
    re.IGNORECASE,
)
IGNORED_EMAILS = {"example@example.com", "test@example.com", "name@example.com"}
IGNORED_PATHS = {"p", "reel", "reels", "stories", "explore", "accounts", "about"}


def _valid_instagram_url(value: str) -> str | None:
    match = INSTAGRAM_RE.search(value or "")
    if not match:
        return None
    url = match.group(0).rstrip("/")
    path = urlparse(url).path.strip("/").split("/")
    if not path or path[0].lower() in IGNORED_PATHS:
        return None
    return url


def _extract_contacts(items: list[dict]) -> dict:
    emails: list[str] = []
    instagram_urls: list[str] = []
    sources: list[str] = []

    for item in items:
        link = str(item.get("link") or "")
        title = str(item.get("title") or "")
        snippet = str(item.get("snippet") or "")
        text = " ".join((title, snippet, link))

        for email in EMAIL_RE.findall(text):
            normalized = email.strip(".,;:!?)(").lower()
            if normalized not in IGNORED_EMAILS and normalized not in emails:
                emails.append(normalized)

        instagram_url = _valid_instagram_url(link) or _valid_instagram_url(text)
        if instagram_url and instagram_url not in instagram_urls:
            instagram_urls.append(instagram_url)

        parsed = urlparse(link)
        if parsed.scheme == "https" and parsed.netloc and link not in sources:
            sources.append(link)

    return {
        "email": emails[0] if emails else None,
        "instagram_url": instagram_urls[0] if instagram_urls else None,
        "sources": sources[:5],
    }


async def find_public_contacts(
    business_name: str,
    city: str | None,
    state: str | None,
) -> dict:
    """Find contact details from public Google Search results, not Maps content."""
    if not GOOGLE_CSE_API_KEY or not GOOGLE_CSE_CX:
        raise RuntimeError(
            "Contact search is not configured. Set GOOGLE_CSE_API_KEY and GOOGLE_CSE_CX."
        )

    location = " ".join(part for part in (city, state) if part)
    query = f'"{business_name}" {location} (email OR contact OR Instagram)'.strip()
    params = {
        "key": GOOGLE_CSE_API_KEY,
        "cx": GOOGLE_CSE_CX,
        "q": query,
        "num": 10,
    }

    timeout = aiohttp.ClientTimeout(total=15, connect=5)
    connector = aiohttp.TCPConnector(limit=2)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        try:
            async with session.get(CSE_ENDPOINT, params=params) as response:
                if response.status != 200:
                    body = (await response.text())[:300]
                    logger.warning("Custom Search API returned %s: %s", response.status, body)
                    raise RuntimeError(f"Contact search provider returned HTTP {response.status}.")
                payload = await response.json()
        except asyncio.TimeoutError as exc:
            raise RuntimeError("Contact search timed out. Please try again.") from exc
        except aiohttp.ClientError as exc:
            raise RuntimeError("Could not reach the contact search provider.") from exc

    return _extract_contacts(payload.get("items") or [])
