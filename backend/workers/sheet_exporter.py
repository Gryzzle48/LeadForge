import asyncio
import base64
import json
import logging
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_SHEET_SHARE_EMAIL
from ..models.campaign import Campaign
from ..models.lead import Lead

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

HEADERS = [
    "Name",
    "Category",
    "Address",
    "Phone",
    "Maps link",
    "Rating",
    "Reviews",
    "Website",
    "Email",
    "Subject",
    "Draft",
    "Status",
    "Notes",
]


class SheetExportError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def load_service_account_info(raw: str) -> dict:
    text = (raw or "").strip()
    if not text:
        raise SheetExportError(
            "Google Sheets is not configured. Set GOOGLE_SERVICE_ACCOUNT_JSON on the backend."
        )
    if os.path.isfile(text):
        with open(text, encoding="utf-8") as handle:
            info = json.load(handle)
    elif text.startswith("{"):
        try:
            info = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SheetExportError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc
    else:
        try:
            info = json.loads(base64.b64decode(text, validate=True).decode("utf-8"))
        except Exception as exc:
            raise SheetExportError(
                "GOOGLE_SERVICE_ACCOUNT_JSON must be the service-account JSON, "
                "that same JSON encoded as base64, or a path to the JSON file."
            ) from exc
    if not isinstance(info, dict) or "client_email" not in info:
        raise SheetExportError("GOOGLE_SERVICE_ACCOUNT_JSON does not look like a Google service account key.")
    return info


def maps_url_for(place_id: str | None, maps_url: str | None = None) -> str:
    if maps_url:
        return maps_url
    if not place_id:
        return ""
    return f"https://www.google.com/maps/search/?api=1&query_place_id={place_id}"


def lead_row(lead) -> list:
    rating = getattr(lead, "rating", None)
    reviews = getattr(lead, "review_count", None)
    return [
        lead.name or "",
        lead.category or "",
        lead.address or "",
        lead.phone or "",
        maps_url_for(getattr(lead, "place_id", None), getattr(lead, "maps_url", None)),
        "" if rating is None else rating,
        "" if reviews is None else reviews,
        getattr(lead, "website_uri", None) or "",
        lead.email or "",
        lead.email_subject or "",
        lead.email_body or "",
        lead.email_status or "draft",
        "",
    ]


def _share(drive, file_id: str, owner_email: str) -> str | None:
    """Return a warning when the sheet may be hard for the owner to open."""
    if GOOGLE_SHEET_SHARE_EMAIL:
        drive.permissions().create(
            fileId=file_id,
            body={"type": "user", "role": "writer", "emailAddress": GOOGLE_SHEET_SHARE_EMAIL},
            sendNotificationEmail=False,
            fields="id",
        ).execute()
        return None
    drive.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "writer"},
        fields="id",
    ).execute()
    return (
        "This sheet is editable by anyone with the link. "
        "Set GOOGLE_SHEET_SHARE_EMAIL on the backend to share it only with you. "
        f"It is owned by {owner_email}."
    )


def create_sheet(title: str, rows: list[list]) -> tuple[str, str | None]:
    info = load_service_account_info(GOOGLE_SERVICE_ACCOUNT_JSON)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)

    created = sheets.spreadsheets().create(body={
        "properties": {"title": title[:100]},
        "sheets": [{"properties": {"title": "Leads"}}],
    }).execute()
    spreadsheet_id = created["spreadsheetId"]
    sheet_gid = created["sheets"][0]["properties"]["sheetId"]

    sheets.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="Leads!A1",
        valueInputOption="RAW",
        body={"values": [HEADERS] + rows},
    ).execute()

    try:
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_gid,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            }]},
        ).execute()
    except Exception:
        logger.warning("Could not freeze the header row", exc_info=True)

    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
    owner = info.get("client_email") or "the service account"
    try:
        warning = _share(drive, spreadsheet_id, owner)
    except Exception as exc:
        logger.exception("Could not share spreadsheet %s", spreadsheet_id)
        warning = (
            "The sheet was created, but it could not be shared, so the link may ask for access. "
            f"In Google Drive, as {owner}, share it with your Google account. "
            f"Google said: {exc}"
        )[:500]
    return url, warning


async def export_to_sheets(campaign_id: int, db: AsyncSession) -> dict:
    if not (GOOGLE_SERVICE_ACCOUNT_JSON or "").strip():
        raise SheetExportError(
            "Google Sheets is not configured. Set GOOGLE_SERVICE_ACCOUNT_JSON on the backend."
        )

    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise SheetExportError("Campaign not found", status_code=404)

    leads_result = await db.execute(select(Lead).where(Lead.campaign_id == campaign_id))
    leads = leads_result.scalars().all()
    rows = [lead_row(lead) for lead in leads]
    title = f"LeadForge - {campaign.query} in {campaign.location}"

    try:
        url, warning = await asyncio.to_thread(create_sheet, title, rows)
    except SheetExportError:
        raise
    except Exception as exc:
        logger.exception("Sheet export failed for campaign %s", campaign_id)
        raise SheetExportError(f"Google Sheets rejected the export: {exc}", status_code=502) from exc

    campaign.sheet_url = url[:500]
    await db.commit()
    return {"sheet_url": url, "warning": warning}
