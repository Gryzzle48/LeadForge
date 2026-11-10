import pytest
from pydantic import ValidationError
from httpx import ASGITransport, AsyncClient
from backend.routers.search import SearchRequest


async def test_radius_below_minimum(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/search", json={
            "query": "pizza", "location": "NYC", "radius": 1
        })
    assert resp.status_code == 422
    body = resp.json()
    assert any("radius" in str(error) for error in body["detail"])


async def test_radius_at_minimum(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/search", json={
            "query": "pizza", "location": "NYC", "radius": 100
        })
    assert resp.status_code in (200, 422)


async def test_missing_query(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/search", json={
            "location": "NYC", "radius": 5000
        })
    assert resp.status_code == 422


async def test_missing_location(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/search", json={
            "query": "pizza", "radius": 5000
        })
    assert resp.status_code == 422


async def test_negative_rating_fails(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/search", json={
            "query": "pizza", "location": "NYC", "min_rating": -1
        })
    assert resp.status_code == 422


def test_city_state_and_result_limit_are_normalized():
    request = SearchRequest(
        query="coffee shops",
        city="Miami",
        state="Florida",
        max_results=120,
    )
    assert request.location == "Miami, Florida, United States"
    assert request.max_results == 120


def test_legacy_location_field_remains_supported():
    request = SearchRequest(query="barbershop", location="Austin, TX")
    assert request.city == "Austin"
    assert request.state == "TX"
    assert request.location == "Austin, TX, United States"


def test_result_limit_is_bounded():
    with pytest.raises(ValidationError):
        SearchRequest(query="coffee shops", city="Miami", state="Florida", max_results=121)
