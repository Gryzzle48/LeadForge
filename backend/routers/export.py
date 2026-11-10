from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from ..database import get_session
from ..workers.sheet_exporter import export_to_sheets
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
        sheet_url = await export_to_sheets(campaign_id, db)
        return {"sheet_url": sheet_url}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
