import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from main import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_create_lead_validates_email(client):
    response = await client.post(
        "/api/v1/leads",
        json={
            "name": "Test",
            "email": "not-an-email",
            "company": "ACME",
            "source": "web",
        },
    )
    assert response.status_code == 422


async def test_create_lead_missing_required_field(client):
    response = await client.post(
        "/api/v1/leads",
        json={"name": "Test", "email": "test@example.com"},  # missing company and source
    )
    assert response.status_code == 422
