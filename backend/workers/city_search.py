"""Cover a whole city with gosom tiles.

The city outline comes from OpenStreetMap via Nominatim (no Google key).
Each tile is one gosom job using lat, lon, zoom, radius, and depth.
"""

import math
from dataclasses import dataclass

from .gosom import haversine_m, zoom_for_radius

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_CACHE: dict[str, "CityBounds"] = {}


@dataclass
class CityBounds:
    south: float
    north: float
    west: float
    east: float
    lat: float
    lng: float
    label: str


@dataclass
class Tile:
    lat: float
    lng: float
    radius_m: int
    zoom: int


@dataclass
class CoverProgress:
    tiles_done: int = 0
    places_checked: int = 0
    leads: int = 0
    empty_streak: int = 0


def clear_geocode_cache():
    _CACHE.clear()


def parse_nominatim(payload) -> CityBounds | None:
    if not isinstance(payload, list) or not payload:
        return None
    item = payload[0] if isinstance(payload[0], dict) else None
    if not item:
        return None
    try:
        lat = float(item["lat"])
        lng = float(item["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    box = item.get("boundingbox") or []
    try:
        south, north, west, east = (float(value) for value in box)
    except (TypeError, ValueError):
        south, north = lat - 0.045, lat + 0.045
        west, east = lng - 0.045, lng + 0.045
    if north < south:
        south, north = north, south
    if east < west:
        west, east = east, west
    if abs(north - south) < 0.01 and abs(east - west) < 0.01:
        south, north = lat - 0.045, lat + 0.045
        west, east = lng - 0.045, lng + 0.045
    label = str(item.get("display_name") or "").strip()
    return CityBounds(south, north, west, east, lat, lng, label)


def _split_bbox(bounds: CityBounds, tile_km: float) -> list[Tile]:
    height_km = max(abs(bounds.north - bounds.south) * 111.32, tile_km)
    mid_lat = (bounds.south + bounds.north) / 2
    width_km = max(abs(bounds.east - bounds.west) * 111.32 * max(math.cos(math.radians(mid_lat)), 0.2), tile_km)
    rows = max(1, math.ceil(height_km / tile_km - 1e-9))
    cols = max(1, math.ceil(width_km / tile_km - 1e-9))
    rows = min(rows, 40)
    cols = min(cols, 40)
    tiles = []
    for row in range(rows):
        lat1 = bounds.south + (bounds.north - bounds.south) * row / rows
        lat2 = bounds.south + (bounds.north - bounds.south) * (row + 1) / rows
        for col in range(cols):
            lng1 = bounds.west + (bounds.east - bounds.west) * col / cols
            lng2 = bounds.west + (bounds.east - bounds.west) * (col + 1) / cols
            center_lat = (lat1 + lat2) / 2
            center_lng = (lng1 + lng2) / 2
            radius = int(max(haversine_m(center_lat, center_lng, lat2, lng2), 400))
            radius = min(radius, 50000)
            tiles.append(Tile(
                lat=round(center_lat, 6),
                lng=round(center_lng, 6),
                radius_m=radius,
                zoom=zoom_for_radius(radius),
            ))
    return tiles


def plan_tiles(bounds: CityBounds, tile_km: float, max_tiles: int) -> tuple[list[Tile], bool]:
    """Return tiles that cover the box, and whether the tile limit cut the city short."""
    km = max(tile_km, 0.5)
    tiles = _split_bbox(bounds, km)
    while len(tiles) > max_tiles and km < 80:
        km = min(km * 1.4, 80)
        tiles = _split_bbox(bounds, km)
    truncated = len(tiles) > max_tiles
    if truncated:
        tiles = tiles[:max_tiles]
    return tiles, truncated


def should_stop_before_tile(progress: CoverProgress, *, elapsed: float, max_seconds: float, max_tiles: int, cancelled: bool) -> str | None:
    if cancelled:
        return "cancelled"
    if elapsed >= max_seconds:
        return "time_cap"
    if progress.tiles_done >= max_tiles:
        return "tile_cap"
    return None


def note_tile(
    progress: CoverProgress,
    *,
    new_places: int,
    new_leads: int,
    checked: int,
    target: int | None,
    empty_limit: int,
    tiles_total: int,
) -> str | None:
    progress.tiles_done += 1
    progress.places_checked += max(0, checked)
    progress.leads += max(0, new_leads)
    if new_places <= 0:
        progress.empty_streak += 1
    else:
        progress.empty_streak = 0
    if target is not None and progress.leads >= target:
        return "target"
    if progress.empty_streak >= empty_limit:
        return "exhausted"
    if progress.tiles_done >= tiles_total:
        return "tiles_done"
    return None


def finish_reason(reason: str | None, truncated: bool) -> str | None:
    if reason == "tiles_done" and truncated:
        return "tile_cap"
    return reason


def stop_message(reason: str | None) -> str:
    messages = {
        "target": "Stopped because the target number of leads was reached.",
        "exhausted": "Stopped because several areas in a row had no new businesses. The rest of the city was not searched.",
        "tiles_done": "Covered the city.",
        "time_cap": "Stopped because the search time limit was reached. Raise SEARCH_MAX_SECONDS to go longer.",
        "tile_cap": "Stopped because the tile limit was reached before every part of the city was covered. Raise SEARCH_MAX_TILES for a finer pass.",
        "cancelled": "Search cancelled. Leads found so far were saved.",
    }
    return messages.get(reason or "", "")


class GeocodeError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


async def geocode_city(session, location: str, user_agent: str) -> CityBounds | None:
    key = " ".join((location or "").lower().split())
    if not key:
        return None
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    headers = {"User-Agent": user_agent, "Accept": "application/json"}
    params = {"q": location, "format": "jsonv2", "limit": "1"}
    async with session.get(NOMINATIM_URL, params=params, headers=headers) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise GeocodeError(f"OpenStreetMap returned HTTP {resp.status} for that city. {text[:160]}")
        payload = await resp.json(content_type=None)
    bounds = parse_nominatim(payload)
    if bounds is None:
        return None
    _CACHE[key] = bounds
    return bounds
