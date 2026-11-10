from fastapi import APIRouter, Depends, Query, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from slowapi import Limiter
from ..database import get_session
from ..models.lead import Lead
from ..workers.email_writer import generate_email, load_templates
from ..models.campaign import Campaign
from ..auth import client_ip_key

router = APIRouter()
limiter = Limiter(key_func=client_ip_key)

class LeadUpdate(BaseModel):
    email: str | None = None
    email_subject: str | None = None
    email_body: str | None = None
    angle_used: str | None = None
    email_status: str | None = None

    @field_validator("email_status")
    @classmethod
    def validate_status(cls, v):
        if v is not None and v not in ("draft", "generated", "sent", "failed"):
            raise ValueError("email_status must be one of: draft, generated, sent, failed")
        return v

    @field_validator("email", "email_subject", "email_body", "angle_used")
    @classmethod
    def limit_text(cls, value):
        if value is None:
            return value
        if len(value) > 20000:
            raise ValueError("is too long")
        return value

@router.get("/campaigns/{campaign_id}/leads")
@limiter.limit("30/minute")
async def get_leads(
    request: Request,
    campaign_id: int,
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_session),
):
    stmt = select(Lead).where(Lead.campaign_id == campaign_id)
    if status:
        stmt = stmt.where(Lead.email_status == status)
    result = await db.execute(stmt)
    leads = result.scalars().all()
    return [l.to_dict() for l in leads]

@router.post("/leads/{lead_id}/regenerate-email")
@limiter.limit("10/minute")
async def regenerate_lead_email(
    request: Request,
    lead_id: int,
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    campaign_result = await db.execute(select(Campaign).where(Campaign.id == lead.campaign_id))
    campaign = campaign_result.scalar_one_or_none()
    location = campaign.location if campaign else "your area"

    templates = load_templates()
    subject, body, angle = generate_email(
        lead.name,
        lead.category or "",
        location,
        lead.rating or 0,
        lead.review_count or 0,
        templates,
    )
    lead.email_subject = subject
    lead.email_body = body
    lead.angle_used = angle
    lead.email_status = "draft"
    await db.commit()

    return lead.to_dict()

@router.patch("/leads/{lead_id}")
@limiter.limit("30/minute")
async def update_lead(
    request: Request,
    lead_id: int,
    data: LeadUpdate,
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(lead, key, value)
    await db.commit()
    return lead.to_dict()
