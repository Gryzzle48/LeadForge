import json
import base64
import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from google.oauth2 import service_account
from googleapiclient.discovery import build
from ..models.lead import Lead
from ..models.campaign import Campaign
from ..config import GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_SPREADSHEET_ID, GOOGLE_SHEET_TAB_NAME

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
HEADERS = ["Number", "Business Name", "Category", "Google Maps Link", "Contacts", "City", "State"]


def get_service():
    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        return None
    raw = GOOGLE_SERVICE_ACCOUNT_JSON.strip()
    try:
        info = json.loads(base64.b64decode(raw).decode("utf-8"))
    except Exception:
        info = json.loads(raw)
    credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def _tab_range(cell_range: str) -> str:
    return "'" + GOOGLE_SHEET_TAB_NAME.replace("'", "''") + "'!" + cell_range


def _normalize(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).casefold()


def _normalize_url(value: str | None) -> str:
    return (value or "").strip().rstrip("/").casefold()


def _contact_cell(lead: Lead) -> str:
    contacts = []
    if lead.phone:
        contacts.append("Phone: " + lead.phone)
    if lead.email:
        contacts.append("Email: " + lead.email)
    if lead.instagram_url:
        contacts.append("Instagram: " + lead.instagram_url)
    return "\n".join(contacts)


def _ensure_leads_tab(service, spreadsheet_id: str) -> None:
    metadata = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets.properties"
    ).execute()
    tabs = metadata.get("sheets", [])
    if any(sheet.get("properties", {}).get("title") == GOOGLE_SHEET_TAB_NAME for sheet in tabs):
        return
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": GOOGLE_SHEET_TAB_NAME}}}]},
    ).execute()


async def export_to_sheets(campaign_id: int, db: AsyncSession):
    if not GOOGLE_SPREADSHEET_ID:
        raise RuntimeError("Set GOOGLE_SPREADSHEET_ID to your permanent Google spreadsheet ID.")
    service = get_service()
    if not service:
        raise RuntimeError("Google service account is not configured.")

    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise ValueError("Campaign not found.")

    leads_result = await db.execute(
        select(Lead).where(Lead.campaign_id == campaign_id).order_by(Lead.id.asc())
    )
    leads = leads_result.scalars().all()

    _ensure_leads_tab(service, GOOGLE_SPREADSHEET_ID)
    values_api = service.spreadsheets().values()

    header_result = values_api.get(
        spreadsheetId=GOOGLE_SPREADSHEET_ID,
        range=_tab_range("A1:G1"),
    ).execute()
    existing_header = header_result.get("values", [])
    if not existing_header:
        values_api.update(
            spreadsheetId=GOOGLE_SPREADSHEET_ID,
            range=_tab_range("A1:G1"),
            valueInputOption="RAW",
            body={"values": [HEADERS]},
        ).execute()
    elif existing_header[0][:7] != HEADERS:
        raise RuntimeError(
            "The Leads tab headers do not match the expected layout: "
            + ", ".join(HEADERS)
        )

    existing_result = values_api.get(
        spreadsheetId=GOOGLE_SPREADSHEET_ID,
        range=_tab_range("A2:G"),
    ).execute()
    existing_rows = existing_result.get("values", [])

    existing_maps_links = set()
    legacy_business_keys = set()
    next_number = 1
    for row in existing_rows:
        padded = row + [""] * max(0, 7 - len(row))
        try:
            next_number = max(next_number, int(float(padded[0])) + 1)
        except (TypeError, ValueError):
            pass
        maps_link = _normalize_url(padded[3])
        if maps_link:
            existing_maps_links.add(maps_link)
        else:
            business_key = (
                _normalize(padded[1]),
                _normalize(padded[5]),
                _normalize(padded[6]),
            )
            if all(business_key):
                legacy_business_keys.add(business_key)

    rows = []
    for lead in leads:
        maps_link = (lead.google_maps_url or "").strip()
        if not maps_link and lead.place_id:
            maps_link = "https://www.google.com/maps/search/?api=1&query_place_id=" + lead.place_id

        maps_key = _normalize_url(maps_link)
        business_key = (
            _normalize(lead.name),
            _normalize(campaign.city),
            _normalize(campaign.state),
        )
        if maps_key and maps_key in existing_maps_links:
            continue
        if not maps_key and all(business_key) and business_key in legacy_business_keys:
            continue

        rows.append([
            next_number + len(rows),
            lead.name or "",
            lead.category or campaign.query or "",
            maps_link,
            _contact_cell(lead),
            campaign.city or "",
            campaign.state or "",
        ])
        if maps_key:
            existing_maps_links.add(maps_key)
        elif all(business_key):
            legacy_business_keys.add(business_key)

    if rows:
        values_api.append(
            spreadsheetId=GOOGLE_SPREADSHEET_ID,
            range=_tab_range("A:G"),
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()

    return "https://docs.google.com/spreadsheets/d/" + GOOGLE_SPREADSHEET_ID
