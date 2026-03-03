import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from main import app


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


# ---------- Integration tests (use real SQLite DB via conftest.py) ----------

async def test_create_lead_full_integration(client):
    from unittest.mock import patch, AsyncMock
    with patch("routers.leads.trigger_n8n", new_callable=AsyncMock):
        response = await client.post(
            "/api/v1/leads",
            json={
                "name": "Alice Smith",
                "email": "alice@acme.com",
                "company": "Acme Corp",
                "source": "website",
                "message": "Interested in your product.",
            },
        )
    assert response.status_code == 202
    data = response.json()
    assert "lead_id" in data
    assert len(data["lead_id"]) == 36  # UUID format


async def test_create_lead_triggers_n8n(client):
    from unittest.mock import patch, AsyncMock, call
    with patch("routers.leads.trigger_n8n", new_callable=AsyncMock) as mock_trigger:
        await client.post(
            "/api/v1/leads",
            json={
                "name": "Bob Jones",
                "email": "bob@startup.io",
                "company": "StartupIO",
                "source": "linkedin",
            },
        )
    mock_trigger.assert_called_once()
    call_args = mock_trigger.call_args[0][0]
    assert call_args["email"] == "bob@startup.io"
    assert "lead_id" in call_args


async def test_log_event_for_lead(client):
    from unittest.mock import patch, AsyncMock
    with patch("routers.leads.trigger_n8n", new_callable=AsyncMock):
        create_response = await client.post(
            "/api/v1/leads",
            json={
                "name": "Bob Jones",
                "email": "bob@startup.io",
                "company": "StartupIO",
                "source": "linkedin",
            },
        )
    lead_id = create_response.json()["lead_id"]

    event_response = await client.post(
        f"/api/v1/leads/{lead_id}/events",
        json={"event_type": "scored", "payload": {"tier": "A", "score": 85}},
    )
    assert event_response.status_code == 200
    assert event_response.json() == {"status": "logged"}


async def test_queue_lead(client):
    from unittest.mock import patch, AsyncMock
    with patch("routers.leads.trigger_n8n", new_callable=AsyncMock):
        create_response = await client.post(
            "/api/v1/leads",
            json={
                "name": "Carol Chen",
                "email": "carol@mid.com",
                "company": "MidCo",
                "source": "form",
            },
        )
    lead_id = create_response.json()["lead_id"]

    queue_response = await client.post(
        f"/api/v1/leads/{lead_id}/queue",
        json={"tier": "B", "score": 55, "reasoning": "Partial ICP match"},
    )
    assert queue_response.status_code == 200
    assert queue_response.json() == {"status": "queued"}


async def test_log_disqualified_lead(client):
    from unittest.mock import patch, AsyncMock
    with patch("routers.leads.trigger_n8n", new_callable=AsyncMock):
        create_response = await client.post(
            "/api/v1/leads",
            json={
                "name": "Dave Student",
                "email": "dave@gmail.com",
                "company": "None",
                "source": "website",
            },
        )
    lead_id = create_response.json()["lead_id"]

    log_response = await client.post(
        f"/api/v1/leads/{lead_id}/log",
        json={"tier": "C", "score": 15},
    )
    assert log_response.status_code == 200
    assert log_response.json() == {"status": "logged"}


async def test_log_error(client):
    response = await client.post(
        "/api/v1/errors",
        json={
            "source": "n8n-error-trigger",
            "error_message": "Claude API timeout",
            "payload": {"workflow": "lead-qualification"},
        },
    )
    assert response.status_code == 200
    assert response.json() == {"status": "logged"}
