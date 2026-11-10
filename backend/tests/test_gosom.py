import json

import pytest

from backend.workers.gosom import (
    GosomClient,
    build_job_body,
    has_real_website,
    parse_csv,
    passes_rating,
    select_places,
)


CSV = """title,category,address,website,phone,review_count,review_rating,latitude,longitude,status,place_id,link
No Site Bakery,Bakery,"1 Main St, Austin",,+1 512-555-0100,18,4.6,30.27,-97.74,,ChIJnosite,https://maps.google.com/?cid=1
Has Site Cafe,Cafe,"2 Main St, Austin",https://cafe.example,512-555-0101,40,4.8,30.27,-97.74,,ChIJhassite,https://maps.google.com/?cid=2
Social Salon,Salon,"3 Main St, Austin",https://facebook.com/socialsalon,512-555-0102,6,4.2,30.28,-97.75,,ChIJsocial,https://maps.google.com/?cid=3
Closed Shop,Plumber,"9 Far St, Austin",,512-555-0103,2,3.2,30.27,-97.74,Permanently closed,ChIJclosed,https://maps.google.com/?cid=4
"""


def test_blank_maps_and_social_are_not_websites():
    assert has_real_website("") is False
    assert has_real_website(None) is False
    assert has_real_website("https://www.google.com/maps/place/Ada") is False
    assert has_real_website("https://facebook.com/adabakery") is False
    assert has_real_website("https://www.instagram.com/adabakery") is False
    assert has_real_website("https://adabakery.com") is True


def test_rating_filter_uses_the_exact_number():
    assert passes_rating(4.2, 4.2) is True
    assert passes_rating(4.1, 4.2) is False
    assert passes_rating(None, 4.2) is False
    assert passes_rating(3.0, None) is True


def test_csv_keeps_blank_and_social_and_drops_real_sites():
    records = parse_csv(CSV)
    stats = select_places(
        records,
        seen_ids=set(),
        min_rating=4.0,
        min_reviews=5,
        max_reviews=None,
        center=(30.27, -97.74),
        radius_m=20000,
    )
    kept = {item["title"]: item for item in stats.kept}
    assert set(kept) == {"No Site Bakery", "Social Salon"}
    assert kept["No Site Bakery"]["website"] == ""
    assert kept["Social Salon"]["website"].startswith("https://facebook.com")
    assert kept["No Site Bakery"]["place_id"] == "ChIJnosite"
    assert stats.dropped_website == 1
    assert stats.closed == 1


def test_duplicate_place_and_review_filter():
    record = {
        "title": "Repeat",
        "website": "",
        "place_id": "same",
        "link": "https://maps.google.com/?cid=9",
        "review_rating": 4.5,
        "review_count": 3,
        "latitude": 30.27,
        "longitude": -97.74,
        "status": "",
    }
    stats = select_places(
        [record, dict(record)],
        seen_ids={"same"},
        min_rating=None,
        min_reviews=10,
        max_reviews=None,
        center=None,
        radius_m=5000,
    )
    assert stats.kept == []
    assert stats.duplicates == 2


def test_json_website_field_web_site_is_recognized():
    from backend.workers.gosom import normalize_record
    record = normalize_record({
        "title": "Hidden",
        "web_site": "https://hidden.example",
        "review_rating": 5,
        "review_count": 11,
        "place_id": "hid",
        "link": "https://maps.google.com/?cid=8",
    })
    stats = select_places(
        [record],
        seen_ids=set(),
        min_rating=None,
        min_reviews=None,
        max_reviews=20,
        center=None,
        radius_m=5000,
    )
    assert stats.dropped_website == 1
    assert stats.kept == []


def test_job_body_uses_seconds_and_the_city_keyword():
    body = build_job_body("plumber in Austin, TX", 10000, None, None, 10, 900)
    assert body["keywords"] == ["plumber in Austin, TX"]
    assert body["max_time"] == 900
    assert body["depth"] == 10
    assert body["lang"] == "en"
    assert body["email"] is False
    assert body["fast_mode"] is False
    assert body["lat"] == ""
    assert body["radius"] == 10000


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
        self.calls = []

    def request(self, method, url, json=None, **kwargs):
        self.calls.append({"method": method, "url": url, "json": json})
        status, text = self.responses.pop(0)
        return _Response(status, text)


@pytest.mark.asyncio
async def test_create_job_posts_to_gosom_and_retries_rate_limits(monkeypatch):
    async def fast_sleep(*_args, **_kwargs):
        return None

    monkeypatch.setattr("backend.workers.gosom.asyncio.sleep", fast_sleep)
    session = _Session([
        (429, "slow down"),
        (201, json.dumps({"id": "job-1"})),
    ])
    client = GosomClient(session, "http://localhost:8080/")
    job_id = await client.create_job("cafe in Austin, TX", 5000, 30.27, -97.74, 10, 900)
    assert job_id == "job-1"
    assert session.calls[0]["url"] == "http://localhost:8080/api/v1/jobs"
    assert session.calls[-1]["json"]["keywords"] == ["cafe in Austin, TX"]
    assert session.calls[-1]["json"]["max_time"] == 900
    assert len(session.calls) == 2


@pytest.mark.asyncio
async def test_poll_reads_go_status_field_and_downloads_csv(monkeypatch):
    clock = {"now": 0.0}

    def monotonic():
        return clock["now"]

    async def sleep(seconds):
        clock["now"] += seconds

    monkeypatch.setattr("backend.workers.gosom.time.monotonic", monotonic)
    monkeypatch.setattr("backend.workers.gosom.asyncio.sleep", sleep)
    csv_body = "title,website,place_id,link,review_rating,review_count\nAda Bakery,,ChIJ1,https://maps.google.com/?cid=1,4.5,9\n"
    session = _Session([
        (200, json.dumps({"ID": "job-9", "Status": "working"})),
        (200, json.dumps({"ID": "job-9", "Status": "ok"})),
        (200, csv_body),
    ])
    client = GosomClient(session, "http://scraper:8080")
    payload = await client.wait_for_job("job-9", timeout_s=30, poll_seconds=5)
    assert payload["Status"] == "ok"
    rows = await client.fetch_results("job-9", payload)
    assert rows[0]["title"] == "Ada Bakery"
    assert rows[0]["website"] == ""
    assert rows[0]["place_id"] == "ChIJ1"
    assert session.calls[-1]["url"].endswith("/api/v1/jobs/job-9/download")


@pytest.mark.asyncio
async def test_timeout_is_a_clear_error(monkeypatch):
    clock = {"now": 0.0}

    def monotonic():
        return clock["now"]

    async def sleep(seconds):
        clock["now"] += seconds

    monkeypatch.setattr("backend.workers.gosom.time.monotonic", monotonic)
    monkeypatch.setattr("backend.workers.gosom.asyncio.sleep", sleep)
    session = _Session([
        (200, json.dumps({"Status": "working"})),
        (200, json.dumps({"Status": "working"})),
        (200, json.dumps({"Status": "working"})),
    ])
    client = GosomClient(session, "http://scraper:8080")
    with pytest.raises(Exception) as caught:
        await client.wait_for_job("job-slow", timeout_s=10, poll_seconds=5)
    assert "still working" in str(caught.value).lower()


@pytest.mark.asyncio
async def test_failed_job_reports_the_scraper_error(monkeypatch):
    async def sleep(*_args, **_kwargs):
        return None

    monkeypatch.setattr("backend.workers.gosom.asyncio.sleep", sleep)
    session = _Session([
        (200, json.dumps({"status": "failed", "error": "Google blocked the browser"})),
    ])
    client = GosomClient(session, "http://scraper:8080")
    with pytest.raises(Exception) as caught:
        await client.wait_for_job("job-bad", timeout_s=30, poll_seconds=5)
    assert "blocked" in str(caught.value).lower()


@pytest.mark.asyncio
async def test_inline_json_results_skip_the_csv_download(monkeypatch):
    async def sleep(*_args, **_kwargs):
        return None

    monkeypatch.setattr("backend.workers.gosom.asyncio.sleep", sleep)
    payload = {
        "status": "completed",
        "results": [{
            "title": "JSON Cafe",
            "web_site": "",
            "place_id": "json-1",
            "link": "https://maps.google.com/?cid=4",
            "review_rating": 4.4,
            "review_count": 7,
        }],
    }
    session = _Session([(200, json.dumps(payload))])
    client = GosomClient(session, "http://scraper:8080")
    got = await client.wait_for_job("job-json", timeout_s=10, poll_seconds=5)
    rows = await client.fetch_results("job-json", got)
    assert rows[0]["title"] == "JSON Cafe"
    assert rows[0]["website"] == ""
    assert all("/download" not in call["url"] for call in session.calls)
