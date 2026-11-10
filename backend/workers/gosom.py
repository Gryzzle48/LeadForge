"""Lead search through a self-hosted gosom Google Maps scraper.

The web server (docker, `-data-folder`) exposes:

- POST /api/v1/jobs — create a job. `max_time` is seconds.
- GET  /api/v1/jobs/{id} — status is pending, working, ok, or failed.
- GET  /api/v1/jobs/{id}/download — results as CSV.

A blank website means the place page had none. Maps links and social-only
pages are not treated as a business website.
"""

import asyncio
import csv
import hashlib
import io
import json
import logging
import math
import time
from dataclasses import dataclass, field

import aiohttp

logger = logging.getLogger(__name__)

RETRY_STATUSES = {429, 500, 502, 503}
OK_STATUSES = {"ok", "completed", "success", "done"}
FAILED_STATUSES = {"failed", "error", "cancelled", "canceled"}
RUNNING_STATUSES = {"pending", "working", "running", "queued", "processing"}

_MAPS_MARKERS = (
    "google.com/maps",
    "maps.google.",
    "goo.gl/maps",
    "maps.app.goo.gl",
)

_SOCIAL_HOSTS = (
    "facebook.com",
    "fb.com",
    "fb.me",
    "instagram.com",
    "instagr.am",
    "twitter.com",
    "x.com",
    "tiktok.com",
    "linkedin.com",
    "linktr.ee",
    "linktree.com",
    "youtube.com",
    "youtu.be",
)


def has_real_website(uri: str | None) -> bool:
    """True only when the place lists a site of its own.

    A blank value, a Google Maps link, or a social profile is not a website.
    gosom reads the website field from the place page, so blank means none.
    """
    if uri is None:
        return False
    text = str(uri).strip()
    if not text:
        return False
    lowered = text.lower()
    if lowered in {"n/a", "na", "none", "null", "-", "no", "no website", "undefined"}:
        return False
    for marker in _MAPS_MARKERS:
        if marker in lowered:
            return False
    host = lowered
    if "://" in host:
        host = host.split("://", 1)[1]
    host = host.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    if ":" in host:
        host = host.split(":", 1)[0]
    for social in _SOCIAL_HOSTS:
        if host == social or host.endswith("." + social):
            return False
    return True


def passes_rating(rating: float | None, min_rating: float | None) -> bool:
    if min_rating is None or min_rating <= 0:
        return True
    if rating is None:
        return False
    try:
        return float(rating) + 1e-9 >= float(min_rating)
    except (TypeError, ValueError):
        return False


def passes_reviews(count: int | None, min_reviews: int | None, max_reviews: int | None) -> bool:
    if min_reviews is None and max_reviews is None:
        return True
    if count is None:
        return False
    try:
        count = int(count)
    except (TypeError, ValueError):
        return False
    if min_reviews is not None and count < min_reviews:
        return False
    if max_reviews is not None and count > max_reviews:
        return False
    return True


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lng / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(a)))


def inside_circle(lat, lng, center_lat: float, center_lng: float, radius_m: float, slack: float = 1.02) -> bool:
    if lat is None or lng is None:
        return True
    try:
        return haversine_m(float(lat), float(lng), center_lat, center_lng) <= float(radius_m) * slack
    except (TypeError, ValueError):
        return True


def zoom_for_radius(radius_m: int) -> int:
    radius_m = int(radius_m or 10000)
    if radius_m <= 2000:
        return 16
    if radius_m <= 5000:
        return 15
    if radius_m <= 10000:
        return 14
    if radius_m <= 25000:
        return 13
    return 12


def _lookup(raw: dict, *names: str):
    if not isinstance(raw, dict):
        return None
    lowered = {str(key).lower(): value for key, value in raw.items()}
    for name in names:
        if name in raw and raw[name] not in (None, ""):
            return raw[name]
        value = lowered.get(name.lower())
        if value not in (None, ""):
            return value
    return None


def _as_float(value):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _as_int(value):
    number = _as_float(value)
    if number is None:
        return None
    return int(number)


def _first_email(value) -> str:
    if isinstance(value, list):
        for item in value:
            text = str(item or "").strip()
            if "@" in text:
                return text
        return ""
    text = str(value or "").strip()
    return text if "@" in text else ""


def stable_place_id(record: dict) -> str:
    for key in ("place_id", "cid", "data_id"):
        value = str(record.get(key) or "").strip()
        if value:
            return value[:255]
    link = str(record.get("link") or "").strip()
    if link:
        if len(link) <= 255:
            return link
        return "link:" + hashlib.sha256(link.encode()).hexdigest()
    name = str(record.get("title") or "").strip()
    address = str(record.get("address") or "").strip()
    if name:
        return "na:" + hashlib.sha256(f"{name}|{address}".lower().encode()).hexdigest()
    return ""


def normalize_record(raw: dict) -> dict:
    categories = _lookup(raw, "categories")
    category = _lookup(raw, "category") or ""
    if not category and isinstance(categories, list) and categories:
        category = str(categories[0])
    website = _lookup(raw, "website", "web_site", "websiteUri") or ""
    link = _lookup(raw, "link", "googleMapsUri") or ""
    place_id = _lookup(raw, "place_id", "placeId") or ""
    return {
        "title": str(_lookup(raw, "title", "name", "displayName") or "").strip(),
        "category": str(category).strip(),
        "address": str(_lookup(raw, "address", "formattedAddress") or "").strip(),
        "phone": str(_lookup(raw, "phone", "internationalPhoneNumber") or "").strip(),
        "website": str(website).strip(),
        "link": str(link).strip(),
        "review_rating": _as_float(_lookup(raw, "review_rating", "rating")),
        "review_count": _as_int(_lookup(raw, "review_count", "userRatingCount", "reviews")),
        "latitude": _as_float(_lookup(raw, "latitude", "lat")),
        "longitude": _as_float(_lookup(raw, "longitude", "longtitude", "lng", "lon")),
        "place_id": str(place_id).strip(),
        "cid": str(_lookup(raw, "cid") or "").strip(),
        "data_id": str(_lookup(raw, "data_id") or "").strip(),
        "status": str(_lookup(raw, "status", "businessStatus") or "").strip(),
        "email": _first_email(_lookup(raw, "emails", "email")),
    }


def parse_csv(text: str) -> list[dict]:
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return []
    return [normalize_record(row) for row in reader if any((value or "").strip() for value in row.values())]


def extract_results(payload) -> list[dict] | None:
    """Return normalized places when the job payload already includes them."""
    if not isinstance(payload, dict):
        return None
    for key in ("results", "Results", "places", "Places", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [normalize_record(item) for item in value if isinstance(item, dict)]
        if isinstance(value, str) and value.strip().startswith("["):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, list):
                return [normalize_record(item) for item in parsed if isinstance(item, dict)]
    return None


def job_id_from(payload) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("id", "ID", "job_id", "jobId"):
        value = payload.get(key)
        if value:
            return str(value).strip()
    return ""


def job_status_from(payload) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("status", "Status"):
        value = payload.get(key)
        if value:
            return str(value).strip().lower()
    return ""


def job_error_from(payload) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("error", "Error", "message", "Message"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def is_permanently_closed(status: str) -> bool:
    text = (status or "").strip().lower().replace("_", " ")
    return "permanently closed" in text or text in {"closed permanently", "closed_permanently"}


@dataclass
class SearchStats:
    kept: list = field(default_factory=list)
    dropped_website: int = 0
    outside: int = 0
    closed: int = 0
    filtered_out: int = 0
    duplicates: int = 0


def select_places(
    records: list[dict],
    *,
    seen_ids: set[str],
    min_rating: float | None,
    min_reviews: int | None,
    max_reviews: int | None,
    center: tuple[float, float] | None,
    radius_m: float,
) -> SearchStats:
    stats = SearchStats()
    seen = set(seen_ids)
    for record in records:
        pid = stable_place_id(record)
        if not pid or pid in seen:
            stats.duplicates += 1
            continue
        seen.add(pid)
        if is_permanently_closed(record.get("status") or ""):
            stats.closed += 1
            continue
        if center and not inside_circle(
            record.get("latitude"), record.get("longitude"), center[0], center[1], radius_m
        ):
            stats.outside += 1
            continue
        if has_real_website(record.get("website")):
            stats.dropped_website += 1
            continue
        if not passes_rating(record.get("review_rating"), min_rating) or not passes_reviews(
            record.get("review_count"), min_reviews, max_reviews
        ):
            stats.filtered_out += 1
            continue
        kept = dict(record)
        kept["place_id"] = pid
        stats.kept.append(kept)
    return stats


def summarize_search(saved: int, stats: SearchStats, area_label: str | None, note: str | None = None) -> str:
    noun = "business" if saved == 1 else "businesses"
    parts = []
    if area_label:
        parts.append(f"Area: {area_label}.")
    parts.append(f"Saved {saved} {noun} with no website.")
    if stats.dropped_website:
        parts.append(f"Left out {stats.dropped_website} that already list a website.")
    if stats.outside:
        parts.append(f"Left out {stats.outside} outside the search radius.")
    if stats.closed:
        parts.append(f"Left out {stats.closed} that are permanently closed.")
    if stats.filtered_out:
        parts.append(f"Left out {stats.filtered_out} that missed the rating or review filter.")
    if stats.duplicates:
        parts.append(f"Skipped {stats.duplicates} already saved.")
    if note:
        parts.append(note)
    return " ".join(parts)[:4000]


def build_job_body(keyword: str, radius: int, lat, lng, depth: int, max_time: int) -> dict:
    """Body for POST /api/v1/jobs.

    gosom multiplies max_time by one second after reading the JSON number,
    so this value is a number of seconds, not nanoseconds.
    """
    return {
        "name": (keyword or "leadforge")[:80],
        "keywords": [keyword],
        "lang": "en",
        "zoom": zoom_for_radius(radius),
        "lat": "" if lat is None else str(lat),
        "lon": "" if lng is None else str(lng),
        "fast_mode": False,
        "radius": int(radius),
        "depth": int(depth),
        "email": False,
        "max_time": int(max_time),
    }


class GosomError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class GosomClient:
    def __init__(self, session: aiohttp.ClientSession, base_url: str):
        self.session = session
        self.base_url = (base_url or "").rstrip("/")

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    async def _request(self, method: str, path: str, body: dict | None, ok_statuses: tuple[int, ...]):
        last_error = "request failed"
        url = self._url(path)
        for attempt in range(4):
            try:
                async with self.session.request(method, url, json=body) as resp:
                    text = await resp.text()
                    if resp.status in RETRY_STATUSES:
                        last_error = f"HTTP {resp.status}: {text[:200]}"
                        await asyncio.sleep(min(2 ** attempt, 8))
                        continue
                    if resp.status in ok_statuses:
                        if not text.strip():
                            return {}, None
                        try:
                            data = json.loads(text)
                        except json.JSONDecodeError:
                            return text, None
                        return data, None
                    return None, f"HTTP {resp.status} from {url}: {text[:300]}"
            except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
                last_error = f"Could not reach the maps scraper at {url}: {exc}"
                await asyncio.sleep(min(2 ** attempt, 8))
        return None, last_error

    async def create_job(self, keyword: str, radius: int, lat, lng, depth: int, max_time: int) -> str:
        body = build_job_body(keyword, radius, lat, lng, depth, max_time)
        data, error = await self._request("POST", "/api/v1/jobs", body, (200, 201, 202))
        if error and "HTTP 404" in error:
            saas_body = {"keyword": keyword, "lang": "en", "max_depth": int(depth)}
            data, error = await self._request("POST", "/api/v1/scrape", saas_body, (200, 201, 202))
        if error:
            raise GosomError(error if "scraper" in error.lower() else f"Could not start a scrape. {error}")
        job_id = job_id_from(data if isinstance(data, dict) else {})
        if not job_id:
            raise GosomError("The scraper accepted the job but did not return an id.")
        return job_id

    async def wait_for_job(self, job_id: str, timeout_s: float, poll_seconds: float = 5):
        deadline = time.monotonic() + timeout_s
        last_status = "pending"
        last_payload = None
        while time.monotonic() < deadline:
            data, error = await self._request("GET", f"/api/v1/jobs/{job_id}", None, (200,))
            if error:
                raise GosomError(error if "scraper" in error.lower() else f"Could not check the scrape. {error}")
            last_payload = data if isinstance(data, dict) else {}
            status = job_status_from(last_payload)
            if status:
                last_status = status
            if status in FAILED_STATUSES:
                detail = job_error_from(last_payload) or "The scraper marked this job as failed. Google Maps may have blocked it."
                raise GosomError(detail)
            if status in OK_STATUSES or (extract_results(last_payload) and status not in RUNNING_STATUSES):
                return last_payload
            await asyncio.sleep(poll_seconds)
        raise GosomError(
            f"The scraper is still {last_status} after {int(timeout_s)} seconds. "
            "It may be blocked, or the area is large. Try a smaller radius, then run the search again."
        )

    async def fetch_results(self, job_id: str, payload) -> list[dict]:
        inline = extract_results(payload)
        if inline is not None:
            return inline
        data, error = await self._request("GET", f"/api/v1/jobs/{job_id}/download", None, (200,))
        if error:
            raise GosomError(
                "The scrape finished, but the results could not be downloaded. "
                + (error if "scraper" in error.lower() else error)
            )
        if isinstance(data, str):
            stripped = data.strip()
            if stripped.startswith("[") or stripped.startswith("{"):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    return [normalize_record(item) for item in parsed if isinstance(item, dict)]
                if isinstance(parsed, dict):
                    found = extract_results(parsed)
                    if found is not None:
                        return found
                    return [normalize_record(parsed)]
                rows = []
                for line in stripped.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        return parse_csv(data)
                    if isinstance(item, dict):
                        rows.append(normalize_record(item))
                if rows:
                    return rows
            return parse_csv(data)
        if isinstance(data, list):
            return [normalize_record(item) for item in data if isinstance(item, dict)]
        return []
