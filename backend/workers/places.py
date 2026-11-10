"""Google Places (New) helpers.

Text Search returns at most 20 places per page and 60 per query. Callers page
through nextPageToken and split a saturated area into smaller rectangles.
websiteUri on the search response is not trusted by itself: a missing value is
confirmed with Place Details so a business that has a site is not saved as a lead.
"""

import asyncio
import json
import logging
import math
from dataclasses import dataclass, field
from urllib.parse import quote

import aiohttp

logger = logging.getLogger(__name__)

PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PLACES_DETAIL_URL = "https://places.googleapis.com/v1/places/{place_id}"
PAGE_SIZE = 20
MAX_PAGES = 3
MAX_RADIUS_METERS = 50000
MIN_CELL_METERS = 1500
MAX_SEARCH_REQUESTS = 36
MAX_DETAIL_LOOKUPS = 200
RETRY_STATUSES = {429, 500, 502, 503}

SEARCH_FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.internationalPhoneNumber",
    "places.nationalPhoneNumber",
    "places.websiteUri",
    "places.googleMapsUri",
    "places.rating",
    "places.userRatingCount",
    "places.primaryType",
    "places.primaryTypeDisplayName",
    "places.businessStatus",
    "places.location",
    "nextPageToken",
])

DETAIL_FIELD_MASK = ",".join([
    "id",
    "displayName",
    "formattedAddress",
    "internationalPhoneNumber",
    "nationalPhoneNumber",
    "websiteUri",
    "googleMapsUri",
    "rating",
    "userRatingCount",
    "primaryType",
    "primaryTypeDisplayName",
    "businessStatus",
    "location",
])

_MAPS_MARKERS = (
    "google.com/maps",
    "maps.google.",
    "goo.gl/maps",
    "maps.app.goo.gl",
)


def has_real_website(uri: str | None) -> bool:
    """True when Google lists a website that is not just a Maps link."""
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
    return True


def api_min_rating(min_rating: float | None) -> float | None:
    """Value safe to send as Places minRating.

    The API rounds the cutoff up to the next 0.5, so 4.2 would drop a 4.3-star
    business. Send the next lower 0.5 step and apply the exact cutoff locally.
    """
    if min_rating is None or min_rating <= 0:
        return None
    stepped = math.floor((float(min_rating) + 1e-9) * 2) / 2
    if stepped <= 0:
        return None
    return min(5.0, stepped)


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
    radius = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lng / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(a)))


def inside_circle(lat, lng, center_lat: float, center_lng: float, radius_m: float, slack: float = 1.02) -> bool:
    """Keep a place when its coordinates are inside the search circle.

    A missing coordinate is kept. Text Search with a rectangle restriction is
    supposed to have already bounded it, and dropping it would lose a real lead.
    """
    if lat is None or lng is None:
        return True
    try:
        return haversine_m(float(lat), float(lng), center_lat, center_lng) <= radius_m * slack
    except (TypeError, ValueError):
        return True


def normalize_bounds(bounds: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    low_lat, low_lng, high_lat, high_lng = bounds
    if low_lat > high_lat:
        low_lat, high_lat = high_lat, low_lat
    if low_lng > high_lng:
        low_lng, high_lng = high_lng, low_lng
    return (round(low_lat, 6), round(low_lng, 6), round(high_lat, 6), round(high_lng, 6))


def circle_bounds(lat: float, lng: float, radius_m: float) -> tuple[float, float, float, float]:
    radius_m = min(max(float(radius_m), 1), MAX_RADIUS_METERS)
    d_lat = radius_m / 111320
    d_lng = radius_m / (111320 * max(abs(math.cos(math.radians(lat))), 0.01))
    return normalize_bounds((lat - d_lat, lng - d_lng, lat + d_lat, lng + d_lng))


def subdivide(low_lat: float, low_lng: float, high_lat: float, high_lng: float) -> list[tuple[float, float, float, float]]:
    mid_lat = (low_lat + high_lat) / 2
    mid_lng = (low_lng + high_lng) / 2
    return [
        normalize_bounds((low_lat, low_lng, mid_lat, mid_lng)),
        normalize_bounds((low_lat, mid_lng, mid_lat, high_lng)),
        normalize_bounds((mid_lat, low_lng, high_lat, mid_lng)),
        normalize_bounds((mid_lat, mid_lng, high_lat, high_lng)),
    ]


def cell_span_meters(bounds: tuple[float, float, float, float]) -> float:
    low_lat, low_lng, high_lat, high_lng = bounds
    height = abs(high_lat - low_lat) * 111320
    mid_lat = (low_lat + high_lat) / 2
    width = abs(high_lng - low_lng) * 111320 * max(abs(math.cos(math.radians(mid_lat))), 0.01)
    return max(height, width)


def cell_radius_m(bounds: tuple[float, float, float, float]) -> float:
    low_lat, low_lng, high_lat, high_lng = bounds
    mid_lat = (low_lat + high_lat) / 2
    mid_lng = (low_lng + high_lng) / 2
    corner = haversine_m(mid_lat, mid_lng, high_lat, high_lng)
    return min(max(corner, 1.0), float(MAX_RADIUS_METERS))


def normalize_place_id(place: dict) -> str:
    pid = place.get("id") or ""
    if not pid and isinstance(place.get("name"), str) and place["name"].startswith("places/"):
        pid = place["name"].split("/", 1)[1]
    pid = str(pid)
    if pid.startswith("places/"):
        pid = pid.split("/", 1)[1]
    return pid.strip()


def place_location(place: dict) -> tuple[float | None, float | None]:
    loc = place.get("location") or {}
    if not isinstance(loc, dict):
        return None, None
    return loc.get("latitude"), loc.get("longitude")


def place_name(place: dict) -> str:
    display = place.get("displayName") or {}
    if isinstance(display, dict):
        return (display.get("text") or "Unknown").strip() or "Unknown"
    text = str(display).strip()
    return text or "Unknown"


def category_label(place: dict) -> str:
    display = place.get("primaryTypeDisplayName") or {}
    if isinstance(display, dict) and display.get("text"):
        return str(display["text"]).strip()
    raw = str(place.get("primaryType") or "").replace("_", " ").strip()
    return raw


def phone_of(place: dict) -> str:
    return (place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber") or "").strip()


def maps_link(place: dict) -> str:
    uri = (place.get("googleMapsUri") or "").strip()
    if uri:
        return uri
    pid = normalize_place_id(place)
    if not pid:
        return ""
    return f"https://www.google.com/maps/search/?api=1&query_place_id={pid}"


def merge_details(search_place: dict, details: dict | None) -> dict:
    if not details:
        return search_place
    merged = dict(search_place)
    for key in (
        "websiteUri",
        "googleMapsUri",
        "internationalPhoneNumber",
        "nationalPhoneNumber",
        "rating",
        "userRatingCount",
        "primaryType",
        "primaryTypeDisplayName",
        "formattedAddress",
        "displayName",
        "businessStatus",
        "location",
    ):
        value = details.get(key)
        if value not in (None, "", {}, []):
            merged[key] = value
    if details.get("id") and not merged.get("id"):
        merged["id"] = details["id"]
    return merged


def build_search_body(text_query: str, bounds, min_rating: float | None, mode: str) -> dict:
    low_lat, low_lng, high_lat, high_lng = normalize_bounds(bounds)
    rectangle = {
        "low": {"latitude": low_lat, "longitude": low_lng},
        "high": {"latitude": high_lat, "longitude": high_lng},
    }
    body = {
        "textQuery": text_query,
        "pageSize": PAGE_SIZE,
        "languageCode": "en",
    }
    if mode == "bias":
        mid_lat = (low_lat + high_lat) / 2
        mid_lng = (low_lng + high_lng) / 2
        body["locationBias"] = {
            "circle": {
                "center": {"latitude": round(mid_lat, 6), "longitude": round(mid_lng, 6)},
                "radius": cell_radius_m((low_lat, low_lng, high_lat, high_lng)),
            }
        }
    else:
        body["locationRestriction"] = {"rectangle": rectangle}
    stepped = api_min_rating(min_rating)
    if stepped is not None:
        body["minRating"] = stepped
    return body


def restriction_was_rejected(error: str | None) -> bool:
    if not error:
        return False
    text = error.lower()
    return "locationrestriction" in text or "location restriction" in text


def resolve_origin(lat, lng, geocoded):
    """Pick a search center. Never substitute a default city."""
    if lat is not None and lng is not None:
        return (float(lat), float(lng), None), None
    if geocoded is not None:
        return geocoded, None
    return None, (
        "Could not find that place on Google Maps. Check the city name, and make sure "
        "Places API (New) is enabled for the API key."
    )


@dataclass
class SearchStats:
    kept: list = field(default_factory=list)
    dropped_website: int = 0
    unverified: int = 0
    outside: int = 0
    closed: int = 0
    filtered_out: int = 0
    duplicates: int = 0
    capped: int = 0


def select_leads(
    places: list[dict],
    details_by_id: dict[str, dict],
    *,
    seen_ids: set[str],
    min_rating: float | None,
    min_reviews: int | None,
    max_reviews: int | None,
    center: tuple[float, float] | None,
    radius_m: float,
    details_available: bool = True,
    skipped_for_cap: set[str] | None = None,
) -> SearchStats:
    stats = SearchStats()
    seen = set(seen_ids)
    cap = skipped_for_cap or set()
    for place in places:
        pid = normalize_place_id(place)
        if not pid or pid in seen:
            stats.duplicates += 1
            continue
        seen.add(pid)
        if place.get("businessStatus") == "CLOSED_PERMANENTLY":
            stats.closed += 1
            continue
        lat, lng = place_location(place)
        if center and not inside_circle(lat, lng, center[0], center[1], radius_m):
            stats.outside += 1
            continue
        if has_real_website(place.get("websiteUri")):
            stats.dropped_website += 1
            continue
        if pid in cap:
            stats.capped += 1
            continue
        merged = place
        if details_available:
            details = details_by_id.get(pid)
            if not details:
                stats.unverified += 1
                continue
            merged = merge_details(place, details)
            if merged.get("businessStatus") == "CLOSED_PERMANENTLY":
                stats.closed += 1
                continue
            if has_real_website(merged.get("websiteUri")):
                stats.dropped_website += 1
                continue
        if not passes_rating(merged.get("rating"), min_rating) or not passes_reviews(
            merged.get("userRatingCount"), min_reviews, max_reviews
        ):
            stats.filtered_out += 1
            continue
        stats.kept.append(merged)
    return stats


def summarize_search(saved: int, stats: SearchStats, errors: list[str], truncated: bool, area_label: str | None, details_note: str | None) -> str:
    parts = []
    if area_label:
        parts.append(f"Area: {area_label}.")
    parts.append(f"Saved {saved} {'business' if saved == 1 else 'businesses'} with no website.")
    if stats.dropped_website:
        parts.append(f"Left out {stats.dropped_website} that already list a website.")
    if stats.outside:
        parts.append(f"Left out {stats.outside} outside the search radius.")
    if stats.closed:
        parts.append(f"Left out {stats.closed} that are permanently closed.")
    if stats.filtered_out:
        parts.append(f"Left out {stats.filtered_out} that missed the rating or review filter.")
    if stats.unverified:
        parts.append(f"Left out {stats.unverified} because the website could not be confirmed.")
    if stats.capped:
        parts.append(
            f"Left out {stats.capped} because this search hit the website-check limit. Use a smaller radius to include more."
        )
    if errors:
        parts.append(f"{len(errors)} Google request(s) failed. Last error: {errors[-1][:220]}")
    if truncated:
        parts.append("The area was too large to finish. Results may be incomplete. Try a smaller radius.")
    if details_note:
        parts.append(details_note)
    return " ".join(parts)[:4000]


async def collect_pages(fetch_page, max_pages: int = MAX_PAGES):
    """Follow nextPageToken up to max_pages.

    fetch_page(token) -> (places, next_token, error).
    A token still present after the last page means the query hit the 60-result cap.
    """
    places = []
    token = None
    requests = 0
    for _ in range(max_pages):
        batch, token, error = await fetch_page(token)
        requests += 1
        if error:
            return places, requests, False, error
        places.extend(batch or [])
        if not token:
            return places, requests, False, None
    return places, requests, True, None


async def walk_area(search_cell, bounds, max_requests: int = MAX_SEARCH_REQUESTS, min_cell_m: float = MIN_CELL_METERS):
    """Search a rectangle, splitting cells that come back full."""
    queue = [normalize_bounds(bounds)]
    found = []
    errors = []
    used_total = 0
    while queue and used_total < max_requests:
        cell = queue.pop(0)
        places, used, saturated, error = await search_cell(cell)
        used_total += used or 0
        if error:
            errors.append(str(error))
        found.extend(places or [])
        if saturated and cell_span_meters(cell) > min_cell_m and used_total < max_requests:
            queue.extend(subdivide(*cell))
    return found, errors, used_total, bool(queue)


def detail_error_is_fatal(error: str | None) -> bool:
    if not error:
        return False
    text = error.lower()
    if "http 401" in text or "http 403" in text:
        return True
    return any(bit in text for bit in ("api key", "billing", "fieldmask", "field mask"))


class PlacesClient:
    def __init__(self, session: aiohttp.ClientSession, api_key: str):
        self.session = session
        self.api_key = api_key

    def _headers(self, field_mask: str) -> dict:
        return {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": field_mask,
        }

    async def _request(self, method: str, url: str, headers: dict, json_body: dict | None):
        last_error = "request failed"
        fatal = False
        for attempt in range(4):
            try:
                async with self.session.request(method, url, headers=headers, json=json_body) as resp:
                    text = await resp.text()
                    if resp.status in RETRY_STATUSES:
                        last_error = f"HTTP {resp.status}: {text[:200]}"
                        fatal = False
                        await asyncio.sleep(min(2 ** attempt, 8))
                        continue
                    if resp.status == 200:
                        try:
                            data = json.loads(text) if text else {}
                        except json.JSONDecodeError:
                            return None, "Places API returned invalid JSON", False
                        return data, None, False
                    last_error = f"HTTP {resp.status}: {text[:300]}"
                    fatal = detail_error_is_fatal(last_error) or resp.status in (401, 403)
                    return None, last_error, fatal
            except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
                last_error = str(exc)
                fatal = False
                await asyncio.sleep(min(2 ** attempt, 8))
        return None, last_error, fatal

    async def _search_mode(self, text_query: str, bounds, min_rating: float | None, mode: str):
        body = build_search_body(text_query, bounds, min_rating, mode)
        headers = self._headers(SEARCH_FIELD_MASK)

        async def fetch_page(token):
            payload = dict(body)
            if token:
                payload["pageToken"] = token
            data, error, _fatal = await self._request("POST", PLACES_SEARCH_URL, headers, payload)
            if error:
                return [], None, error
            return data.get("places") or [], data.get("nextPageToken") or None, None

        return await collect_pages(fetch_page)

    async def search_cell(self, text_query: str, bounds, min_rating: float | None):
        total_used = 0
        last_error = None
        for mode in ("restriction", "bias"):
            places, used, saturated, error = await self._search_mode(text_query, bounds, min_rating, mode)
            total_used += used
            if error and mode == "restriction" and restriction_was_rejected(error):
                last_error = error
                logger.warning("Places API rejected locationRestriction (%s). Retrying with locationBias.", error[:180])
                continue
            return places, total_used, saturated, error
        return [], total_used, False, last_error

    async def place_details(self, place_id: str):
        url = PLACES_DETAIL_URL.format(place_id=quote(place_id, safe=""))
        data, error, fatal = await self._request("GET", url, self._headers(DETAIL_FIELD_MASK), None)
        if error and not fatal:
            fatal = detail_error_is_fatal(error)
        return data, error, fatal

    async def geocode(self, location: str):
        body = {"textQuery": location, "pageSize": 1}
        data, error, _fatal = await self._request(
            "POST",
            PLACES_SEARCH_URL,
            self._headers("places.location,places.formattedAddress,places.displayName"),
            body,
        )
        if error or not data:
            logger.error("Could not geocode %r: %s", location, error)
            return None
        places = data.get("places") or []
        if not places:
            logger.error("No geocode result for %r", location)
            return None
        loc = places[0].get("location") or {}
        lat, lng = loc.get("latitude"), loc.get("longitude")
        if lat is None or lng is None:
            return None
        label = places[0].get("formattedAddress")
        if not label:
            display = places[0].get("displayName") or {}
            label = display.get("text") if isinstance(display, dict) else None
        return float(lat), float(lng), label or location


async def fetch_details_map(client: PlacesClient, place_ids: list[str]) -> tuple[dict[str, dict], str | None, str | None]:
    found: dict[str, dict] = {}
    fatal_msg = None
    sample_error = None
    semaphore = asyncio.Semaphore(5)

    async def one(pid: str):
        nonlocal fatal_msg, sample_error
        if fatal_msg:
            return
        async with semaphore:
            if fatal_msg:
                return
            data, error, fatal = await client.place_details(pid)
            if fatal:
                fatal_msg = error or "Place Details is unavailable"
                return
            if data is not None:
                found[pid] = data
            elif error:
                sample_error = error
                logger.warning("Place Details failed for %s: %s", pid, error[:180])

    await asyncio.gather(*(one(pid) for pid in place_ids))
    return found, fatal_msg, sample_error
