import asyncio
import csv
import hashlib
import io
import json
import logging

import aiohttp
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import MAPS_SCRAPER_API_URL, MAX_RESULTS_PER_QUERY
from ..database import async_session
from ..models.campaign import Campaign, CampaignStatus
from ..models.lead import Lead

logger = logging.getLogger(__name__)

SCRAPER_TIMEOUT_SECONDS = 360
SCRAPER_POLL_INTERVAL_SECONDS = 5


def _split_emails(raw: str | None) -> str | None:
    if not raw:
        return None
    for candidate in raw.replace(";", ",").split(","):
        value = candidate.strip().strip(" .;")
        if "@" in value and "." in value.rsplit("@", 1)[-1]:
            return value[:255]
    return None


def parse_scraper_csv(content: str) -> list[dict]:
    """Parse the CSV emitted by gosom/google-maps-scraper."""
    reader = csv.DictReader(io.StringIO(content))
    rows: list[dict] = []
    for row in reader:
        name = (row.get("title") or row.get("name") or "").strip()
        if not name:
            continue
        address = (row.get("address") or "").strip()
        place_id = (row.get("place_id") or row.get("cid") or row.get("data_id") or "").strip()
        if not place_id:
            stable_key = "|".join((name.casefold(), address.casefold()))
            place_id = "gosom:" + hashlib.sha256(stable_key.encode("utf-8")).hexdigest()

        maps_url = (row.get("link") or "").strip()
        if not maps_url and not place_id.startswith("gosom:"):
            maps_url = (
                "https://www.google.com/maps/search/?api=1&query_place_id="
                + place_id
            )

        website = (row.get("website") or row.get("web_site") or "").strip()
        category = (row.get("category") or "").strip()
        phone = (row.get("phone") or "").strip()
        rating_raw = (row.get("review_rating") or "").strip()
        review_count_raw = (row.get("review_count") or "").strip()
        try:
            rating = float(rating_raw) if rating_raw else None
        except ValueError:
            rating = None
        try:
            review_count = int(float(review_count_raw)) if review_count_raw else None
        except ValueError:
            review_count = None

        rows.append({
            "place_id": place_id,
            "name": name,
            "address": address,
            "phone": phone or None,
            "email": _split_emails(row.get("emails")),
            "instagram_url": None,
            "google_maps_url": maps_url or None,
            "category": category or None,
            "rating": rating,
            "review_count": review_count,
            "website_uri": website or None,
        })
    return rows


async def _run_scraper_query(
    session: aiohttp.ClientSession,
    query_name: str,
    keyword: str,
) -> list[dict]:
    # The requested count is the number of qualifying leads to save, not the
    # number of raw Maps results. Fetch the deepest candidate set so filtering
    # for missing websites and global deduplication can still fill the target.
    # gosom's local web runner expects max_time in seconds. Its API converts
    # that value to a Go duration internally.
    depth = 10
    payload = {
        "Name": query_name,
        "keywords": [keyword],
        "lang": "en",
        "zoom": 15,
        "depth": depth,
        "email": False,
        "fast_mode": False,
        "extra_reviews": False,
        "radius": 50000,
        "max_time": 300,
    }

    async with session.post(
        f"{MAPS_SCRAPER_API_URL}/api/v1/jobs",
        json=payload,
    ) as response:
        body = await response.text()
        if response.status not in (200, 201, 202):
            raise RuntimeError(
                f"Local Maps scraper rejected the job (HTTP {response.status}): {body[:300]}"
            )
        try:
            created = json.loads(body)
        except Exception as exc:
            raise RuntimeError("Local Maps scraper returned an invalid job response.") from exc

    job_id = str(created.get("id") or created.get("ID") or "").strip()
    if not job_id:
        raise RuntimeError("Local Maps scraper did not return a job ID.")

    loop = asyncio.get_running_loop()
    deadline = loop.time() + SCRAPER_TIMEOUT_SECONDS
    status = "pending"
    last_error = ""

    while loop.time() < deadline:
        async with session.get(f"{MAPS_SCRAPER_API_URL}/api/v1/jobs/{job_id}") as response:
            body = await response.text()
            if response.status != 200:
                raise RuntimeError(
                    f"Could not read local Maps scraper job (HTTP {response.status}): {body[:300]}"
                )
            try:
                job = json.loads(body)
            except Exception as exc:
                raise RuntimeError("Local Maps scraper returned invalid job status.") from exc

        status = str(job.get("Status") or job.get("status") or "").lower()
        last_error = str(job.get("Error") or job.get("error") or "")
        if status in {"ok", "completed", "success"}:
            break
        if status in {"failed", "error"}:
            raise RuntimeError(last_error or "Local Maps scraper job failed.")
        await asyncio.sleep(SCRAPER_POLL_INTERVAL_SECONDS)
    else:
        raise RuntimeError(
            "Local Maps scraper timed out. Check its Docker logs and try a smaller search."
        )

    async with session.get(
        f"{MAPS_SCRAPER_API_URL}/api/v1/jobs/{job_id}/download"
    ) as response:
        if response.status != 200:
            body = await response.text()
            raise RuntimeError(
                f"Could not download Maps scraper results (HTTP {response.status}): {body[:300]}"
            )
        csv_content = await response.text()

    return parse_scraper_csv(csv_content)


async def run_grid_search(campaign_id: int, req, _db_session: AsyncSession):
    """Scrape a broad candidate set and save up to the requested qualifying lead count."""
    async with async_session() as db:
        result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if not campaign:
            return

        campaign.status = CampaignStatus.RUNNING.value
        await db.commit()

        try:
            max_results = min(int(req.max_results), MAX_RESULTS_PER_QUERY)
            keyword = f"{req.query} in {campaign.city}, {campaign.state}, United States"
            timeout = aiohttp.ClientTimeout(
                total=SCRAPER_TIMEOUT_SECONDS + 30,
                connect=10,
                sock_read=SCRAPER_TIMEOUT_SECONDS + 30,
            )
            async with aiohttp.ClientSession(timeout=timeout) as session:
                scraped_rows = await _run_scraper_query(
                    session,
                    query_name=f"{req.query} - {campaign.city}, {campaign.state}",
                    keyword=keyword,
                )

            existing_result = await db.execute(select(Lead.place_id))
            seen_place_ids = {row[0] for row in existing_result if row[0]}
            added_count = 0

            for place in scraped_rows:
                if added_count >= max_results:
                    break

                # A business with a website listed on its Maps profile is not
                # part of this workflow. We still parse the field to filter it.
                if place.get("website_uri"):
                    continue

                place_id = place["place_id"]
                if place_id in seen_place_ids:
                    continue
                seen_place_ids.add(place_id)

                rating = place.get("rating")
                if req.min_rating is not None and rating is not None and rating < req.min_rating:
                    continue

                statement = pg_insert(Lead).values(
                    campaign_id=campaign_id,
                    place_id=place_id,
                    name=place["name"],
                    address=place.get("address") or "",
                    phone=place.get("phone"),
                    email=place.get("email"),
                    instagram_url=None,
                    google_maps_url=place.get("google_maps_url"),
                    category=place.get("category") or campaign.query,
                    rating=rating,
                    review_count=place.get("review_count"),
                    website_uri=None,
                    has_website=False,
                    email_status="no_email" if not place.get("email") else "draft",
                ).on_conflict_do_nothing(index_elements=[Lead.place_id])
                insert_result = await db.execute(statement)
                if insert_result.rowcount:
                    added_count += 1

            campaign.total_leads = added_count
            campaign.status = CampaignStatus.COMPLETED.value
            await db.commit()
            logger.info(
                "Campaign %s completed with %s new leads from local Maps scraper",
                campaign_id,
                added_count,
            )
        except Exception as exc:
            logger.exception("Local Maps scraper failed for campaign %s", campaign_id)
            # Clear any failed SQL transaction before persisting the campaign
            # failure state, so the dashboard does not remain stuck on RUNNING.
            await db.rollback()
            failed_result = await db.execute(
                select(Campaign).where(Campaign.id == campaign_id)
            )
            failed_campaign = failed_result.scalar_one_or_none()
            if failed_campaign:
                failed_campaign.status = CampaignStatus.FAILED.value
                await db.commit()
            logger.error("Campaign %s failed: %s", campaign_id, exc)
