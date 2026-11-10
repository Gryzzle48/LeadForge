import html
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from slowapi import Limiter
from ..database import get_session
from ..models.lead import Lead
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
