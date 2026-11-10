from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from ..database import get_session
from ..workers.sheet_exporter import SheetExportError, export_to_sheets
from ..auth import client_ip_key

router = APIRouter()
limiter = Limiter(key_func=client_ip_key)

@router.post("/campaigns/{campaign_id}/export")
@limiter.limit("10/minute")
async def export_campaign(
    request: Request,
    campaign_id: int,
    db: AsyncSession = Depends(get_session),
):
    try:
        return await export_to_sheets(campaign_id, db)
    except SheetExportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
