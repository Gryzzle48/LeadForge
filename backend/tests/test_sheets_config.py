import base64
from types import SimpleNamespace

import pytest

from backend.config import normalize_database_url
from backend.workers.sheet_exporter import (
    HEADERS,
    SheetExportError,
    lead_row,
    load_service_account_info,
    plan_append,
)


def test_postgres_url_and_sslmode_are_converted():
    url, args = normalize_database_url(
        "postgres://user:pass@host:5432/db?sslmode=require&channel_binding=require"
    )
    assert url.startswith("postgresql+asyncpg://user:pass@host:5432/db")
    assert "sslmode" not in url
    assert "channel_binding" not in url
    assert args["ssl"] is True


def test_asyncpg_url_without_ssl_is_unchanged():
    raw = "postgresql+asyncpg://postgres:postgres@localhost:5432/leadforge"
    url, args = normalize_database_url(raw)
    assert url == raw
    assert "ssl" not in args


def test_service_account_json_and_base64():
    raw = '{"type":"service_account","client_email":"sheets@example.iam.gserviceaccount.com"}'
    assert load_service_account_info(raw)["client_email"].startswith("sheets@")
    encoded = base64.b64encode(raw.encode()).decode()
    assert load_service_account_info(encoded)["type"] == "service_account"


def test_bad_service_account_is_rejected():
    with pytest.raises(SheetExportError):
        load_service_account_info("not-a-key")


def test_broken_json_is_not_echoed_back():
    raw = '{"private_key": "SECRET_KEY_MATERIAL"'
    with pytest.raises(SheetExportError) as caught:
        load_service_account_info(raw)
    assert "SECRET_KEY_MATERIAL" not in caught.value.message


def test_lead_row_has_the_fields_needed_to_call_them():
    lead = SimpleNamespace(
        name="Ada's Bakery",
        category="Bakery",
        address="1 Main St",
        phone="+1 512-555-0100",
        maps_url="https://maps.example/ada",
        rating=4.6,
        review_count=12,
        website_uri="",
        email="",
        email_subject="Hello",
        email_body="Draft body",
        email_status="draft",
        place_id="abc",
    )
    row = lead_row(lead)
    assert HEADERS == [
        "Name", "Category", "Address", "Phone", "Maps link", "Rating",
        "Reviews", "Website", "Email", "Subject", "Draft", "Status", "Notes",
        "Place ID",
    ]
    assert row[0] == "Ada's Bakery"
    assert row[1] == "Bakery"
    assert row[2] == "1 Main St"
    assert row[3] == "+1 512-555-0100"
    assert row[4] == "https://maps.example/ada"
    assert row[5] == 4.6
    assert row[6] == 12
    assert row[7] == ""
    assert row[10] == "Draft body"
    assert row[-1] == "abc"
    assert row.count("Ada's Bakery") == 1


def test_append_skips_rows_already_on_the_sheet():
    existing = [[
        "Name", "Phone", "Maps link",
    ], [
        "Ada's Bakery", "+1 512-555-0100", "https://maps.example/ada",
    ]]
    incoming = [{
        "name": "Ada's Bakery",
        "phone": "+1 512-555-0100",
        "maps": "https://maps.example/ada",
        "place_id": "abc",
        "address": "1 Main St",
        "category": "Bakery",
        "rating": 4.6,
        "reviews": 12,
        "website": "",
        "email": "",
        "subject": "Hello",
        "draft": "Draft",
        "status": "draft",
        "notes": "",
    }, {
        "name": "New Cafe",
        "phone": "+1 512-555-0199",
        "maps": "https://maps.example/new",
        "place_id": "new",
        "address": "2 Main St",
        "category": "Cafe",
        "rating": 4.2,
        "reviews": 8,
        "website": "",
        "email": "",
        "subject": "",
        "draft": "",
        "status": "draft",
        "notes": "",
    }]
    header, rows, skipped = plan_append(existing, incoming, "Leads")
    assert skipped == 1
    assert len(rows) == 1
    assert "Place ID" in header
    assert rows[0][header.index("Name")] == "New Cafe"
    assert rows[0][header.index("Place ID")] == "new"
