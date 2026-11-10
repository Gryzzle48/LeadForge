import asyncio
import base64
import json
import logging
import os
import re
from urllib.parse import parse_qs, urlparse

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

HEADERS = ["#", "Name", "Category", "Google Maps", "Contacts"]
TAB_SUFFIX = " (LeadForge)"


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


def _is_maps_link(url: str) -> bool:
    lowered = (url or "").strip().lower()
    return any(marker in lowered for marker in (
        "google.com/maps", "maps.google.", "goo.gl/maps", "maps.app.goo.gl",
    ))


def contacts_text(phone: str = "", email: str = "", extra: str = "") -> str:
    """Phone, email, and a social or other link, one per line. Blanks are left out."""
    parts = []
    seen = set()
    for value in (phone, email, extra):
        text = str(value or "").strip()
        if not text or _is_maps_link(text):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        parts.append(text)
    return "\n".join(parts)


def maps_identity(url: str) -> str:
    """Stable key for a Maps link. Place id or cid when the URL has one."""
    text = (url or "").strip()
    if not text:
        return ""
    candidate = text if "://" in text else "https://" + text
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return "url:" + text.lower().rstrip("/")
    query = parse_qs(parsed.query)
    for key in ("query_place_id", "place_id"):
        values = query.get(key) or []
        if values and str(values[0]).strip():
            return "place:" + str(values[0]).strip()
    cid_values = query.get("cid") or []
    if cid_values and str(cid_values[0]).strip():
        return "cid:" + str(cid_values[0]).strip()
    place = re.search(r"(ChIJ[A-Za-z0-9_-]+)", text)
    if place:
        return "place:" + place.group(1)
    cid = re.search(r"(?:[?&]cid=|!1s)(\d{5,})", text)
    if cid:
        return "cid:" + cid.group(1)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    tail = f"{host}{path}"
    if parsed.query:
        tail += "?" + parsed.query
    return "url:" + tail.lower()


def _squash(value: str) -> str:
    return " ".join(str(value or "").lower().split())


def row_identity(name: str, maps: str, contacts: str) -> set[str]:
    ident = maps_identity(maps)
    if ident:
        return {"map:" + ident}
    fallback = _squash(name) + "|" + _squash(contacts.replace("\n", " "))
    if fallback != "|":
        return {"nc:" + fallback}
    return set()


def lead_fields(lead) -> dict:
    extra = getattr(lead, "website_uri", None) or ""
    return {
        "name": lead.name or "",
        "category": lead.category or "",
        "maps": maps_url_for(getattr(lead, "place_id", None), getattr(lead, "maps_url", None)),
        "phone": lead.phone or "",
        "email": lead.email or "",
        "extra": extra,
    }


def lead_row(lead, number: int) -> list:
    fields = lead_fields(lead) if not isinstance(lead, dict) else lead
    contacts = contacts_text(fields.get("phone", ""), fields.get("email", ""), fields.get("extra", ""))
    return [number, fields.get("name") or "", fields.get("category") or "", fields.get("maps") or "", contacts]


def header_matches(row) -> bool:
    cells = [str(cell).strip() for cell in row]
    while cells and cells[-1] == "":
        cells.pop()
    return cells == HEADERS


def next_row_number(existing_values: list[list]) -> int:
    if len(existing_values) <= 1:
        return 1
    last = existing_values[-1]
    if last:
        try:
            return int(float(str(last[0]).strip())) + 1
        except (TypeError, ValueError):
            pass
    return len(existing_values)


def alternate_tab_name(tab: str) -> str:
    suffix = TAB_SUFFIX
    base = tab[:-len(suffix)] if tab.endswith(suffix) else tab
    name = f"{base}{suffix}"
    return name[:100]


def tab_range(tab: str, a1: str) -> str:
    safe = (tab or "Leads").replace("'", "''")
    return f"'{safe}'!{a1}"


def plan_append(existing_values: list[list], field_rows: list[dict], tab: str) -> tuple[list[str], list[list], int]:
    """Return the header, new data rows, and how many leads were already present.

    The tab is used only when it is empty or its header is exactly
    #, Name, Category, Google Maps, Contacts. Anything else is refused so the
    old tab is not rewritten.
    """
    if existing_values and not header_matches(existing_values[0]):
        raise SheetExportError(
            f"Tab {tab!r} has a different header, so it was not changed. "
            "Use an empty tab, or a tab whose header is: #, Name, Category, Google Maps, Contacts."
        )
    start = next_row_number(existing_values)
    seen = set()
    for row in existing_values[1:]:
        name = row[1] if len(row) > 1 else ""
        maps = row[3] if len(row) > 3 else ""
        contacts = row[4] if len(row) > 4 else ""
        seen.update(row_identity(str(name), str(maps), str(contacts)))

    fresh = []
    skipped = 0
    number = start
    for fields in field_rows:
        contacts = contacts_text(fields.get("phone", ""), fields.get("email", ""), fields.get("extra", ""))
        keys = row_identity(fields.get("name") or "", fields.get("maps") or "", contacts)
        if keys and keys & seen:
            skipped += 1
            continue
        seen.update(keys)
        fresh.append([number, fields.get("name") or "", fields.get("category") or "", fields.get("maps") or "", contacts])
        number += 1
    return list(HEADERS), fresh, skipped


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


def choose_write_tab(requested: str, headers: dict) -> tuple[str, str | None]:
    """Pick a tab that is missing, empty, or already uses the LeadForge header.

    headers maps a tab name to None (missing), [] (empty), or its first row.
    A tab with any other header is left untouched. The return value is
    (tab to write, original tab name if we switched, otherwise None).
    """
    def usable(name: str) -> bool:
        header = headers.get(name, None)
        if header is None or header == []:
            return True
        return header_matches(header)

    if usable(requested):
        return requested, None
    alt = alternate_tab_name(requested)
    if alt != requested and usable(alt):
        return alt, requested
    raise SheetExportError(
        f"Tabs {requested!r} and {alt!r} both have a different header, so nothing was written. "
        "Set GOOGLE_SHEET_TAB_NAME to a new empty tab."
    )


def _header_row(sheets, spreadsheet_id: str, tab: str):
    existing = sheets.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=tab_range(tab, "1:1"),
    ).execute()
    values = existing.get("values") or []
    return values[0] if values else []


def _ensure_tab(sheets, spreadsheet_id: str, tab: str, titles: list[str]):
    if tab in titles:
        return
    sheets.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": tab}}}]},
    ).execute()
    titles.append(tab)


def _writable_tab(sheets, spreadsheet_id: str, tab: str, titles: list[str]) -> tuple[str, str | None]:
    known = {}
    for name in {tab, alternate_tab_name(tab)}:
        if name in titles:
            known[name] = _header_row(sheets, spreadsheet_id, name)
        else:
            known[name] = None
    chosen, switched = choose_write_tab(tab, known)
    _ensure_tab(sheets, spreadsheet_id, chosen, titles)
    return chosen, switched


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
    tab, switched = _writable_tab(sheets, spreadsheet_id, tab, titles)
    existing = sheets.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=tab_range(tab, "A:Z"),
    ).execute()
    values = existing.get("values") or []
    header, fresh, skipped = plan_append(values, field_rows, tab)

    if not values:
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
    if switched:
        note = (
            f"Tab {switched!r} has a different header, so it was left as-is. "
            f"Rows were written to {tab!r} instead. {note}"
        )
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
            rows = [lead_row(fields, index) for index, fields in enumerate(field_rows, start=1)]
            url, warning = await asyncio.to_thread(create_sheet, title, rows)
    except SheetExportError:
        raise
    except Exception as exc:
        logger.exception("Sheet export failed for campaign %s", campaign_id)
        raise SheetExportError(f"Google Sheets rejected the export: {exc}", status_code=502) from exc

    campaign.sheet_url = url[:500]
    await db.commit()
    return {"sheet_url": url, "warning": warning}
