import asyncio
import base64
import json
import logging
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import (
    GOOGLE_SERVICE_ACCOUNT_JSON,
    GOOGLE_SHEET_SHARE_EMAIL,
    GOOGLE_SHEET_TAB_NAME,
    GOOGLE_SPREADSHEET_ID,
)
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
    "Place ID",
]

# Header label -> field on a lead record. Extra labels cover older sheets.
_HEADER_FIELDS = {
    "name": "name",
    "business": "name",
    "category": "category",
    "address": "address",
    "phone": "phone",
    "maps link": "maps",
    "map": "maps",
    "maps": "maps",
    "rating": "rating",
    "reviews": "reviews",
    "review count": "reviews",
    "website": "website",
    "email": "email",
    "subject": "subject",
    "draft": "draft",
    "body": "draft",
    "status": "status",
    "notes": "notes",
    "place id": "place_id",
    "place_id": "place_id",
}


class SheetExportError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def service_account_path_candidates(text: str) -> list[str]:
    """Paths to try for a service-account file.

    ./secrets/service-account.json works on the host and inside Docker, where
    that folder is mounted at /app/secrets and /secrets.
    """
    normalized = text.replace("\\", "/").strip()
    names = [text, normalized, os.path.expanduser(normalized)]
    base = os.path.basename(normalized)
    if base and base not in {".", ".."}:
        names.extend([
            os.path.join("/app/secrets", base),
            os.path.join("/secrets", base),
            os.path.join(os.getcwd(), "secrets", base),
        ])
    found = []
    seen = set()
    for name in names:
        if not name or name in seen:
            continue
        seen.add(name)
        found.append(name)
    return found


def load_service_account_info(raw: str) -> dict:
    text = (raw or "").strip()
    if not text:
        raise SheetExportError(
            "Google Sheets is not configured. Set GOOGLE_SERVICE_ACCOUNT_JSON on the backend."
        )
    if text.startswith("{"):
        try:
            info = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SheetExportError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc
    else:
        path = next((item for item in service_account_path_candidates(text) if os.path.isfile(item)), None)
        if path:
            with open(path, encoding="utf-8") as handle:
                info = json.load(handle)
        else:
            try:
                info = json.loads(base64.b64decode(text, validate=True).decode("utf-8"))
            except Exception as exc:
                raise SheetExportError(
                    "GOOGLE_SERVICE_ACCOUNT_JSON must be the service-account JSON, "
                    "that JSON encoded as base64, or a path such as ./secrets/service-account.json."
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


def lead_fields(lead) -> dict:
    rating = getattr(lead, "rating", None)
    reviews = getattr(lead, "review_count", None)
    return {
        "name": lead.name or "",
        "category": lead.category or "",
        "address": lead.address or "",
        "phone": lead.phone or "",
        "maps": maps_url_for(getattr(lead, "place_id", None), getattr(lead, "maps_url", None)),
        "rating": "" if rating is None else rating,
        "reviews": "" if reviews is None else reviews,
        "website": getattr(lead, "website_uri", None) or "",
        "email": lead.email or "",
        "subject": lead.email_subject or "",
        "draft": lead.email_body or "",
        "status": lead.email_status or "draft",
        "notes": "",
        "place_id": getattr(lead, "place_id", None) or "",
    }


def lead_row(lead) -> list:
    fields = lead_fields(lead)
    return [fields[_HEADER_FIELDS[header.lower()]] for header in HEADERS]


def _header_field(cell) -> str | None:
    return _HEADER_FIELDS.get(str(cell or "").strip().lower())


def _looks_like_header(row) -> bool:
    return any(_header_field(cell) for cell in row)


def _extend_header(header: list[str]) -> list[str]:
    present = {_header_field(cell) for cell in header}
    extended = list(header)
    for label in HEADERS:
        field = _HEADER_FIELDS[label.lower()]
        if field not in present:
            extended.append(label)
            present.add(field)
    return extended


def project_row(header: list[str], fields: dict) -> list:
    row = []
    for cell in header:
        field = _header_field(cell)
        row.append("" if field is None else fields.get(field, ""))
    return row


def _identity_keys(header: list[str], row: list) -> set[str]:
    values = {}
    for cell, value in zip(header, row):
        field = _header_field(cell)
        if field:
            values[field] = str(value or "").strip().lower()
    keys = set()
    if values.get("place_id"):
        keys.add("id:" + values["place_id"])
    if values.get("maps"):
        keys.add("map:" + values["maps"])
    if values.get("name") and values.get("phone"):
        keys.add(f"np:{values['name']}|{values['phone']}")
    return keys


def tab_range(tab: str, a1: str) -> str:
    safe = (tab or "Leads").replace("'", "''")
    return f"'{safe}'!{a1}"


def plan_append(existing_values: list[list], field_rows: list[dict], tab: str) -> tuple[list[str], list[list], int]:
    """Return the header, new data rows, and how many leads were already present.

    An empty sheet gets the standard header. A sheet that already has a header
    keeps that header and gains any missing columns. Rows already identified by
    place id, Maps link, or name plus phone are not returned.
    """
    if not existing_values:
        header = list(HEADERS)
        return header, [project_row(header, fields) for fields in field_rows], 0

    first = [str(cell) for cell in existing_values[0]]
    if not _looks_like_header(first):
        raise SheetExportError(
            f"Tab {tab!r} has rows but no header. Add a header row "
            "(Name, Category, Address, Phone, Maps link, ...) or choose an empty tab."
        )

    header = _extend_header(first)
    seen = set()
    for row in existing_values[1:]:
        seen.update(_identity_keys(header, row))

    fresh = []
    skipped = 0
    for fields in field_rows:
        row = project_row(header, fields)
        keys = _identity_keys(header, row)
        if keys and keys & seen:
            skipped += 1
            continue
        seen.update(keys)
        fresh.append(row)
    return header, fresh, skipped


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


def _sheets_client(scopes: list[str]):
    info = load_service_account_info(GOOGLE_SERVICE_ACCOUNT_JSON)
    creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return info, sheets


def append_to_sheet(spreadsheet_id: str, tab: str, field_rows: list[dict]) -> tuple[str, str | None]:
    info, sheets = _sheets_client(["https://www.googleapis.com/auth/spreadsheets"])
    owner = info.get("client_email") or "the service account"
    try:
        meta = sheets.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="sheets.properties.title",
        ).execute()
    except Exception as exc:
        raise SheetExportError(
            f"Could not open spreadsheet {spreadsheet_id}. Share it with {owner} as an editor. "
            f"Google said: {exc}"
        ) from exc

    titles = [sheet["properties"]["title"] for sheet in meta.get("sheets", [])]
    if tab not in titles:
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": tab}}}]},
        ).execute()

    existing = sheets.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=tab_range(tab, "A:Z"),
    ).execute()
    values = existing.get("values") or []
    previous_header = [str(cell) for cell in values[0]] if values else []
    header, fresh, skipped = plan_append(values, field_rows, tab)

    if not values or previous_header != header:
        sheets.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=tab_range(tab, "A1"),
            valueInputOption="RAW",
            body={"values": [header]},
        ).execute()

    if fresh:
        sheets.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=tab_range(tab, "A1"),
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": fresh},
        ).execute()

    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
    note = f"Added {len(fresh)} new {'row' if len(fresh) == 1 else 'rows'} to tab {tab}."
    if skipped:
        note += f" Skipped {skipped} already on the sheet."
    return url, note


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
    field_rows = [lead_fields(lead) for lead in leads]
    title = f"LeadForge - {campaign.query} in {campaign.location}"

    try:
        if GOOGLE_SPREADSHEET_ID:
            tab = GOOGLE_SHEET_TAB_NAME or "Leads"
            url, warning = await asyncio.to_thread(append_to_sheet, GOOGLE_SPREADSHEET_ID, tab, field_rows)
        else:
            rows = [project_row(HEADERS, fields) for fields in field_rows]
            url, warning = await asyncio.to_thread(create_sheet, title, rows)
    except SheetExportError:
        raise
    except Exception as exc:
        logger.exception("Sheet export failed for campaign %s", campaign_id)
        raise SheetExportError(f"Google Sheets rejected the export: {exc}", status_code=502) from exc

    campaign.sheet_url = url[:500]
    await db.commit()
    return {"sheet_url": url, "warning": warning}
