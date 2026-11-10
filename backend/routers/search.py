from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from ..database import get_session
from ..models.campaign import Campaign, CampaignStatus
from ..workers.grid_search import run_grid_search
from ..auth import client_ip_key

router = APIRouter()
limiter = Limiter(key_func=client_ip_key)

class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    location: str = Field(min_length=1, max_length=200)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    min_rating: float | None = Field(default=None, ge=0, le=5)
    min_reviews: int | None = Field(default=None, ge=0, le=1_000_000)
    max_reviews: int | None = Field(default=None, ge=0, le=1_000_000)
    target_leads: int | None = Field(default=None, ge=1, le=5000)

    @field_validator("query", "location")
    @classmethod
    def strip_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("must not be blank")
        return text

    @model_validator(mode="after")
    def reviews_in_order(self):
        if (
            self.min_reviews is not None
            and self.max_reviews is not None
            and self.min_reviews > self.max_reviews
        ):
            raise ValueError("min_reviews cannot be greater than max_reviews")
        return self

@router.post("/search")
@limiter.limit("5/minute")
async def create_search(
    req: SearchRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
):
    campaign = Campaign(
        query=req.query,
        location=req.location,
        lat=req.lat,
        lng=req.lng,
        radius=None,
        min_rating=req.min_rating,
        min_reviews=req.min_reviews,
        max_reviews=req.max_reviews,
        target_leads=req.target_leads,
        status=CampaignStatus.PENDING.value,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    background_tasks.add_task(run_grid_search, campaign.id, req)

    return {"campaign_id": campaign.id, "status": campaign.status}

@router.get("/campaigns")
async def list_campaigns(
    db: AsyncSession = Depends(get_session),
):
    from sqlalchemy import select
    result = await db.execute(
        select(Campaign).order_by(Campaign.created_at.desc()).limit(50)
    )
    campaigns = result.scalars().all()
    return [c.to_dict() for c in campaigns]

@router.post("/search/{campaign_id}/cancel")
async def cancel_search(
    campaign_id: int,
    db: AsyncSession = Depends(get_session),
):
    from sqlalchemy import select
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.status in (CampaignStatus.PENDING.value, CampaignStatus.RUNNING.value):
        campaign.cancel_requested = True
        await db.commit()
    return campaign.to_dict()

@router.get("/search/{campaign_id}")
async def get_search_status(
    campaign_id: int,
    db: AsyncSession = Depends(get_session),
):
    from sqlalchemy import select
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign.to_dict()
