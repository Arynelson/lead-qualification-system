
# PRD #1 — Lead Qualification System

## Overview

**Product name:** Lead Qualification System
**Version:** 1.0
**Backend:** Python 3.12 + FastAPI
**Target completion:** 29 March 2026
**GitHub repo:** `MakeItBot/lead-qualification-system`

### Problem Statement

SDRs at B2B companies spend 30–40% of their time manually reviewing inbound leads that will never convert. The process is slow (leads wait hours), inconsistent (scoring varies by rep), and expensive. An automated pipeline can score and route 80%+ of leads without human intervention, letting SDRs focus only on genuinely qualified prospects.

### Goals

- **Primary:** Demonstrate a production-grade n8n workflow to European employers
- **Secondary:** Show Python FastAPI backend design (learning project)
- **Tertiary:** Show Claude AI structured output integration

---

## User Stories

**As a sales manager,** I want inbound leads scored and routed automatically so SDRs only touch qualified prospects.

**As an SDR,** I want a Slack notification with a complete lead profile and AI score the moment a high-value lead arrives.

**As a developer reviewing this portfolio,** I want to see the n8n workflow JSON, the FastAPI code, and the PostgreSQL schema to assess technical depth.

**As a recruiter,** I want to watch a 4-minute video that shows the system working end-to-end and explains the key architecture decisions.

---

## Functional Requirements

### FR-1: Lead Intake
- `POST /api/v1/leads` accepts: `name`, `email`, `company`, `source`, `message` (optional)
- Returns `202 Accepted` with `lead_id`
- Immediately triggers n8n via webhook call from FastAPI
- Request validated with Pydantic model before processing

### FR-2: Lead Enrichment
- n8n calls Apollo.io free tier API to fetch: company size, industry, location, funding stage
- If enrichment fails (rate limit, 404): log warning, continue with available data
- Enrichment result stored in `enrichment_data` table

### FR-3: AI Scoring (Claude)
- n8n calls Claude API (claude-3-5-sonnet) via HTTP Request node
- System prompt defines ICP criteria; user message contains lead + enrichment JSON
- Claude returns structured JSON (enforced via prompt schema):
  ```json
  {
    "score": 82,
    "tier": "A",
    "reasoning": "Company size and industry match ICP. Decision-maker title.",
    "disqualifiers": [],
    "recommended_action": "immediate_outreach",
    "confidence": "high"
  }
  ```
- Tiers: A (score ≥ 70), B (40–69), C (< 40)
- Score + reasoning stored in `ai_scores` table

### FR-4: Lead Routing
- **Tier A:** Slack message to `#hot-leads` with full profile, score, reasoning, and direct CRM link
- **Tier B:** HTTP call to `POST /api/v1/leads/{id}/queue` — added to CRM follow-up queue
- **Tier C:** Stored in DB only. No active notification.
- Routing logic: n8n Switch node (visible and readable in workflow diagram)

### FR-5: Persistence & Audit Trail
- All leads stored in PostgreSQL regardless of score
- Every state transition logged to `lead_events` table: `(lead_id, event_type, timestamp, payload)`
- State machine: `received → enriched → scored → routed`
- Schema exported and documented in GitHub repo

### FR-6: Error Handling
- Failed enrichment: log to `errors` table, set `enrichment_status = 'failed'`, continue
- Failed Claude call: retry 3× with exponential backoff (2s, 4s, 8s); fallback to rule-based score if all fail
- Failed Slack notification: log error, retry once after 5 min via n8n Error Trigger workflow
- n8n Error Trigger workflow: separate workflow that catches all failed executions and writes to `errors` table

### FR-7: Metrics Endpoint
- `GET /api/v1/metrics` returns:
  ```json
  {
    "leads_today": 14,
    "leads_this_week": 67,
    "tier_a": 12,
    "tier_b": 31,
    "tier_c": 24,
    "avg_processing_time_seconds": 18,
    "error_rate": 0.02
  }
  ```

---

## Technical Architecture

```
[Webhook / Form]
      │
      ▼
[FastAPI: POST /leads]  ──── validate (Pydantic) ──── store (PostgreSQL)
      │
      │ trigger via webhook
      ▼
[n8n Workflow: lead-qualification]
      │
      ├─► [HTTP Request: Apollo Enrichment API]
      │         │ success / failure
      │         ▼
      ├─► [HTTP Request: Claude API — Score Lead]
      │         │
      │         ▼
      ├─► [Switch: Route by Tier]
      │     ├─ A → [Slack: #hot-leads]
      │     ├─ B → [HTTP: POST /leads/{id}/queue]
      │     └─ C → [HTTP: POST /leads/{id}/log]
      │
      └─► [HTTP: POST /leads/{id}/events — log final state]

[n8n Error Trigger Workflow] ──► [HTTP: POST /errors — log failure]
```

**Python service files:**
```
lead-qualification-system/
├── main.py
├── routers/
│   ├── leads.py
│   └── metrics.py
├── models/
│   ├── lead.py        # SQLAlchemy
│   └── schemas.py     # Pydantic
├── services/
│   ├── enrichment.py
│   └── n8n_trigger.py
├── db/
│   └── migrations/    # Alembic
├── tests/
│   ├── test_leads.py
│   └── test_metrics.py
├── docker-compose.yml
└── README.md
```

---

## Non-Functional Requirements

| Requirement | Target |
|---|---|
| Webhook → Slack time (happy path) | < 30 seconds |
| FastAPI response time (POST /leads) | < 300ms |
| Test coverage | > 70% |
| Docker Compose: `docker compose up` | Working with no manual steps |

---

## Test Dataset

Seed script with 20 test leads:
- 8 Tier A (large company, right industry, decision-maker email)
- 7 Tier B (partial ICP match)
- 5 Tier C (student email, wrong industry, tiny company)

---

## Success Criteria

- [ ] `docker compose up` starts FastAPI + PostgreSQL locally
- [ ] Sending a test lead via curl triggers full n8n pipeline
- [ ] Claude returns valid JSON for all 20 test leads
- [ ] Slack notification received for all Tier A leads
- [ ] All events logged correctly in PostgreSQL
- [ ] pytest passes with >70% coverage
- [ ] n8n workflow JSON committed to repo (importable)
- [ ] Loom video recorded: 4–5 min, problem → live demo → architecture walkthrough
- [ ] GitHub README: architecture diagram, setup in < 5 commands, design decisions

---

## Key Design Decisions (for Case Study)

**Why FastAPI over Flask?** Async-native, automatic OpenAPI docs, Pydantic integration. More representative of production Python API design.

**Why Claude for scoring instead of rule-based?** Rule-based scoring requires constant maintenance as ICP evolves. Claude can reason about contextual signals (e.g., "VP of Operations at a 50-person SaaS company in fintech") that boolean rules can't capture. Structured output enforces the response format.

**Why n8n instead of pure Python for the pipeline?** n8n makes the workflow visually inspectable. A recruiter or hiring manager can see the flow in a screenshot without reading code. That's a portfolio advantage that pure Python doesn't have.

---
---
