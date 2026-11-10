import asyncio
import aiohttp
import math
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import async_session
from ..models.campaign import Campaign, CampaignStatus
from ..models.lead import Lead
from ..config import GOOGLE_MAPS_API_KEY, MAX_RESULTS_PER_QUERY, SEARCH_RADIUS_METERS, OVERLAP_FACTOR

logger = logging.getLogger(__name__)

PLACES_API_BASE = "https://places.googleapis.com/v1/places:searchText"
GEOCODING_API_BASE = "https://maps.googleapis.com/maps/api/geocode/json"
FIELDS_MASK = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.internationalPhoneNumber,places.websiteUri,places.googleMapsUri,"
    "places.rating,places.userRatingCount,places.primaryType"
)


def grid_circles(lat: float, lng: float, radius_m: int, step_m: int | None = None):
    if step_m is None:
        step_m = int(radius_m * OVERLAP_FACTOR)
    circles = []
    dlat = step_m / 111320
    dlng = step_m / (111320 * abs(math.cos(math.radians(lat))) + 1e-6)
    rlat = radius_m / 111320
    rlng = radius_m / (111320 * abs(math.cos(math.radians(lat))) + 1e-6)
    lat_start, lat_end = lat - rlat, lat + rlat
    lng_start, lng_end = lng - rlng, lng + rlng
    lat_c = lat_start
    while lat_c <= lat_end:
        lng_c = lng_start
        while lng_c <= lng_end:
            circles.append((round(lat_c, 6), round(lng_c, 6)))
            lng_c += dlng
        lat_c += dlat
    return circles


async def search_places(
    session: aiohttp.ClientSession,
    lat: float,
    lng: float,
    query: str,
    radius: int,
    min_rating: float | None = None,
) -> tuple[list, bool]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": FIELDS_MASK,
    }
    body = {
        "textQuery": query,
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": min(radius, SEARCH_RADIUS_METERS),
            }
        },
        "pageSize": MAX_RESULTS_PER_QUERY,
    }
    if min_rating is not None:
        body["minRating"] = min_rating

    try:
        async with session.post(PLACES_API_BASE, json=body, headers=headers) as resp:
            if resp.status != 200:
                response_text = await resp.text()
                logger.error("Places API error %s at (%s,%s): %s", resp.status, lat, lng, response_text[:200])
                return [], True
            data = await resp.json()
            return data.get("places", []), False
    except asyncio.TimeoutError:
        logger.warning("Places API timeout at (%s,%s)", lat, lng)
        return [], True
    except aiohttp.ClientError as exc:
        logger.error("Places API request failed at (%s,%s): %s", lat, lng, exc)
        return [], True
    except Exception:
        logger.exception("Unexpected error in search_places at (%s,%s)", lat, lng)
        return [], True


async def geocode_location(session: aiohttp.ClientSession, location: str) -> tuple[float, float] | None:
    params = {"address": location, "key": GOOGLE_MAPS_API_KEY}
    try:
        async with session.get(GEOCODING_API_BASE, params=params) as resp:
            if resp.status != 200:
                logger.error("Geocoding API error %s for %r", resp.status, location)
                return None
            data = await resp.json()
            if data.get("status") != "OK" or not data.get("results"):
                logger.error("Geocoding failed for %r: %s", location, data.get("status"))
                return None
            loc = data["results"][0]["geometry"]["location"]
            return loc["lat"], loc["lng"]
    except Exception:
        logger.exception("Geocoding exception for %r", location)
        return None


async def run_grid_search(campaign_id: int, req, _db_session: AsyncSession):
    async with async_session() as db:
        result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if not campaign:
            return

        campaign.status = CampaignStatus.RUNNING.value
        await db.commit()

        lat, lng = req.lat, req.lng
        radius = req.radius or 50000
        location = req.location or campaign.location

        if lat is None or lng is None:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as geo_session:
                coords = await geocode_location(geo_session, location)
            if not coords:
                campaign.status = CampaignStatus.FAILED.value
                await db.commit()
                logger.error("Campaign %s stopped: could not geocode %r", campaign_id, location)
                return
            lat, lng = coords
            campaign.lat, campaign.lng = lat, lng
            await db.commit()

        centers = grid_circles(lat, lng, radius)
        existing_result = await db.execute(select(Lead.place_id))
        seen_place_ids = {row[0] for row in existing_result if row[0]}

        total_errors = 0
        total_attempts = 0
        added_place_ids = []
        target_count = req.max_results

        timeout = aiohttp.ClientTimeout(total=35)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            batch_size = 5
            for offset in range(0, len(centers), batch_size):
                if len(added_place_ids) >= target_count:
                    break

                batch = centers[offset:offset + batch_size]
                results = await asyncio.gather(*[
                    search_places(session, clat, clng, req.query, radius, req.min_rating)
                    for clat, clng in batch
                ])

                for places, is_error in results:
                    total_attempts += 1
                    if is_error:
                        total_errors += 1
                        continue

                    for place in places:
                        if len(added_place_ids) >= target_count:
                            break

                        place_id = place.get("id")
                        if not place_id or place_id in seen_place_ids:
                            continue
                        seen_place_ids.add(place_id)

                        website = (place.get("websiteUri") or "").strip()
                        if website:
                            continue

                        name = (place.get("displayName") or {}).get("text") or "Unknown"
                        category = place.get("primaryType") or req.query
                        maps_url = place.get("googleMapsUri") or (
                            "https://www.google.com/maps/search/?api=1&query_place_id=" + place_id
                        )

                        db.add(Lead(
                            campaign_id=campaign_id,
                            place_id=place_id,
                            name=name,
                            address=place.get("formattedAddress") or "",
                            phone=place.get("internationalPhoneNumber") or "",
                            email=None,
                            instagram_url=None,
                            google_maps_url=maps_url,
                            category=category,
                            rating=place.get("rating"),
                            review_count=place.get("userRatingCount"),
                            website_uri=None,
                            has_website=False,
                            email_status="no_email",
                        ))
                        added_place_ids.append(place_id)

                await db.commit()

        campaign.total_leads = len(added_place_ids)
        if total_attempts > 0 and total_errors == total_attempts:
            campaign.status = CampaignStatus.FAILED.value
            logger.error("Campaign %s: all %s Places API calls failed", campaign_id, total_errors)
        else:
            campaign.status = CampaignStatus.COMPLETED.value
            logger.info("Campaign %s completed with %s new leads", campaign_id, len(added_place_ids))
        await db.commit()
