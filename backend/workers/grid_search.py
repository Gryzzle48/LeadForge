import logging

import aiohttp
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..config import (
    MAPS_SCRAPER_API_URL,
    MAPS_SCRAPER_DEPTH,
    MAPS_SCRAPER_MAX_TIME_SECONDS,
    MAPS_SCRAPER_POLL_SECONDS,
)
from ..database import async_session
from ..models.campaign import Campaign, CampaignStatus
from ..models.lead import Lead
from .email_writer import generate_emails_for_campaign
from .gosom import GosomClient, GosomError, select_places, summarize_search

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


async def _execute(campaign_id: int, req):
    async with async_session() as db:
        result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if not campaign:
            return

        campaign.status = CampaignStatus.RUNNING.value
        await db.commit()

        if not MAPS_SCRAPER_API_URL:
            campaign.status = CampaignStatus.FAILED.value
            campaign.status_detail = (
                "MAPS_SCRAPER_API_URL is not set. Point it at the gosom scraper, "
                "for example http://localhost:8080."
            )
            await db.commit()
            return

        keyword = f"{req.query} in {req.location}".strip()
        radius = min(int(req.radius or 10000), 50000)
        timeout = aiohttp.ClientTimeout(total=120, connect=10, sock_read=60)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                client = GosomClient(session, MAPS_SCRAPER_API_URL)
                job_id = await client.create_job(
                    keyword,
                    radius,
                    req.lat,
                    req.lng,
                    MAPS_SCRAPER_DEPTH,
                    MAPS_SCRAPER_MAX_TIME_SECONDS,
                )
                logger.info("Campaign %s started scraper job %s", campaign_id, job_id)
                payload = await client.wait_for_job(
                    job_id,
                    timeout_s=MAPS_SCRAPER_MAX_TIME_SECONDS + 90,
                    poll_seconds=MAPS_SCRAPER_POLL_SECONDS,
                )
                records = await client.fetch_results(job_id, payload)
        except GosomError as exc:
            campaign.status = CampaignStatus.FAILED.value
            campaign.status_detail = exc.message[:4000]
            await db.commit()
            logger.error("Campaign %s scraper failed: %s", campaign_id, exc.message[:300])
            return

        existing = await db.execute(select(Lead.place_id))
        seen_ids = {row[0] for row in existing if row[0]}
        center = (req.lat, req.lng) if req.lat is not None and req.lng is not None else None
        stats = select_places(
            records,
            seen_ids=seen_ids,
            min_rating=req.min_rating,
            min_reviews=getattr(req, "min_reviews", None),
            max_reviews=getattr(req, "max_reviews", None),
            center=center,
            radius_m=radius,
        )
        saved = await _save_leads(db, [lead_from_record(campaign_id, record) for record in stats.kept])
        note = None
        if not records:
            note = "The scraper finished and returned no businesses. Try a broader category or a larger radius."
        campaign.total_leads = saved
        campaign.status = CampaignStatus.COMPLETED.value
        campaign.status_detail = summarize_search(saved, stats, req.location, note)
        await db.commit()
        logger.info("Campaign %s finished: %s", campaign_id, campaign.status_detail)


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
