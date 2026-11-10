import json

import pytest

from backend.workers.places import (
    PAGE_SIZE,
    PlacesClient,
    api_min_rating,
    build_search_body,
    collect_pages,
    has_real_website,
    passes_rating,
    passes_reviews,
    resolve_origin,
    select_leads,
    walk_area,
)


def place(pid="p1", **kwargs):
    data = {
        "id": pid,
        "displayName": {"text": kwargs.get("name", "Ada Bakery")},
        "formattedAddress": kwargs.get("address", "1 Main St, Austin, TX"),
        "location": {
            "latitude": kwargs.get("lat", 30.267),
            "longitude": kwargs.get("lng", -97.743),
        },
        "rating": kwargs.get("rating", 4.6),
        "userRatingCount": kwargs.get("reviews", 18),
        "primaryTypeDisplayName": {"text": kwargs.get("category", "Bakery")},
        "websiteUri": kwargs.get("website", ""),
        "businessStatus": kwargs.get("status", "OPERATIONAL"),
    }
    return data


def test_maps_link_is_not_a_website():
    assert has_real_website("") is False
    assert has_real_website(None) is False
    assert has_real_website("https://www.google.com/maps/place/Ada") is False
    assert has_real_website("https://maps.app.goo.gl/abc") is False
    assert has_real_website("https://adabakery.com") is True


def test_api_min_rating_does_not_round_up():
    assert api_min_rating(4.2) == 4.0
    assert api_min_rating(4.0) == 4.0
    assert api_min_rating(None) is None
    assert passes_rating(4.3, 4.2) is True
    assert passes_rating(4.1, 4.2) is False
    assert passes_rating(None, 4.2) is False
    assert passes_rating(3.0, None) is True


def test_review_filter():
    assert passes_reviews(10, 5, 20) is True
    assert passes_reviews(4, 5, None) is False
    assert passes_reviews(30, None, 20) is False
    assert passes_reviews(None, 1, None) is False
    assert passes_reviews(None, None, None) is True


def test_search_body_pages_and_restricts_area():
    body = build_search_body("plumber in Austin, TX", (30.0, -98.0, 30.2, -97.8), 4.2, "restriction")
    assert body["pageSize"] == PAGE_SIZE == 20
    assert body["pageSize"] != 60
    assert "locationRestriction" in body
    assert "locationBias" not in body
    assert body["minRating"] == 4.0
    assert "pageToken" not in body
    low = body["locationRestriction"]["rectangle"]["low"]
    high = body["locationRestriction"]["rectangle"]["high"]
    assert low["latitude"] <= high["latitude"]
    assert low["longitude"] <= high["longitude"]


def test_failed_geocode_does_not_fall_back_to_new_york():
    origin, error = resolve_origin(None, None, None)
    assert origin is None
    assert error
    assert origin != (40.7128, -74.0060)


def test_explicit_coordinates_are_used():
    origin, error = resolve_origin(30.27, -97.74, None)
    assert error is None
    assert origin[0] == 30.27
    assert origin[1] == -97.74


@pytest.mark.asyncio
async def test_pagination_follows_three_pages_and_stops():
    pages = {
        None: ([{"id": "a"}], "t1", None),
        "t1": ([{"id": "b"}], "t2", None),
        "t2": ([{"id": "c"}], "t3", None),
        "t3": ([{"id": "d"}], None, None),
    }
    seen = []

    async def fetch(token):
        seen.append(token)
        return pages[token]

    found, requests, saturated, error = await collect_pages(fetch, max_pages=3)
    assert error is None
    assert requests == 3
    assert saturated is True
    assert [p["id"] for p in found] == ["a", "b", "c"]
    assert seen == [None, "t1", "t2"]


@pytest.mark.asyncio
async def test_pagination_stops_when_there_is_no_next_page():
    async def fetch(token):
        assert token is None
        return [{"id": "only"}], None, None

    found, requests, saturated, error = await collect_pages(fetch)
    assert found == [{"id": "only"}]
    assert requests == 1
    assert saturated is False
    assert error is None


@pytest.mark.asyncio
async def test_full_cell_is_split_and_a_small_cell_is_not():
    calls = []

    async def search_cell(bounds):
        calls.append(bounds)
        if len(calls) == 1:
            return [{"id": "saturated"}], 3, True, None
        return [{"id": f"child-{len(calls)}"}], 1, False, None

    found, errors, used, truncated = await walk_area(
        search_cell, (30.0, -98.0, 30.5, -97.5), max_requests=20, min_cell_m=1000
    )
    assert errors == []
    assert len(calls) == 5
    assert used == 7
    assert truncated is False
    assert len(found) == 5

    small_calls = []

    async def small_cell(bounds):
        small_calls.append(bounds)
        return [{"id": "one"}], 3, True, None

    await walk_area(small_cell, (30.0, -97.0, 30.001, -96.999), max_requests=20, min_cell_m=1500)
    assert len(small_calls) == 1


def test_select_leads_drops_websites_and_keeps_confirmed_gaps():
    with_site = place("has-site", website="https://example.com")
    hidden_site = place("hidden-site", website="")
    no_site = place("no-site", website="", name="No Site Cafe")
    unrated = place("unrated", website="", rating=None, reviews=3)
    low_reviews = place("few", website="", reviews=2)
    outside = place("outside", website="", lat=32.0, lng=-97.7)
    closed = place("closed", website="", status="CLOSED_PERMANENTLY")
    duplicate = place("no-site", website="")
    maps_only = place("maps-only", website="https://www.google.com/maps/place/x")

    stats = select_leads(
        [with_site, hidden_site, no_site, unrated, low_reviews, outside, closed, duplicate, maps_only],
        {
            "hidden-site": {"websiteUri": "https://hidden.example"},
            "no-site": {"websiteUri": ""},
            "unrated": {"websiteUri": ""},
            "few": {"websiteUri": ""},
            "maps-only": {"websiteUri": "https://maps.app.goo.gl/abc"},
        },
        seen_ids=set(),
        min_rating=4.0,
        min_reviews=5,
        max_reviews=None,
        center=(30.267, -97.743),
        radius_m=8000,
    )
    kept_ids = [p["id"] for p in stats.kept]
    assert kept_ids == ["no-site", "maps-only"]
    assert stats.dropped_website == 2
    assert stats.filtered_out == 2
    assert stats.outside == 1
    assert stats.closed == 1
    assert stats.duplicates == 1


def test_unconfirmed_place_is_not_saved_as_a_lead():
    stats = select_leads(
        [place("maybe", website="")],
        {},
        seen_ids=set(),
        min_rating=None,
        min_reviews=None,
        max_reviews=None,
        center=(30.267, -97.743),
        radius_m=8000,
        details_available=True,
    )
    assert stats.kept == []
    assert stats.unverified == 1


def test_details_outage_still_uses_the_search_website_field():
    stats = select_leads(
        [place("open", website=""), place("site", website="https://shop.example")],
        {},
        seen_ids=set(),
        min_rating=None,
        min_reviews=None,
        max_reviews=None,
        center=None,
        radius_m=8000,
        details_available=False,
    )
    assert [p["id"] for p in stats.kept] == ["open"]
    assert stats.dropped_website == 1
    assert stats.unverified == 0


class _Response:
    def __init__(self, status, text):
        self.status = status
        self._text = text

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.last = None

    def request(self, method, url, headers=None, json=None):
        self.calls += 1
        self.last = {"method": method, "url": url, "json": json}
        status, text = self.responses.pop(0)
        return _Response(status, text)


@pytest.mark.asyncio
async def test_rate_limit_is_retried_and_then_reported(monkeypatch):
    async def fast_sleep(*_args, **_kwargs):
        return None

    monkeypatch.setattr("backend.workers.places.asyncio.sleep", fast_sleep)
    session = _Session([(429, "slow down")] * 4)
    client = PlacesClient(session, "key")
    data, error, fatal = await client._request("POST", "https://places.example", {}, {})
    assert data is None
    assert "429" in error
    assert fatal is False
    assert session.calls == 4


@pytest.mark.asyncio
async def test_rate_limit_then_success(monkeypatch):
    async def fast_sleep(*_args, **_kwargs):
        return None

    monkeypatch.setattr("backend.workers.places.asyncio.sleep", fast_sleep)
    session = _Session([
        (429, "slow down"),
        (200, json.dumps({"places": [{"id": "ok"}]})),
    ])
    client = PlacesClient(session, "key")
    data, error, fatal = await client._request("POST", "https://places.example", {}, {})
    assert error is None
    assert data["places"][0]["id"] == "ok"
    assert session.calls == 2


@pytest.mark.asyncio
async def test_auth_error_is_not_retried(monkeypatch):
    async def fast_sleep(*_args, **_kwargs):
        return None

    monkeypatch.setattr("backend.workers.places.asyncio.sleep", fast_sleep)
    session = _Session([(401, "API key invalid")])
    client = PlacesClient(session, "key")
    data, error, fatal = await client._request("GET", "https://places.example", {}, None)
    assert data is None
    assert fatal is True
    assert session.calls == 1


@pytest.mark.asyncio
async def test_rejected_restriction_falls_back_to_bias(monkeypatch):
    async def fast_sleep(*_args, **_kwargs):
        return None

    monkeypatch.setattr("backend.workers.places.asyncio.sleep", fast_sleep)
    session = _Session([
        (400, '{"error":{"message":"locationRestriction is not supported for this query"}}'),
        (200, json.dumps({"places": [{"id": "abc"}]})),
    ])
    client = PlacesClient(session, "key")
    places, used, saturated, error = await client.search_cell(
        "plumber in Austin", (30.0, -98.0, 30.1, -97.9), None
    )
    assert error is None
    assert saturated is False
    assert places[0]["id"] == "abc"
    assert used == 2
    assert "locationBias" in session.last["json"]
    assert "locationRestriction" not in session.last["json"]
