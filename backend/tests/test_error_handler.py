import asyncio

from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from backend.main import unhandled_exception


def _client_app():
    app = FastAPI()
    app.add_exception_handler(Exception, unhandled_exception)

    @app.get("/boom")
    async def boom():
        raise RuntimeError("secret database password")

    @app.get("/missing")
    async def missing():
        raise HTTPException(status_code=404, detail="Campaign not found")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    return transport


def test_unhandled_errors_are_json_and_hide_the_cause():
    transport = _client_app()

    async def run():
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/boom")

    response = asyncio.run(run())
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert "detail" in body
    assert "password" not in response.text
    assert "secret" not in body["detail"]


def test_http_exceptions_keep_their_status_and_message():
    transport = _client_app()

    async def run():
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/missing")

    response = asyncio.run(run())
    assert response.status_code == 404
    assert response.json()["detail"] == "Campaign not found"
