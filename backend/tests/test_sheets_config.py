import base64
from types import SimpleNamespace

import pytest

from backend.config import normalize_database_url
from backend.workers.sheet_exporter import (
    HEADERS,
    SheetExportError,
    choose_write_tab,
    contacts_text,
    lead_row,
    load_service_account_info,
    maps_identity,
    plan_append,
    service_account_path_candidates,
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


def test_service_account_file_and_mounted_path(tmp_path):
    key = tmp_path / "service-account.json"
    key.write_text(
        '{"type":"service_account","client_email":"sheets@example.iam.gserviceaccount.com"}',
        encoding="utf-8",
    )
    info = load_service_account_info(str(key))
    assert info["client_email"].startswith("sheets@")
    candidates = service_account_path_candidates("./secrets/service-account.json")
    assert "/secrets/service-account.json" in candidates
    assert "/app/secrets/service-account.json" in candidates


def test_bad_service_account_is_rejected():
    with pytest.raises(SheetExportError):
        load_service_account_info("not-a-key")


def test_broken_json_is_not_echoed_back():
    raw = '{"private_key": "SECRET_KEY_MATERIAL"'
    with pytest.raises(SheetExportError) as caught:
        load_service_account_info(raw)
    assert "SECRET_KEY_MATERIAL" not in caught.value.message


def test_lead_row_is_the_five_contact_columns():
    lead = SimpleNamespace(
        name="Ada's Bakery",
        category="Bakery",
        address="1 Main St",
        phone="+1 512-555-0100",
        maps_url="https://www.google.com/maps/search/?api=1&query_place_id=ChIJada",
        rating=4.6,
        review_count=12,
        website_uri="https://facebook.com/adabakery",
        email="ada@example.com",
        email_subject="Hello",
        email_body="Draft body",
        email_status="draft",
        place_id="ChIJada",
    )
    row = lead_row(lead, 7)
    assert HEADERS == ["#", "Name", "Category", "Google Maps", "Contacts"]
    assert row == [
        7,
        "Ada's Bakery",
        "Bakery",
        "https://www.google.com/maps/search/?api=1&query_place_id=ChIJada",
        "+1 512-555-0100\nada@example.com\nhttps://facebook.com/adabakery",
    ]
    assert "Draft body" not in row
    assert "1 Main St" not in row


def test_contacts_skip_blanks_and_maps_links():
    assert contacts_text("+1 512", "", "https://www.google.com/maps/place/Ada") == "+1 512"
    assert contacts_text("", "", "") == ""


def test_maps_links_with_the_same_place_match():
    full = "https://www.google.com/maps/search/?api=1&query_place_id=ChIJada"
    messy = "https://maps.google.com/maps?q=place&query_place_id=ChIJada"
    assert maps_identity(full) == maps_identity(messy)
    assert maps_identity("https://maps.google.com/?cid=99") == maps_identity("http://www.google.com/maps?cid=99")


def test_append_continues_numbering_and_skips_the_same_map():
    existing = [
        ["#", "Name", "Category", "Google Maps", "Contacts"],
        [1, "Ada's Bakery", "Bakery", "https://www.google.com/maps/search/?api=1&query_place_id=ChIJada", "+1 512-555-0100"],
        [4, "Other", "Cafe", "https://maps.google.com/?cid=55", ""],
    ]
    incoming = [{
        "name": "Ada again",
        "category": "Bakery",
        "maps": "https://maps.google.com/maps?query_place_id=ChIJada",
        "phone": "different",
        "email": "",
        "extra": "",
    }, {
        "name": "New Cafe",
        "category": "Cafe",
        "maps": "https://maps.google.com/?cid=77",
        "phone": "512-555-0199",
        "email": "",
        "extra": "https://instagram.com/newcafe",
    }]
    header, rows, skipped = plan_append(existing, incoming, "Leads")
    assert header == HEADERS
    assert skipped == 1
    assert rows == [[
        5, "New Cafe", "Cafe", "https://maps.google.com/?cid=77",
        "512-555-0199\nhttps://instagram.com/newcafe",
    ]]


def test_append_without_a_map_uses_name_and_contacts():
    existing = [
        ["#", "Name", "Category", "Google Maps", "Contacts"],
        [2, "Ada's Bakery", "Bakery", "", "+1 512-555-0100"],
    ]
    incoming = [
        {"name": "Ada's Bakery", "category": "Bakery", "maps": "", "phone": "+1 512-555-0100", "email": "", "extra": ""},
        {"name": "Ada's Bakery", "category": "Bakery", "maps": "", "phone": "different", "email": "", "extra": ""},
    ]
    _header, rows, skipped = plan_append(existing, incoming, "Leads")
    assert skipped == 1
    assert rows[0][0] == 3
    assert rows[0][1] == "Ada's Bakery"
    assert rows[0][4] == "different"


def test_old_header_is_not_rewritten():
    existing = [["Name", "Phone", "Maps link"], ["Ada", "555", "https://maps.example/ada"]]
    with pytest.raises(SheetExportError) as caught:
        plan_append(existing, [{
            "name": "New", "category": "Cafe", "maps": "https://maps.google.com/?cid=1",
            "phone": "", "email": "", "extra": "",
        }], "Leads")
    assert "was not changed" in caught.value.message


def test_mismatched_tab_switches_to_a_leadforge_tab():
    headers = {
        "Leads": ["Name", "Address"],
        "Leads (LeadForge)": None,
    }
    tab, switched = choose_write_tab("Leads", headers)
    assert tab == "Leads (LeadForge)"
    assert switched == "Leads"
    both = {"Leads": ["Name"], "Leads (LeadForge)": ["Something else"]}
    with pytest.raises(SheetExportError) as caught:
        choose_write_tab("Leads", both)
    assert "nothing was written" in caught.value.message
