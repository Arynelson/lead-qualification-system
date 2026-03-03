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
