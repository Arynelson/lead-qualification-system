# Lead Qualification System

Automated B2B lead qualification pipeline: FastAPI receives inbound leads, n8n enriches them via Apollo.io, scores them with Claude AI, and routes qualified leads to Slack/CRM with a full PostgreSQL audit trail.

> **Portfolio project** by [Ary Hauffe Neto](https://github.com/MakeItBot) — demonstrating production-grade n8n automation + Python FastAPI backend design.

---

## Architecture

```
[Webhook / Form / curl]
        │
        ▼
[FastAPI: POST /api/v1/leads]  ── validate (Pydantic) ── store (PostgreSQL)
        │
        │ trigger via webhook
        ▼
[n8n Workflow: lead-qualification]
        │
        ├─► [HTTP: Apollo.io /v1/people/match]  (continueOnFail)
        │         │ success / failure
        │         ▼
        ├─► [Set: Prepare Lead Data]
        │         │
        │         ▼
        ├─► [HTTP: Claude API — Score Lead]  (retry 3×, backoff 2s)
        │         │
        │         ▼
        ├─► [Code: Parse Claude Response + enrichment]
        │         │
        │         ▼
        ├─► [HTTP: POST /leads/{id}/events — log score]
        │         │
        │         ▼
        ├─► [Switch: Route by Tier (expression)]
        │     ├─ A → [HTTP: Slack #hot-leads]
        │     ├─ B → [HTTP: POST /leads/{id}/queue]
        │     └─ C → [HTTP: POST /leads/{id}/log]
        │               │
        │               ▼
        └─►        [HTTP: POST /leads/{id}/events — log routed]

[n8n Error Trigger Workflow] ──► [HTTP: POST /api/v1/errors]
```

**Scoring tiers:**
- **Tier A** (score ≥ 70): Immediate → Slack `#hot-leads` notification
- **Tier B** (score 40–69): → CRM follow-up queue
- **Tier C** (score < 40): Stored in DB only, no active notification

---

## Quick Start

```bash
git clone https://github.com/MakeItBot/lead-qualification-system
cd lead-qualification-system
cp .env.example .env        # Fill in APOLLO_API_KEY, ANTHROPIC_API_KEY, SLACK_WEBHOOK_URL
docker compose up -d
python scripts/seed.py
```

---

## Setup Steps

### 1. Environment Variables

Copy `.env.example` to `.env` and fill in the required values:

```bash
APOLLO_API_KEY=your_apollo_api_key_here
ANTHROPIC_API_KEY=sk-ant-...
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
```

The rest are pre-configured for Docker Compose and don't need to be changed.

### 2. Run Migrations

Once `docker compose up -d` is running:

```bash
alembic upgrade head
```

### 3. Import n8n Workflows

1. Open n8n at **http://localhost:5678**
2. Go to **Workflows → Import**
3. Import `n8n-workflows/lead-qualification.json`
4. Import `n8n-workflows/error-handler.json`

### 4. Set n8n Environment Variables

In n8n UI: **Settings → Environment Variables** → add:

| Variable | Value |
|---|---|
| `APOLLO_API_KEY` | Your Apollo.io API key |
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `SLACK_WEBHOOK_URL` | Your Slack incoming webhook URL |
| `FASTAPI_INTERNAL_URL` | `http://fastapi:8000` |

### 5. Activate the Workflows

In the n8n UI:
- Open `lead-qualification` → toggle **Active**
- Open `lead-qualification-error-handler` → toggle **Active**
- In `lead-qualification` settings, set **Error Workflow** to `lead-qualification-error-handler`

### 6. Test the Full Pipeline

```bash
curl -X POST http://localhost:8000/api/v1/leads \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Alice VP Sales",
    "email": "alice@techstartup.io",
    "company": "TechStartup Inc",
    "source": "website",
    "message": "We need to automate our SDR process for 500+ leads/month"
  }'
```

Expected: `202 {"lead_id": "...", "status": "received"}` in <300ms, then Slack notification within 30 seconds.

---

## API Reference

### `POST /api/v1/leads`

Ingest a new lead. Validates with Pydantic, stores in PostgreSQL, triggers n8n pipeline.

**Request:**
```json
{
  "name": "Alice Johnson",
  "email": "alice@company.io",
  "company": "TechCo",
  "source": "website",
  "message": "Optional message from the lead"
}
```

**Response** `202 Accepted`:
```json
{"lead_id": "550e8400-e29b-41d4-a716-446655440000", "status": "received"}
```

---

### `POST /api/v1/leads/{lead_id}/queue`

Called by n8n to queue a Tier B lead for CRM follow-up.

**Request:**
```json
{"tier": "B", "score": 55, "reasoning": "Partial ICP match — wrong title"}
```

**Response** `200 OK`: `{"status": "queued"}`

---

### `POST /api/v1/leads/{lead_id}/log`

Called by n8n to log a Tier C lead (stored only, no follow-up).

**Request:**
```json
{"tier": "C", "score": 22}
```

**Response** `200 OK`: `{"status": "logged"}`

---

### `POST /api/v1/leads/{lead_id}/events`

Called by n8n to append a state transition event.

**Request:**
```json
{"event_type": "scored", "payload": {"score": 82, "tier": "A", "confidence": "high"}}
```

**Response** `200 OK`: `{"status": "ok"}`

---

### `POST /api/v1/errors`

Called by n8n Error Trigger to log pipeline failures.

**Request:**
```json
{
  "source": "n8n-error-trigger",
  "error_message": "Apollo API returned 429",
  "lead_id": "550e8400-...",
  "payload": {"workflow_name": "lead-qualification", "last_node": "Apollo Enrichment"}
}
```

**Response** `200 OK`: `{"status": "logged"}`

---

### `GET /api/v1/metrics`

Returns pipeline stats for the dashboard.

**Response** `200 OK`:
```json
{
  "leads_today": 14,
  "leads_this_week": 67,
  "tier_a": 12,
  "tier_b": 31,
  "tier_c": 24,
  "avg_processing_time_seconds": 18.4,
  "error_rate": 0.02
}
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | Python 3.12, FastAPI, Uvicorn |
| Validation | Pydantic v2 with EmailStr |
| ORM | SQLAlchemy 2 (async, asyncpg) |
| Migrations | Alembic (psycopg2 for migrations) |
| Database | PostgreSQL 16 |
| Orchestration | n8n (self-hosted) |
| AI Scoring | Claude API (`claude-3-5-sonnet-20241022`) |
| Enrichment | Apollo.io free tier (`/v1/people/match`) |
| Notifications | Slack Incoming Webhooks |
| Tests | pytest, pytest-asyncio, httpx (ASGITransport) |
| Infrastructure | Docker Compose v2 |

---

## Design Decisions

**Why FastAPI over Flask?**
Async-native, automatic OpenAPI docs at `/docs`, Pydantic integration out of the box. More representative of production Python API design at modern SaaS companies.

**Why Claude for scoring instead of rule-based?**
Rule-based scoring requires constant maintenance as ICP evolves. Claude can reason about contextual signals ("VP of Operations at a 50-person SaaS company in fintech") that boolean rules can't capture. The `Parse Claude Response` Code node also implements a fallback rule-based scorer for when Claude returns malformed JSON, so the pipeline never silently fails.

**Why n8n instead of pure Python for the pipeline?**
n8n makes the workflow visually inspectable. A recruiter or hiring manager can see the flow in a single screenshot without reading code. Every node, connection, and routing rule is visible. That's a portfolio advantage that pure Python orchestration doesn't have. The FastAPI backend handles validation and storage (what it's good at); n8n handles the multi-step async pipeline (what it's good at).

**Why not store enrichment data in a separate DB call from n8n?**
The enrichment data is accessed by the Code node and merged directly into the scoring payload. A separate `POST /enrichment` endpoint would add a network round-trip and a database write before Claude even runs, slowing the pipeline. The current design logs everything via `lead_events` which provides the audit trail without the overhead.

---

## Success Criteria

- [x] `docker compose up` starts FastAPI + PostgreSQL + n8n locally
- [x] Sending a test lead via curl triggers full n8n pipeline
- [x] Claude returns valid JSON for test leads (with fallback for failures)
- [x] Slack notification sent for all Tier A leads
- [x] All events logged correctly in PostgreSQL (`lead_events` table)
- [x] State machine: `received → scored → routed`
- [x] pytest passes with >70% coverage (achieved: 91%)
- [x] n8n workflow JSON committed to repo (importable)
- [ ] Loom video: 4–5 min problem → live demo → architecture walkthrough
- [ ] GitHub README: architecture diagram, setup in 5 commands, design decisions ← you are here

---

## Project Structure

```
lead-qualification-system/
├── main.py                    # FastAPI app entry point
├── routers/
│   ├── leads.py               # POST /leads, /queue, /log, /events, /errors
│   └── metrics.py             # GET /metrics
├── models/
│   ├── lead.py                # SQLAlchemy: leads table
│   ├── enrichment.py          # SQLAlchemy: enrichment_data table
│   ├── ai_score.py            # SQLAlchemy: ai_scores table
│   ├── lead_event.py          # SQLAlchemy: lead_events table
│   ├── error.py               # SQLAlchemy: errors table
│   └── schemas.py             # Pydantic v2 request/response models
├── services/
│   └── n8n_trigger.py         # Fire-and-forget n8n webhook trigger
├── db/
│   ├── database.py            # Async SQLAlchemy engine + session
│   ├── base.py                # DeclarativeBase
│   └── migrations/            # Alembic migrations
│       └── versions/
│           └── 0001_initial_schema.py
├── tests/
│   ├── conftest.py            # SQLite in-memory fixtures
│   ├── test_leads.py          # 9 tests (validation + integration)
│   ├── test_metrics.py        # 2 tests (mocked metrics)
│   └── test_models.py         # 5 tests (schema validation)
├── n8n-workflows/
│   ├── lead-qualification.json       # Main pipeline (import to n8n)
│   └── error-handler.json            # Error trigger workflow
├── scripts/
│   └── seed.py                # 20 test leads across all tiers
├── docker/
│   └── init-postgres.sql      # Creates n8n database on first startup
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── .env.example
```

---

## Troubleshooting

**n8n can't reach FastAPI:**
Make sure `FASTAPI_INTERNAL_URL=http://fastapi:8000` is set in n8n environment variables (not `localhost`). Both services share the same Docker network.

**Claude returns non-JSON:**
The `Parse Claude Response` Code node handles this via fallback rule-based scoring. Check the n8n execution log to see the raw Claude response.

**Apollo 429 (rate limit):**
Apollo free tier allows ~50 enrichments/month. The `Apollo Enrichment` node has `onError: continueRegularOutput` set — the pipeline continues with `"unknown"` for enrichment fields. Claude still scores based on name, email, company, and message.

**Alembic `psycopg2` not found:**
```bash
pip install psycopg2-binary
```
Alembic uses sync psycopg2; the runtime app uses async asyncpg. Both are needed.

**n8n workflow not triggering:**
Ensure the workflow is set to **Active** in the n8n UI. Inactive workflows don't respond to webhook calls.
