import pytest
from httpx import AsyncClient, ASGITransport
from app.main import create_app

class TestHealthAPI:
    @pytest.mark.asyncio
    async def test_health(self):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "healthy"
