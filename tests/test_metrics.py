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


async def test_metrics_endpoint_returns_200(client):
    mock_result = {
        "leads_today": 5,
        "leads_this_week": 20,
        "tier_a": 3,
        "tier_b": 10,
        "tier_c": 7,
        "avg_processing_time_seconds": 12.5,
        "error_rate": 0.01,
    }
    with patch("routers.metrics.get_metrics", new_callable=AsyncMock, return_value=mock_result):
        response = await client.get("/api/v1/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "leads_today" in data
    assert "tier_a" in data
    assert "error_rate" in data


async def test_metrics_schema_fields(client):
    mock_result = {
        "leads_today": 0,
        "leads_this_week": 0,
        "tier_a": 0,
        "tier_b": 0,
        "tier_c": 0,
        "avg_processing_time_seconds": 0.0,
        "error_rate": 0.0,
    }
    with patch("routers.metrics.get_metrics", new_callable=AsyncMock, return_value=mock_result):
        response = await client.get("/api/v1/metrics")
    assert response.status_code == 200
    data = response.json()
    required_fields = ["leads_today", "leads_this_week", "tier_a", "tier_b", "tier_c",
                       "avg_processing_time_seconds", "error_rate"]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"
