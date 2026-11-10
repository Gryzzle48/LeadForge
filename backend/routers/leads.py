import html
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from slowapi import Limiter
from ..database import get_session
from ..models.lead import Lead
from ..models.campaign import Campaign
from ..workers.contact_finder import find_public_contacts
from ..auth import client_ip_key

router = APIRouter()
limiter = Limiter(key_func=client_ip_key)


def sanitize(value: str | None) -> str | None:
    return html.escape(value) if value else value


class LeadUpdate(BaseModel):
    phone: str | None = None
    email: str | None = None
    instagram_url: str | None = None

    @field_validator("phone", "email", "instagram_url")
    @classmethod
    def sanitize_contact_fields(cls, value):
        return sanitize(value)


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
    return [lead.to_dict() for lead in result.scalars().all()]


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
    await db.refresh(lead)
    return lead.to_dict()


@router.post("/leads/{lead_id}/enrich")
@limiter.limit("10/minute")
async def enrich_lead(
    request: Request,
    lead_id: int,
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Avoid spending an external search when both requested fields are present.
    if lead.email and lead.instagram_url:
        result_data = lead.to_dict()
        result_data["contact_sources"] = []
        return result_data

    campaign_result = await db.execute(
        select(Campaign).where(Campaign.id == lead.campaign_id)
    )
    campaign = campaign_result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    try:
        contacts = await find_public_contacts(
            business_name=lead.name,
            city=campaign.city,
            state=campaign.state,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Never overwrite contact information already present in the lead record.
    if not lead.email and contacts.get("email"):
        lead.email = contacts["email"]
    if not lead.instagram_url and contacts.get("instagram_url"):
        lead.instagram_url = contacts["instagram_url"]

    await db.commit()
    await db.refresh(lead)
    result_data = lead.to_dict()
    result_data["contact_sources"] = contacts.get("sources", [])
    return result_data
