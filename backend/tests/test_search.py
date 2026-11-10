from httpx import ASGITransport, AsyncClient

async def test_radius_is_not_a_filter(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/search", json={
            "query": "pizza", "location": "Austin, TX", "radius": 1, "target_leads": 5
        })
    assert "radius" not in resp.text

async def test_target_must_be_positive(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/search", json={
            "query": "pizza", "location": "Austin, TX", "target_leads": 0
        })
    assert resp.status_code == 422

async def test_missing_query(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/search", json={
            "location": "Austin, TX"
        })
    assert resp.status_code == 422

async def test_missing_location(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/search", json={
            "query": "pizza"
        })
    assert resp.status_code == 422

async def test_blank_query_fails(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/search", json={
            "query": "   ", "location": "Austin, TX"
        })
    assert resp.status_code == 422

async def test_review_range_must_be_ordered(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/search", json={
            "query": "pizza", "location": "Austin, TX",
            "min_reviews": 50, "max_reviews": 10,
        })
    assert resp.status_code == 422

async def test_negative_rating_fails(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/search", json={
            "query": "pizza", "location": "Austin, TX", "min_rating": -1
        })
    assert resp.status_code == 422
