from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from ..config import MAX_RESULTS_PER_QUERY
from ..database import get_session
from ..models.campaign import Campaign, CampaignStatus
from ..workers.grid_search import run_grid_search
from ..auth import client_ip_key

router = APIRouter()
limiter = Limiter(key_func=client_ip_key)


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=255)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    country: str = Field(default="United States", max_length=80)
    # Kept for compatibility with older clients that sent "location".
    location: str | None = Field(default=None, max_length=255)
    max_results: int = Field(default=100, ge=1, le=MAX_RESULTS_PER_QUERY)
    lat: float | None = None
    lng: float | None = None
    radius: int = Field(default=50000, ge=100, le=50000)
    min_rating: float | None = Field(default=None, ge=1, le=5)

    @model_validator(mode="before")
    @classmethod
    def normalize_location(cls, values):
        if not isinstance(values, dict):
            return values

        city = values.get("city")
        state = values.get("state")
        location = values.get("location")

        if (not city or not state) and location:
            parts = [part.strip() for part in str(location).split(",") if part.strip()]
            if parts:
                values.setdefault("city", parts[0])
            if len(parts) > 1:
                values.setdefault("state", parts[1])

        if not values.get("city") and not values.get("location"):
            raise ValueError("city is required")
        if not values.get("state") and not values.get("location"):
            raise ValueError("state is required")

        if values.get("city") and values.get("state"):
            values["location"] = ", ".join(
                part for part in [values["city"], values["state"], values.get("country", "United States")] if part
            )
        return values


@router.post("/search")
@limiter.limit("5/minute")
async def create_search(
    req: SearchRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
):
    campaign = Campaign(
        query=req.query.strip(),
        location=req.location or ", ".join(part for part in [req.city, req.state, req.country] if part),
        country=req.country,
        city=req.city,
        state=req.state,
        max_results=req.max_results,
        lat=req.lat,
        lng=req.lng,
        radius=req.radius,
        min_rating=req.min_rating,
        status=CampaignStatus.PENDING.value,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    background_tasks.add_task(run_grid_search, campaign.id, req, db)

    return {"campaign_id": campaign.id, "status": campaign.status}


@router.get("/campaigns")
async def list_campaigns(db: AsyncSession = Depends(get_session)):
    from sqlalchemy import select
    result = await db.execute(select(Campaign).order_by(Campaign.created_at.desc()).limit(50))
    return [campaign.to_dict() for campaign in result.scalars().all()]


@router.get("/search/{campaign_id}")
async def get_search_status(campaign_id: int, db: AsyncSession = Depends(get_session)):
    from sqlalchemy import select
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign.to_dict()
