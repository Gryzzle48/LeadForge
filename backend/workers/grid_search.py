import logging
import time

import aiohttp
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..config import (
    MAPS_SCRAPER_API_URL,
    MAPS_SCRAPER_POLL_SECONDS,
    NOMINATIM_USER_AGENT,
    SEARCH_EMPTY_TILES,
    SEARCH_MAX_SECONDS,
    SEARCH_MAX_TILES,
    SEARCH_TILE_DEPTH,
    SEARCH_TILE_KM,
    SEARCH_TILE_SECONDS,
    GOOGLE_SHEET_TAB_NAME,
    GOOGLE_SPREADSHEET_ID,
)
from ..database import async_session
from ..models.campaign import Campaign, CampaignStatus
from ..models.lead import Lead
from .city_search import (
    CoverProgress,
    GeocodeError,
    finish_reason,
    geocode_city,
    note_tile,
    plan_tiles,
    should_stop_before_tile,
    stop_message,
)
from .email_writer import generate_emails_for_campaign
from .gosom import GosomClient, GosomError, SearchStats, select_places, stable_place_id, summarize_search
from .sheet_exporter import SheetExportError, append_to_sheet, lead_fields

logger = logging.getLogger(__name__)


def _clip(value, limit: int) -> str:
    text = "" if value is None else str(value)
    return text[:limit]


def lead_from_record(campaign_id: int, record: dict) -> Lead:
    link = record.get("link") or ""
    if not link and record.get("place_id"):
        link = f"https://www.google.com/maps/search/?api=1&query_place_id={record['place_id']}"
    return Lead(
        campaign_id=campaign_id,
        place_id=_clip(record.get("place_id"), 255),
        name=_clip(record.get("title") or "Unknown", 255),
        address=_clip(record.get("address") or "", 500),
        phone=_clip(record.get("phone") or "", 50),
        email=_clip(record.get("email") or "", 255) or None,
        category=_clip(record.get("category") or "", 255),
        rating=record.get("review_rating"),
        review_count=record.get("review_count"),
        website_uri=_clip(record.get("website") or "", 500),
        has_website=False,
        maps_url=link,
        email_status="draft",
    )


def _copy_lead(source: Lead) -> Lead:
    return Lead(
        campaign_id=source.campaign_id,
        place_id=source.place_id,
        name=source.name,
        address=source.address,
        phone=source.phone,
        email=source.email,
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


async def _load_campaign(campaign_id: int):
    async with async_session() as db:
        result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
        return result.scalar_one_or_none()


async def _save_progress(campaign_id: int, progress: CoverProgress, **extra):
    async with async_session() as db:
        result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if not campaign:
            return None
        campaign.tiles_done = progress.tiles_done
        campaign.places_checked = progress.places_checked
        campaign.total_leads = progress.leads
        for key, value in extra.items():
            setattr(campaign, key, value)
        await db.commit()
        return campaign.cancel_requested


async def _append_saved_leads(campaign_id: int, place_ids: list[str]):
    if not GOOGLE_SPREADSHEET_ID or not place_ids:
        return None
    async with async_session() as db:
        result = await db.execute(
            select(Lead).where(Lead.campaign_id == campaign_id, Lead.place_id.in_(place_ids))
        )
        leads = result.scalars().all()
    if not leads:
        return None
    tab = GOOGLE_SHEET_TAB_NAME or "Leads"
    try:
        _url, note = await asyncio_to_thread(append_to_sheet, GOOGLE_SPREADSHEET_ID, tab, [lead_fields(lead) for lead in leads])
    except SheetExportError as exc:
        logger.warning("Sheet append failed for campaign %s: %s", campaign_id, exc.message)
        return exc.message
    except Exception as exc:
        logger.warning("Sheet append failed for campaign %s: %s", campaign_id, exc)
        return str(exc)[:300]
    async with async_session() as db:
        result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if campaign and not campaign.sheet_url:
            campaign.sheet_url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SPREADSHEET_ID}"[:500]
            await db.commit()
    return note


def asyncio_to_thread(func, *args):
    import asyncio
    return asyncio.to_thread(func, *args)


def _fresh_records(records: list[dict], seen: set[str]) -> list[dict]:
    fresh = []
    for record in records:
        keys = []
        place_id = stable_place_id(record)
        link = str(record.get("link") or "").strip().lower()
        if place_id:
            keys.append(place_id)
        if link:
            keys.append("link:" + link)
        if not keys or any(key in seen for key in keys):
            continue
        seen.update(keys)
        fresh.append(record)
    return fresh


async def _execute(campaign_id: int, req):
    async with async_session() as db:
        result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if not campaign:
            return
        campaign.status = CampaignStatus.RUNNING.value
        campaign.radius = None
        await db.commit()

    if not MAPS_SCRAPER_API_URL:
        await _finish(campaign_id, CampaignStatus.FAILED.value, CoverProgress(), (
            "MAPS_SCRAPER_API_URL is not set. Point it at the gosom scraper, "
            "for example http://localhost:8080."
        ))
        return

    keyword = f"{req.query} in {req.location}".strip()
    target = getattr(req, "target_leads", None)
    timeout = aiohttp.ClientTimeout(total=max(SEARCH_TILE_SECONDS + 60, 120), connect=10, sock_read=60)
    sheet_note = None
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            bounds = await geocode_city(session, req.location, NOMINATIM_USER_AGENT)
        except GeocodeError as exc:
            await _finish(campaign_id, CampaignStatus.FAILED.value, CoverProgress(), exc.message)
            return
        if bounds is None:
            await _finish(
                campaign_id,
                CampaignStatus.FAILED.value,
                CoverProgress(),
                f"Could not find {req.location} on OpenStreetMap. Check the city name and try again.",
            )
            return

        tiles, truncated = plan_tiles(bounds, SEARCH_TILE_KM, SEARCH_MAX_TILES)
        progress = CoverProgress()
        await _save_progress(
            campaign_id,
            progress,
            tiles_total=len(tiles),
            lat=bounds.lat,
            lng=bounds.lng,
            target_leads=target,
        )
        existing = await _existing_place_ids()
        seen = set(existing)
        client = GosomClient(session, MAPS_SCRAPER_API_URL)
        started = time.monotonic()
        reason = None
        for tile in tiles:
            cancelled = await _is_cancelled(campaign_id)
            early = should_stop_before_tile(
                progress,
                elapsed=time.monotonic() - started,
                max_seconds=SEARCH_MAX_SECONDS,
                max_tiles=SEARCH_MAX_TILES,
                cancelled=cancelled,
            )
            if early:
                reason = early
                break
            try:
                records = await _scrape_tile(client, keyword, tile)
            except GosomError as exc:
                logger.error("Campaign %s tile failed: %s", campaign_id, exc.message[:300])
                if progress.leads:
                    await _finish(
                        campaign_id,
                        CampaignStatus.COMPLETED.value,
                        progress,
                        f"{exc.message} Leads found so far were saved.",
                        bounds.label,
                    )
                    return
                await _finish(campaign_id, CampaignStatus.FAILED.value, progress, exc.message, bounds.label)
                return
            fresh = _fresh_records(records, seen)
            stats = select_places(
                fresh,
                seen_ids=set(),
                min_rating=req.min_rating,
                min_reviews=getattr(req, "min_reviews", None),
                max_reviews=getattr(req, "max_reviews", None),
                center=None,
                radius_m=0,
            )
            saved_records = stats.kept
            saved = await _persist_tile(campaign_id, saved_records)
            if saved:
                try:
                    await generate_emails_for_campaign(campaign_id)
                except Exception:
                    logger.exception("Draft generation failed for campaign %s", campaign_id)
                note = await _append_saved_leads(campaign_id, [record["place_id"] for record in saved_records])
                if note and "Skipped" not in str(note) and "Added" not in str(note):
                    sheet_note = note
            reason = note_tile(
                progress,
                new_places=len(fresh),
                new_leads=saved,
                checked=len(records),
                target=target,
                empty_limit=SEARCH_EMPTY_TILES,
                tiles_total=len(tiles),
            )
            await _save_progress(campaign_id, progress)
            if reason:
                break
        reason = finish_reason(reason or "tiles_done", truncated)
        message = summarize_search(progress.leads, SearchStats(), bounds.label, stop_message(reason))
        if sheet_note:
            message = f"{message} {sheet_note}"[:4000]
        status = CampaignStatus.CANCELLED.value if reason == "cancelled" else CampaignStatus.COMPLETED.value
        await _finish(campaign_id, status, progress, message, bounds.label)
        logger.info("Campaign %s finished: %s", campaign_id, message)


async def _existing_place_ids() -> set[str]:
    async with async_session() as db:
        result = await db.execute(select(Lead.place_id))
        return {row[0] for row in result if row[0]}


async def _is_cancelled(campaign_id: int) -> bool:
    campaign = await _load_campaign(campaign_id)
    if not campaign:
        return True
    return bool(campaign.cancel_requested) or campaign.status == CampaignStatus.CANCELLED.value


async def _scrape_tile(client: GosomClient, keyword: str, tile):
    job_id = await client.create_job(
        keyword,
        tile.radius_m,
        tile.lat,
        tile.lng,
        SEARCH_TILE_DEPTH,
        SEARCH_TILE_SECONDS,
    )
    payload = await client.wait_for_job(
        job_id,
        timeout_s=SEARCH_TILE_SECONDS + 45,
        poll_seconds=MAPS_SCRAPER_POLL_SECONDS,
    )
    return await client.fetch_results(job_id, payload)


async def _persist_tile(campaign_id: int, records: list[dict]) -> int:
    if not records:
        return 0
    async with async_session() as db:
        saved = await _save_leads(db, [lead_from_record(campaign_id, record) for record in records])
    return saved


async def _finish(campaign_id: int, status: str, progress: CoverProgress, message: str, label: str | None = None):
    async with async_session() as db:
        result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if not campaign:
            return
        campaign.status = status
        campaign.tiles_done = progress.tiles_done
        campaign.places_checked = progress.places_checked
        campaign.total_leads = progress.leads
        detail = message
        if label and label not in detail:
            detail = f"Area: {label}. {detail}"
        campaign.status_detail = detail[:4000]
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
