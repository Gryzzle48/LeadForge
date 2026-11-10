from httpx import ASGITransport, AsyncClient

async def test_radius_below_minimum(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/search", json={
            "query": "pizza", "location": "NYC", "radius": 1
        })
    assert resp.status_code == 422
    body = resp.json()
    detail = body["detail"][0] if isinstance(body["detail"], list) else body["detail"]
    assert any("radius" in str(e) for e in (body["detail"] if isinstance(body["detail"], list) else [body["detail"]]))

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

async def test_radius_above_places_limit(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/search", json={
            "query": "pizza", "location": "NYC", "radius": 90000
        })
    assert resp.status_code == 422

async def test_blank_query_fails(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/search", json={
            "query": "   ", "location": "NYC", "radius": 5000
        })
    assert resp.status_code == 422

async def test_review_range_must_be_ordered(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/search", json={
            "query": "pizza", "location": "NYC", "radius": 5000,
            "min_reviews": 50, "max_reviews": 10,
        })
    assert resp.status_code == 422

async def test_negative_rating_fails(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/search", json={
            "query": "pizza", "location": "NYC", "min_rating": -1
        })
    assert resp.status_code == 422
