import logging

import aiohttp
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..config import GOOGLE_MAPS_API_KEY
from ..database import async_session
from ..models.campaign import Campaign, CampaignStatus
from ..models.lead import Lead
from .email_writer import generate_emails_for_campaign
from .places import (
    MAX_DETAIL_LOOKUPS,
    MAX_RADIUS_METERS,
    PlacesClient,
    category_label,
    circle_bounds,
    fetch_details_map,
    has_real_website,
    inside_circle,
    maps_link,
    normalize_place_id,
    phone_of,
    place_location,
    place_name,
    resolve_origin,
    select_leads,
    summarize_search,
    walk_area,
)

logger = logging.getLogger(__name__)


def _clip(value, limit: int) -> str:
    text = "" if value is None else str(value)
    return text[:limit]


def _as_float(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value):
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def lead_from_place(campaign_id: int, place: dict) -> Lead:
    return Lead(
        campaign_id=campaign_id,
        place_id=_clip(normalize_place_id(place), 255),
        name=_clip(place_name(place), 255),
        address=_clip(place.get("formattedAddress") or "", 500),
        phone=_clip(phone_of(place), 50),
        category=_clip(category_label(place), 255),
        rating=_as_float(place.get("rating")),
        review_count=_as_int(place.get("userRatingCount")),
        website_uri=_clip(place.get("websiteUri") or "", 500),
        has_website=False,
        maps_url=maps_link(place),
        email_status="draft",
    )


def _copy_lead(source: Lead) -> Lead:
    return Lead(
        campaign_id=source.campaign_id,
        place_id=source.place_id,
        name=source.name,
        address=source.address,
        phone=source.phone,
        category=source.category,
        rating=source.rating,
        review_count=source.review_count,
        website_uri=source.website_uri,
        has_website=False,
        maps_url=source.maps_url,
        email_status="draft",
    )


async def _save_leads(db, leads: list[Lead]) -> int:
    if not leads:
        return 0
    try:
        async with db.begin_nested():
            db.add_all(leads)
    except IntegrityError:
        logger.warning("Batch insert hit a duplicate place id; saving one by one")
    else:
        await db.commit()
        return len(leads)

    saved = 0
    for source in leads:
        try:
            async with db.begin_nested():
                db.add(_copy_lead(source))
        except IntegrityError:
            continue
        saved += 1
    await db.commit()
    return saved


async def _mark_failed(campaign_id: int, message: str):
    try:
        async with async_session() as db:
            result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
            campaign = result.scalar_one_or_none()
            if not campaign:
                return
            if campaign.status in (CampaignStatus.PENDING.value, CampaignStatus.RUNNING.value):
                campaign.status = CampaignStatus.FAILED.value
                campaign.status_detail = message[:4000]
                await db.commit()
    except Exception:
        logger.exception("Could not record failure for campaign %s", campaign_id)


async def _execute(campaign_id: int, req):
    async with async_session() as db:
        result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if not campaign:
            return

        campaign.status = CampaignStatus.RUNNING.value
        await db.commit()

        if not GOOGLE_MAPS_API_KEY:
            campaign.status = CampaignStatus.FAILED.value
            campaign.status_detail = "GOOGLE_MAPS_API_KEY is not set on the server."
            await db.commit()
            return

        radius = min(int(req.radius or 10000), MAX_RADIUS_METERS)
        timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            client = PlacesClient(session, GOOGLE_MAPS_API_KEY)
            geocoded = None
            if req.lat is None or req.lng is None:
                geocoded = await client.geocode(req.location)
            origin, origin_error = resolve_origin(req.lat, req.lng, geocoded)
            if origin_error or origin is None:
                campaign.status = CampaignStatus.FAILED.value
                campaign.status_detail = origin_error or "Could not find that location."
                await db.commit()
                return

            lat, lng, area_label = origin
            campaign.lat = lat
            campaign.lng = lng
            await db.commit()

            text_query = f"{req.query} in {req.location}"
            bounds = circle_bounds(lat, lng, radius)

            async def search_cell(cell):
                return await client.search_cell(text_query, cell, req.min_rating)

            found, errors, _used, truncated = await walk_area(search_cell, bounds)

            existing = await db.execute(select(Lead.place_id))
            seen_ids = {row[0] for row in existing if row[0]}

            detail_ids = []
            seen_for_details = set(seen_ids)
            for place in found:
                pid = normalize_place_id(place)
                if not pid or pid in seen_for_details:
                    continue
                seen_for_details.add(pid)
                if place.get("businessStatus") == "CLOSED_PERMANENTLY":
                    continue
                plat, plng = place_location(place)
                if not inside_circle(plat, plng, lat, lng, radius):
                    continue
                if has_real_website(place.get("websiteUri")):
                    continue
                detail_ids.append(pid)

            skipped_for_cap = set(detail_ids[MAX_DETAIL_LOOKUPS:])
            to_check = detail_ids[:MAX_DETAIL_LOOKUPS]
            details_by_id, fatal, detail_error = await fetch_details_map(client, to_check)
            details_note = None
            details_available = True
            if fatal:
                details_available = False
                details_by_id = {}
                skipped_for_cap = set()
                details_note = (
                    "Place Details could not be used, so websites were checked from search results only. "
                    f"Google said: {fatal[:180]}"
                )
                logger.error("Place Details unavailable for campaign %s: %s", campaign_id, fatal[:300])
            elif detail_error:
                details_note = f"Some website checks failed. Last error: {detail_error[:180]}"

            stats = select_leads(
                found,
                details_by_id,
                seen_ids=seen_ids,
                min_rating=req.min_rating,
                min_reviews=getattr(req, "min_reviews", None),
                max_reviews=getattr(req, "max_reviews", None),
                center=(lat, lng),
                radius_m=radius,
                details_available=details_available,
                skipped_for_cap=skipped_for_cap,
            )
            leads = [lead_from_place(campaign_id, place) for place in stats.kept]
            saved = await _save_leads(db, leads)

            campaign.total_leads = saved
            campaign.status_detail = summarize_search(
                saved, stats, errors, truncated, area_label or req.location, details_note
            )
            if not found and errors:
                campaign.status = CampaignStatus.FAILED.value
                logger.error("Campaign %s failed: %s", campaign_id, campaign.status_detail)
            else:
                campaign.status = CampaignStatus.COMPLETED.value
                logger.info("Campaign %s finished: %s", campaign_id, campaign.status_detail)
            await db.commit()


async def run_grid_search(campaign_id: int, req):
    try:
        await _execute(campaign_id, req)
    except Exception as exc:
        logger.exception("Campaign %s crashed", campaign_id)
        await _mark_failed(campaign_id, f"Search stopped: {exc}"[:500])
    try:
        await generate_emails_for_campaign(campaign_id)
    except Exception:
        logger.exception("Draft generation failed for campaign %s", campaign_id)
