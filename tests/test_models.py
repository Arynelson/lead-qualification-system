def test_models_importable():
    from models.lead import Lead
    from models.enrichment import EnrichmentData
    from models.ai_score import AIScore
    from models.lead_event import LeadEvent
    from models.error import ErrorLog

    assert Lead.__tablename__ == "leads"
    assert EnrichmentData.__tablename__ == "enrichment_data"
    assert AIScore.__tablename__ == "ai_scores"
    assert LeadEvent.__tablename__ == "lead_events"
    assert ErrorLog.__tablename__ == "errors"


def test_lead_create_schema_valid():
    from models.schemas import LeadCreate
    lead = LeadCreate(
        name="Alice Smith",
        email="alice@example.com",
        company="Acme Corp",
        source="website",
    )
    assert lead.email == "alice@example.com"
    assert lead.message is None


def test_lead_create_schema_rejects_invalid_email():
    from models.schemas import LeadCreate
    from pydantic import ValidationError
    import pytest
    with pytest.raises(ValidationError):
        LeadCreate(name="A", email="not-an-email", company="X", source="y")


def test_lead_response_schema():
    from models.schemas import LeadResponse
    r = LeadResponse(lead_id="abc-123")
    assert r.status == "received"


def test_metrics_response_schema():
    from models.schemas import MetricsResponse
    m = MetricsResponse(
        leads_today=5,
        leads_this_week=20,
        tier_a=3,
        tier_b=10,
        tier_c=7,
        avg_processing_time_seconds=12.5,
        error_rate=0.01,
    )
    assert m.tier_a == 3
