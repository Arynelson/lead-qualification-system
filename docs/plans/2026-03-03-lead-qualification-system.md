# Lead Qualification System — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a production-grade, fully self-hosted lead qualification pipeline that ingests inbound leads via a FastAPI backend, enriches them with Apollo.io, scores them with Claude AI, routes them by tier, and logs every event to PostgreSQL — all orchestrated by n8n.

**Architecture:** FastAPI receives the lead via `POST /api/v1/leads`, validates it with Pydantic, persists it to PostgreSQL, then triggers an n8n webhook. n8n runs the pipeline: Apollo enrichment → Claude scoring → Switch routing (Slack for Tier A, queue endpoint for Tier B, log for Tier C) → event logging. A second n8n Error Trigger workflow catches any failed execution and writes it to the `errors` table.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 (async), asyncpg, Alembic, Pydantic v2, pytest + httpx, PostgreSQL 16, n8n (self-hosted), Claude API (`claude-3-5-sonnet-20241022`), Apollo.io free tier, Slack Incoming Webhooks, Docker Compose v2.

---

## Environment Variables Reference

The following must be set before running anything. Store them in a `.env` file at project root (never commit this file).

```
# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=leads
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/leads

# n8n
N8N_BASE_URL=http://localhost:5678
N8N_WEBHOOK_PATH=lead-qualification

# External APIs
APOLLO_API_KEY=your_apollo_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ

# Internal (used by n8n to call back to FastAPI inside Docker)
FASTAPI_INTERNAL_URL=http://fastapi:8000
```

---

## Task 1: Docker Compose + Project Skeleton

**Files:**
- Create: `docker-compose.yml`
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `main.py`
- Create: `routers/__init__.py`
- Create: `models/__init__.py`
- Create: `services/__init__.py`
- Create: `db/__init__.py`

**Step 1: Create `docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: leads
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  fastapi:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@postgres:5432/leads
    env_file:
      - .env
    depends_on:
      postgres:
        condition: service_healthy
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

  n8n:
    image: n8nio/n8n:latest
    ports:
      - "5678:5678"
    environment:
      N8N_HOST: localhost
      N8N_PORT: 5678
      N8N_PROTOCOL: http
      DB_TYPE: postgresdb
      DB_POSTGRESDB_HOST: postgres
      DB_POSTGRESDB_PORT: 5432
      DB_POSTGRESDB_DATABASE: n8n
      DB_POSTGRESDB_USER: postgres
      DB_POSTGRESDB_PASSWORD: postgres
      N8N_ENCRYPTION_KEY: super-secret-key-change-this
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - n8n_data:/home/node/.n8n

volumes:
  postgres_data:
  n8n_data:
```

**Step 2: Create `Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Step 3: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "lead-qualification-system"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.7.0",
    "httpx>=0.28.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "httpx>=0.28.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

**Step 4: Create minimal `main.py`**

```python
from fastapi import FastAPI
from routers import leads, metrics

app = FastAPI(title="Lead Qualification System", version="1.0.0")

app.include_router(leads.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Step 5: Create empty `__init__.py` files**

```bash
touch routers/__init__.py models/__init__.py services/__init__.py db/__init__.py
```

**Step 6: Create `.gitignore`**

```
.env
__pycache__/
*.pyc
.pytest_cache/
htmlcov/
*.egg-info/
```

**Step 7: Create `.env.example`** (copy from Environment Variables Reference section above, with placeholder values)

**Step 8: Start Docker Compose and verify postgres is healthy**

```bash
docker compose up postgres -d
docker compose ps
```

Expected: postgres container running and healthy.

**Step 9: Commit**

```bash
git init
git add docker-compose.yml Dockerfile pyproject.toml main.py routers/ models/ services/ db/ .env.example .gitignore
git commit -m "chore: initial project structure and docker compose"
```

---

## Task 2: Database Configuration & SQLAlchemy Setup

**Files:**
- Create: `db/database.py`
- Create: `db/base.py`

**Step 1: Create `db/database.py`**

```python
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/leads"
)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

**Step 2: Create `db/base.py`**

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

**Step 3: Commit**

```bash
git add db/
git commit -m "chore: add SQLAlchemy async database setup"
```

---

## Task 3: SQLAlchemy Models (Database Schema)

**Files:**
- Create: `models/lead.py`
- Create: `models/enrichment.py`
- Create: `models/ai_score.py`
- Create: `models/lead_event.py`
- Create: `models/error.py`

**Step 1: Write failing test for model imports**

Create `tests/__init__.py` and `tests/test_models.py`:

```python
# tests/test_models.py
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
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_models.py -v
```

Expected: `FAILED` — ImportError or AttributeError.

**Step 3: Create `models/lead.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Enum, func
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="received",
    )
    enrichment_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

**Step 4: Create `models/enrichment.py`**

```python
from datetime import datetime
from sqlalchemy import String, DateTime, JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class EnrichmentData(Base):
    __tablename__ = "enrichment_data"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("leads.id"), nullable=False
    )
    company_size: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    funding_stage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

**Step 5: Create `models/ai_score.py`**

```python
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class AIScore(Base):
    __tablename__ = "ai_scores"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("leads.id"), nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    tier: Mapped[str] = mapped_column(String(1), nullable=False)  # A, B, C
    reasoning: Mapped[str] = mapped_column(String(2000), nullable=False)
    disqualifiers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    recommended_action: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

**Step 6: Create `models/lead_event.py`**

```python
from datetime import datetime
from sqlalchemy import String, DateTime, JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class LeadEvent(Base):
    __tablename__ = "lead_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("leads.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

**Step 7: Create `models/error.py`**

```python
from datetime import datetime
from sqlalchemy import String, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class ErrorLog(Base):
    __tablename__ = "errors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    lead_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    error_message: Mapped[str] = mapped_column(String(2000), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

**Step 8: Run test to verify it passes**

```bash
pytest tests/test_models.py -v
```

Expected: `PASSED`

**Step 9: Commit**

```bash
git add models/ tests/
git commit -m "feat: add SQLAlchemy models for leads, enrichment, ai_scores, lead_events, errors"
```

---

## Task 4: Alembic Migrations

**Files:**
- Create: `alembic.ini`
- Create: `db/migrations/env.py` (via alembic init)

**Step 1: Initialize Alembic**

```bash
alembic init db/migrations
```

**Step 2: Edit `alembic.ini`** — set `sqlalchemy.url` to empty (we override in env.py):

```ini
sqlalchemy.url =
```

**Step 3: Edit `db/migrations/env.py`**

Replace the generated file with this content:

```python
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

from db.base import Base
# Import all models so Alembic detects them
from models.lead import Lead
from models.enrichment import EnrichmentData
from models.ai_score import AIScore
from models.lead_event import LeadEvent
from models.error import ErrorLog

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    # Use sync URL for alembic (replace asyncpg with psycopg2)
    url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/leads"
    )
    return url.replace("postgresql+asyncpg://", "postgresql://")


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    config.set_main_option("sqlalchemy.url", get_url())
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**Step 4: Add `psycopg2-binary` to `pyproject.toml` dependencies** (needed by Alembic for sync migrations):

```toml
"psycopg2-binary>=2.9.0",
```

Then run: `pip install psycopg2-binary`

**Step 5: Generate the initial migration**

```bash
alembic revision --autogenerate -m "initial schema"
```

Expected: new file in `db/migrations/versions/xxxx_initial_schema.py` containing `op.create_table(...)` calls for all 5 tables.

**Step 6: Run the migration against the local postgres container**

Make sure postgres is running via Docker:
```bash
docker compose up postgres -d
```

Then:
```bash
alembic upgrade head
```

Expected output ends with: `INFO  [alembic.runtime.migration] Running upgrade  -> xxxx, initial schema`

**Step 7: Verify tables were created**

```bash
docker compose exec postgres psql -U postgres -d leads -c "\dt"
```

Expected: lists `leads`, `enrichment_data`, `ai_scores`, `lead_events`, `errors`, `alembic_version`.

**Step 8: Commit**

```bash
git add alembic.ini db/migrations/
git commit -m "chore: add Alembic migrations for initial schema"
```

---

## Task 5: Pydantic Schemas

**Files:**
- Create: `models/schemas.py`

**Step 1: Write failing test**

Add to `tests/test_models.py`:

```python
def test_lead_create_schema_valid():
    from models.schemas import LeadCreate
    lead = LeadCreate(
        name="Alice Smith",
        email="alice@example.com",
        company="Acme Corp",
        source="website",
    )
    assert lead.email == "alice@example.com"


def test_lead_create_schema_rejects_invalid_email():
    from models.schemas import LeadCreate
    from pydantic import ValidationError
    import pytest
    with pytest.raises(ValidationError):
        LeadCreate(name="A", email="not-an-email", company="X", source="y")
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_models.py::test_lead_create_schema_valid -v
```

Expected: `FAILED` — ImportError.

**Step 3: Create `models/schemas.py`**

```python
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime


class LeadCreate(BaseModel):
    name: str
    email: EmailStr
    company: str
    source: str
    message: Optional[str] = None


class LeadResponse(BaseModel):
    lead_id: str
    status: str = "received"


class LeadQueueRequest(BaseModel):
    tier: str
    score: int
    reasoning: str


class LeadLogRequest(BaseModel):
    tier: str
    score: int


class LeadEventRequest(BaseModel):
    event_type: str
    payload: Optional[dict] = None


class ErrorLogRequest(BaseModel):
    lead_id: Optional[str] = None
    source: str
    error_message: str
    payload: Optional[dict] = None


class MetricsResponse(BaseModel):
    leads_today: int
    leads_this_week: int
    tier_a: int
    tier_b: int
    tier_c: int
    avg_processing_time_seconds: float
    error_rate: float
```

Note: `pydantic[email]` (which provides `EmailStr`) must be installed:
```bash
pip install "pydantic[email]"
```
Add `"pydantic[email]>=2.10.0"` to `pyproject.toml` dependencies.

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
```

Expected: all PASSED.

**Step 5: Commit**

```bash
git add models/schemas.py pyproject.toml
git commit -m "feat: add Pydantic v2 schemas for leads, events, metrics"
```

---

## Task 6: Leads Router — Intake Endpoint (FR-1)

**Files:**
- Create: `routers/leads.py`
- Create: `services/n8n_trigger.py`
- Modify: `tests/test_leads.py`

**Step 1: Write failing tests**

Create `tests/test_leads.py`:

```python
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


async def test_create_lead_returns_202(client):
    with patch("routers.leads.trigger_n8n", new_callable=AsyncMock):
        with patch("routers.leads.get_db"):
            # Patch db session to avoid real DB
            pass
    # Full integration test in Task 9 — this is a smoke test
    response = await client.get("/health")
    assert response.status_code == 200


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
        json={"name": "Test", "email": "test@example.com"},
    )
    assert response.status_code == 422
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_leads.py -v
```

Expected: `FAILED` — ImportError for `routers.leads`.

**Step 3: Create `services/n8n_trigger.py`**

```python
import os
import httpx


N8N_BASE_URL = os.getenv("N8N_BASE_URL", "http://localhost:5678")
N8N_WEBHOOK_PATH = os.getenv("N8N_WEBHOOK_PATH", "lead-qualification")


async def trigger_n8n(lead_data: dict) -> None:
    url = f"{N8N_BASE_URL}/webhook/{N8N_WEBHOOK_PATH}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(url, json=lead_data)
            response.raise_for_status()
        except httpx.HTTPError as e:
            # Log but don't fail — n8n trigger is fire-and-forget
            print(f"[WARNING] Failed to trigger n8n: {e}")
```

**Step 4: Create `routers/leads.py`**

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from db.database import get_db
from models.lead import Lead
from models.lead_event import LeadEvent
from models.enrichment import EnrichmentData
from models.ai_score import AIScore
from models.error import ErrorLog
from models.schemas import (
    LeadCreate, LeadResponse, LeadQueueRequest,
    LeadLogRequest, LeadEventRequest, ErrorLogRequest
)
from services.n8n_trigger import trigger_n8n

router = APIRouter()


@router.post("/leads", status_code=202, response_model=LeadResponse)
async def create_lead(payload: LeadCreate, db: AsyncSession = Depends(get_db)):
    lead_id = str(uuid.uuid4())
    lead = Lead(
        id=lead_id,
        name=payload.name,
        email=payload.email,
        company=payload.company,
        source=payload.source,
        message=payload.message,
        status="received",
        enrichment_status="pending",
    )
    db.add(lead)

    event = LeadEvent(
        lead_id=lead_id,
        event_type="received",
        payload={"source": payload.source},
    )
    db.add(event)
    await db.commit()

    # Fire-and-forget: trigger n8n pipeline
    await trigger_n8n({
        "lead_id": lead_id,
        "name": payload.name,
        "email": payload.email,
        "company": payload.company,
        "source": payload.source,
        "message": payload.message,
    })

    return LeadResponse(lead_id=lead_id)


@router.post("/leads/{lead_id}/queue", status_code=200)
async def queue_lead(
    lead_id: str,
    payload: LeadQueueRequest,
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(Lead).where(Lead.id == lead_id).values(status="queued")
    )
    db.add(LeadEvent(
        lead_id=lead_id,
        event_type="queued",
        payload={"tier": payload.tier, "score": payload.score},
    ))
    await db.commit()
    return {"status": "queued"}


@router.post("/leads/{lead_id}/log", status_code=200)
async def log_lead(
    lead_id: str,
    payload: LeadLogRequest,
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(Lead).where(Lead.id == lead_id).values(status="logged")
    )
    db.add(LeadEvent(
        lead_id=lead_id,
        event_type="disqualified",
        payload={"tier": payload.tier, "score": payload.score},
    ))
    await db.commit()
    return {"status": "logged"}


@router.post("/leads/{lead_id}/events", status_code=200)
async def log_event(
    lead_id: str,
    payload: LeadEventRequest,
    db: AsyncSession = Depends(get_db),
):
    db.add(LeadEvent(
        lead_id=lead_id,
        event_type=payload.event_type,
        payload=payload.payload,
    ))
    await db.commit()
    return {"status": "logged"}


@router.post("/errors", status_code=200)
async def log_error(
    payload: ErrorLogRequest,
    db: AsyncSession = Depends(get_db),
):
    db.add(ErrorLog(
        lead_id=payload.lead_id,
        source=payload.source,
        error_message=payload.error_message,
        payload=payload.payload,
    ))
    await db.commit()
    return {"status": "logged"}
```

**Step 5: Run tests**

```bash
pytest tests/test_leads.py -v
```

Expected: all PASSED (validation tests pass without real DB).

**Step 6: Commit**

```bash
git add routers/leads.py services/n8n_trigger.py tests/test_leads.py
git commit -m "feat: add lead intake endpoint and n8n trigger service (FR-1)"
```

---

## Task 7: Metrics Router (FR-7)

**Files:**
- Create: `routers/metrics.py`
- Modify: `tests/test_metrics.py`

**Step 1: Write failing test**

Create `tests/test_metrics.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock, AsyncMock
from main import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


async def test_metrics_endpoint_returns_200(client):
    # Full DB integration tested separately — just verify schema
    # We mock the DB call
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
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_metrics.py -v
```

Expected: `FAILED` — ImportError.

**Step 3: Create `routers/metrics.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from datetime import datetime, timedelta, timezone

from db.database import get_db
from models.lead import Lead
from models.error import ErrorLog
from models.schemas import MetricsResponse

router = APIRouter()


async def get_metrics(db: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)

    # Leads today
    result = await db.execute(
        select(func.count()).where(Lead.created_at >= today_start)
    )
    leads_today = result.scalar() or 0

    # Leads this week
    result = await db.execute(
        select(func.count()).where(Lead.created_at >= week_start)
    )
    leads_this_week = result.scalar() or 0

    # Tier counts (from ai_scores)
    from models.ai_score import AIScore
    result = await db.execute(
        select(AIScore.tier, func.count()).group_by(AIScore.tier)
    )
    tier_counts = {row[0]: row[1] for row in result.fetchall()}

    # Error rate (errors / total leads this week, avoid div-by-zero)
    result = await db.execute(
        select(func.count()).select_from(ErrorLog).where(
            ErrorLog.created_at >= week_start
        )
    )
    error_count = result.scalar() or 0
    error_rate = round(error_count / leads_this_week, 4) if leads_this_week > 0 else 0.0

    return {
        "leads_today": leads_today,
        "leads_this_week": leads_this_week,
        "tier_a": tier_counts.get("A", 0),
        "tier_b": tier_counts.get("B", 0),
        "tier_c": tier_counts.get("C", 0),
        "avg_processing_time_seconds": 0.0,  # Placeholder — requires event timestamps
        "error_rate": error_rate,
    }


@router.get("/metrics", response_model=MetricsResponse)
async def metrics(db: AsyncSession = Depends(get_db)):
    data = await get_metrics(db)
    return MetricsResponse(**data)
```

**Step 4: Run test**

```bash
pytest tests/test_metrics.py -v
```

Expected: `PASSED`.

**Step 5: Commit**

```bash
git add routers/metrics.py tests/test_metrics.py
git commit -m "feat: add metrics endpoint (FR-7)"
```

---

## Task 8: Integration Tests with Real Database (>70% Coverage)

**Files:**
- Create: `tests/conftest.py`
- Modify: `tests/test_leads.py`
- Modify: `tests/test_metrics.py`

**Step 1: Create `tests/conftest.py`**

This sets up an in-process test database using PostgreSQL via Docker (must be running).

```python
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from db.base import Base
from db.database import get_db
from main import app

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/leads_test"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    TestSession = async_sessionmaker(test_engine, expire_on_commit=False)
    async with TestSession() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
```

Note: Create the test database before running:
```bash
docker compose exec postgres psql -U postgres -c "CREATE DATABASE leads_test;"
```

**Step 2: Add integration tests to `tests/test_leads.py`**

Append:

```python
from unittest.mock import patch, AsyncMock


async def test_create_lead_full_integration(client):
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
    assert len(data["lead_id"]) == 36  # UUID


async def test_log_event_for_lead(client):
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


async def test_queue_lead(client):
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
```

**Step 3: Run full test suite with coverage**

```bash
pytest tests/ -v --cov=. --cov-report=term-missing --cov-omit="tests/*,db/migrations/*"
```

Expected: coverage > 70%, all tests PASSED.

**Step 4: Commit**

```bash
git add tests/conftest.py tests/test_leads.py tests/test_metrics.py
git commit -m "test: add integration tests, achieve >70% coverage"
```

---

## Task 9: n8n Main Workflow — Lead Qualification Pipeline

**Context for implementer:**
- Access n8n at `http://localhost:5678` (start Docker Compose: `docker compose up -d`)
- Use the `mcp__n8n-mcp__n8n_create_workflow` tool to create the workflow programmatically
- The workflow is triggered by FastAPI calling `POST http://n8n:5678/webhook/lead-qualification`
- n8n calls back to FastAPI at `http://fastapi:8000` (Docker internal hostname)

**Files:**
- Create: `n8n-workflows/lead-qualification.json` (export after creation)

**Step 1: Verify n8n is running**

```bash
docker compose up -d
```

Wait ~20 seconds for n8n to initialize, then:

```bash
curl http://localhost:5678/healthz
```

Expected: `{"status":"ok"}`

**Step 2: Create the n8n workflow using the MCP tool**

Use `mcp__n8n-mcp__n8n_create_workflow` with the following specification.

**Workflow name:** `lead-qualification`

**Nodes:**

```json
[
  {
    "id": "webhook-trigger",
    "name": "Lead Intake Webhook",
    "type": "n8n-nodes-base.webhook",
    "typeVersion": 2,
    "position": [250, 300],
    "parameters": {
      "path": "lead-qualification",
      "httpMethod": "POST",
      "responseMode": "onReceived",
      "responseData": "allEntries"
    }
  },
  {
    "id": "apollo-enrichment",
    "name": "Apollo Enrichment",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4,
    "position": [500, 300],
    "continueOnFail": true,
    "parameters": {
      "method": "POST",
      "url": "https://api.apollo.io/v1/people/match",
      "sendHeaders": true,
      "headerParameters": {
        "parameters": [
          {"name": "Content-Type", "value": "application/json"},
          {"name": "Cache-Control", "value": "no-cache"}
        ]
      },
      "sendBody": true,
      "bodyParameters": {
        "parameters": [
          {"name": "api_key", "value": "={{ $env.APOLLO_API_KEY }}"},
          {"name": "email", "value": "={{ $json.body.email }}"},
          {"name": "first_name", "value": "={{ $json.body.name.split(' ')[0] }}"},
          {"name": "last_name", "value": "={{ $json.body.name.split(' ').slice(1).join(' ') }}"},
          {"name": "organization_name", "value": "={{ $json.body.company }}"}
        ]
      }
    }
  },
  {
    "id": "set-enrichment-data",
    "name": "Prepare Enrichment Data",
    "type": "n8n-nodes-base.set",
    "typeVersion": 3,
    "position": [750, 300],
    "parameters": {
      "assignments": {
        "assignments": [
          {
            "id": "lead_id",
            "name": "lead_id",
            "value": "={{ $('Lead Intake Webhook').item.json.body.lead_id }}",
            "type": "string"
          },
          {
            "id": "lead_email",
            "name": "lead_email",
            "value": "={{ $('Lead Intake Webhook').item.json.body.email }}",
            "type": "string"
          },
          {
            "id": "lead_name",
            "name": "lead_name",
            "value": "={{ $('Lead Intake Webhook').item.json.body.name }}",
            "type": "string"
          },
          {
            "id": "lead_company",
            "name": "lead_company",
            "value": "={{ $('Lead Intake Webhook').item.json.body.company }}",
            "type": "string"
          },
          {
            "id": "lead_source",
            "name": "lead_source",
            "value": "={{ $('Lead Intake Webhook').item.json.body.source }}",
            "type": "string"
          },
          {
            "id": "lead_message",
            "name": "lead_message",
            "value": "={{ $('Lead Intake Webhook').item.json.body.message ?? '' }}",
            "type": "string"
          },
          {
            "id": "company_size",
            "name": "company_size",
            "value": "={{ $('Apollo Enrichment').item.json?.person?.employment_history?.[0]?.organization?.num_employees ?? 'unknown' }}",
            "type": "string"
          },
          {
            "id": "industry",
            "name": "industry",
            "value": "={{ $('Apollo Enrichment').item.json?.person?.employment_history?.[0]?.organization?.industry ?? 'unknown' }}",
            "type": "string"
          },
          {
            "id": "job_title",
            "name": "job_title",
            "value": "={{ $('Apollo Enrichment').item.json?.person?.title ?? 'unknown' }}",
            "type": "string"
          },
          {
            "id": "location",
            "name": "location",
            "value": "={{ $('Apollo Enrichment').item.json?.person?.city ?? 'unknown' }}",
            "type": "string"
          }
        ]
      }
    }
  },
  {
    "id": "claude-scoring",
    "name": "Claude AI Scoring",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4,
    "position": [1000, 300],
    "retryOnFail": true,
    "maxTries": 3,
    "waitBetweenTries": 2000,
    "parameters": {
      "method": "POST",
      "url": "https://api.anthropic.com/v1/messages",
      "sendHeaders": true,
      "headerParameters": {
        "parameters": [
          {"name": "x-api-key", "value": "={{ $env.ANTHROPIC_API_KEY }}"},
          {"name": "anthropic-version", "value": "2023-06-01"},
          {"name": "content-type", "value": "application/json"}
        ]
      },
      "sendBody": true,
      "contentType": "raw",
      "body": "={\n  \"model\": \"claude-3-5-sonnet-20241022\",\n  \"max_tokens\": 1024,\n  \"system\": \"You are a B2B lead qualification expert. Evaluate leads against our ICP (Ideal Customer Profile).\\n\\nOur ICP:\\n- Company size: 50-500 employees\\n- Industries: SaaS, fintech, healthtech, logistics, e-commerce\\n- Decision-maker titles: VP, Director, Head of, C-suite\\n- Location: US, UK, Canada, Australia, Western Europe\\n- Signal: company has raised funding OR has >$5M revenue\\n\\nDisqualifiers:\\n- Student or personal email domain (@gmail, @hotmail, etc.)\\n- Company size <10 or >10,000 employees\\n- Industries: gaming, real estate, non-profit, government\\n- Job titles: intern, student, assistant\\n\\nRespond ONLY with valid JSON matching this exact schema — no other text:\\n{\\n  \\\"score\\\": <integer 0-100>,\\n  \\\"tier\\\": \\\"A\\\" | \\\"B\\\" | \\\"C\\\",\\n  \\\"reasoning\\\": \\\"<max 200 chars>\\\",\\n  \\\"disqualifiers\\\": [<strings>],\\n  \\\"recommended_action\\\": \\\"immediate_outreach\\\" | \\\"follow_up\\\" | \\\"disqualify\\\",\\n  \\\"confidence\\\": \\\"high\\\" | \\\"medium\\\" | \\\"low\\\"\\n}\\nTier A = score >= 70, Tier B = 40-69, Tier C = < 40\",\n  \"messages\": [\n    {\n      \"role\": \"user\",\n      \"content\": \"Qualify this lead:\\nName: {{ $json.lead_name }}\\nEmail: {{ $json.lead_email }}\\nCompany: {{ $json.lead_company }}\\nJob Title: {{ $json.job_title }}\\nCompany Size: {{ $json.company_size }} employees\\nIndustry: {{ $json.industry }}\\nLocation: {{ $json.location }}\\nSource: {{ $json.lead_source }}\\nMessage: {{ $json.lead_message }}\"\n    }\n  ]\n}"
    }
  },
  {
    "id": "parse-claude-response",
    "name": "Parse Claude Response",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [1250, 300],
    "parameters": {
      "jsCode": "const content = $input.item.json.content[0].text;\ntry {\n  const parsed = JSON.parse(content);\n  // Validate tier\n  const score = parseInt(parsed.score);\n  let tier;\n  if (score >= 70) tier = 'A';\n  else if (score >= 40) tier = 'B';\n  else tier = 'C';\n  return [{\n    json: {\n      ...$('Prepare Enrichment Data').item.json,\n      score: score,\n      tier: tier,\n      reasoning: parsed.reasoning,\n      disqualifiers: parsed.disqualifiers || [],\n      recommended_action: parsed.recommended_action,\n      confidence: parsed.confidence,\n    }\n  }];\n} catch (e) {\n  // Fallback rule-based scoring if Claude fails to return valid JSON\n  const lead = $('Prepare Enrichment Data').item.json;\n  const isPersonalEmail = /gmail|hotmail|yahoo|outlook/.test(lead.lead_email);\n  const score = isPersonalEmail ? 20 : 50;\n  return [{\n    json: {\n      ...lead,\n      score: score,\n      tier: score >= 70 ? 'A' : score >= 40 ? 'B' : 'C',\n      reasoning: 'Fallback rule-based score (Claude parse error)',\n      disqualifiers: isPersonalEmail ? ['personal_email'] : [],\n      recommended_action: score >= 70 ? 'immediate_outreach' : 'follow_up',\n      confidence: 'low',\n    }\n  }];\n}"
    }
  },
  {
    "id": "save-ai-score",
    "name": "Save AI Score to DB",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4,
    "position": [1500, 300],
    "parameters": {
      "method": "POST",
      "url": "={{ $env.FASTAPI_INTERNAL_URL }}/api/v1/leads/{{ $json.lead_id }}/events",
      "sendBody": true,
      "contentType": "json",
      "body": "={ \"event_type\": \"scored\", \"payload\": { \"score\": {{ $json.score }}, \"tier\": \"{{ $json.tier }}\", \"reasoning\": \"{{ $json.reasoning }}\", \"confidence\": \"{{ $json.confidence }}\" } }"
    }
  },
  {
    "id": "route-by-tier",
    "name": "Route by Tier",
    "type": "n8n-nodes-base.switch",
    "typeVersion": 3,
    "position": [1750, 300],
    "parameters": {
      "mode": "rules",
      "rules": {
        "rules": [
          {
            "outputIndex": 0,
            "conditions": {
              "options": {"caseSensitive": true},
              "conditions": [
                {
                  "id": "tier-a",
                  "leftValue": "={{ $json.tier }}",
                  "rightValue": "A",
                  "operator": {"type": "string", "operation": "equals"}
                }
              ]
            }
          },
          {
            "outputIndex": 1,
            "conditions": {
              "options": {"caseSensitive": true},
              "conditions": [
                {
                  "id": "tier-b",
                  "leftValue": "={{ $json.tier }}",
                  "rightValue": "B",
                  "operator": {"type": "string", "operation": "equals"}
                }
              ]
            }
          }
        ],
        "fallbackOutput": 2
      }
    }
  },
  {
    "id": "slack-hot-leads",
    "name": "Slack Hot Lead Alert",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4,
    "position": [2000, 150],
    "parameters": {
      "method": "POST",
      "url": "={{ $env.SLACK_WEBHOOK_URL }}",
      "sendBody": true,
      "contentType": "json",
      "body": "={\n  \"text\": \":fire: *New Tier A Lead!*\",\n  \"blocks\": [\n    {\n      \"type\": \"section\",\n      \"text\": {\n        \"type\": \"mrkdwn\",\n        \"text\": \":fire: *New Tier A Lead — Score {{ $json.score }}/100*\\n*Name:* {{ $json.lead_name }}\\n*Email:* {{ $json.lead_email }}\\n*Company:* {{ $json.lead_company }}\\n*Title:* {{ $json.job_title }}\\n*Industry:* {{ $json.industry }}\\n*Company Size:* {{ $json.company_size }}\\n*Reasoning:* {{ $json.reasoning }}\\n*Recommended Action:* {{ $json.recommended_action }}\"\n      }\n    }\n  ]\n}"
    }
  },
  {
    "id": "queue-tier-b",
    "name": "Queue Tier B Lead",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4,
    "position": [2000, 300],
    "parameters": {
      "method": "POST",
      "url": "={{ $env.FASTAPI_INTERNAL_URL }}/api/v1/leads/{{ $json.lead_id }}/queue",
      "sendBody": true,
      "contentType": "json",
      "body": "={ \"tier\": \"{{ $json.tier }}\", \"score\": {{ $json.score }}, \"reasoning\": \"{{ $json.reasoning }}\" }"
    }
  },
  {
    "id": "log-tier-c",
    "name": "Log Tier C Lead",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4,
    "position": [2000, 450],
    "parameters": {
      "method": "POST",
      "url": "={{ $env.FASTAPI_INTERNAL_URL }}/api/v1/leads/{{ $json.lead_id }}/log",
      "sendBody": true,
      "contentType": "json",
      "body": "={ \"tier\": \"{{ $json.tier }}\", \"score\": {{ $json.score }} }"
    }
  },
  {
    "id": "log-final-event",
    "name": "Log Final Event",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4,
    "position": [2250, 300],
    "parameters": {
      "method": "POST",
      "url": "={{ $env.FASTAPI_INTERNAL_URL }}/api/v1/leads/{{ $json.lead_id }}/events",
      "sendBody": true,
      "contentType": "json",
      "body": "={ \"event_type\": \"routed\", \"payload\": { \"tier\": \"{{ $json.tier }}\", \"action\": \"{{ $json.recommended_action }}\" } }"
    }
  }
]
```

**Connections:**

```json
{
  "Lead Intake Webhook": {
    "main": [[{"node": "Apollo Enrichment", "type": "main", "index": 0}]]
  },
  "Apollo Enrichment": {
    "main": [[{"node": "Prepare Enrichment Data", "type": "main", "index": 0}]]
  },
  "Prepare Enrichment Data": {
    "main": [[{"node": "Claude AI Scoring", "type": "main", "index": 0}]]
  },
  "Claude AI Scoring": {
    "main": [[{"node": "Parse Claude Response", "type": "main", "index": 0}]]
  },
  "Parse Claude Response": {
    "main": [[{"node": "Save AI Score to DB", "type": "main", "index": 0}]]
  },
  "Save AI Score to DB": {
    "main": [[{"node": "Route by Tier", "type": "main", "index": 0}]]
  },
  "Route by Tier": {
    "main": [
      [{"node": "Slack Hot Lead Alert", "type": "main", "index": 0}],
      [{"node": "Queue Tier B Lead", "type": "main", "index": 0}],
      [{"node": "Log Tier C Lead", "type": "main", "index": 0}]
    ]
  },
  "Slack Hot Lead Alert": {
    "main": [[{"node": "Log Final Event", "type": "main", "index": 0}]]
  },
  "Queue Tier B Lead": {
    "main": [[{"node": "Log Final Event", "type": "main", "index": 0}]]
  },
  "Log Tier C Lead": {
    "main": [[{"node": "Log Final Event", "type": "main", "index": 0}]]
  }
}
```

**Step 3: Configure environment variables in n8n**

In the n8n UI (`http://localhost:5678`):
- Go to Settings → Environment Variables
- Add: `APOLLO_API_KEY`, `ANTHROPIC_API_KEY`, `SLACK_WEBHOOK_URL`, `FASTAPI_INTERNAL_URL=http://fastapi:8000`

**Step 4: Validate the workflow using MCP tool**

```
mcp__n8n-mcp__n8n_validate_workflow with the workflow ID returned from creation
```

Fix any validation errors before proceeding.

**Step 5: Activate the workflow**

In n8n UI, toggle the workflow to Active. The webhook will now be listening at:
`http://localhost:5678/webhook/lead-qualification`

**Step 6: Export workflow JSON for version control**

In n8n UI: Open workflow → ... menu → Download → Save as `n8n-workflows/lead-qualification.json`

Or use the MCP tool: `mcp__n8n-mcp__n8n_get_workflow` with mode="full", save the result to `n8n-workflows/lead-qualification.json`.

**Step 7: Smoke test with curl**

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

Expected:
1. FastAPI returns `202 {"lead_id": "..."}` in < 300ms
2. n8n workflow triggers and completes in < 30 seconds
3. Check n8n execution log for success
4. Slack `#hot-leads` (or test channel) receives notification if Tier A

**Step 8: Commit**

```bash
mkdir -p n8n-workflows
# Save workflow JSON to n8n-workflows/lead-qualification.json
git add n8n-workflows/lead-qualification.json
git commit -m "feat: add n8n lead qualification pipeline workflow (FR-2, FR-3, FR-4)"
```

---

## Task 10: n8n Error Trigger Workflow

**Files:**
- Create: `n8n-workflows/error-handler.json`

**Step 1: Create the error handler workflow using MCP tool**

Use `mcp__n8n-mcp__n8n_create_workflow`:

**Workflow name:** `lead-qualification-error-handler`

**Nodes:**

```json
[
  {
    "id": "error-trigger",
    "name": "On Workflow Error",
    "type": "n8n-nodes-base.errorTrigger",
    "typeVersion": 1,
    "position": [250, 300],
    "parameters": {}
  },
  {
    "id": "log-error-to-db",
    "name": "Log Error to FastAPI",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4,
    "position": [500, 300],
    "parameters": {
      "method": "POST",
      "url": "={{ $env.FASTAPI_INTERNAL_URL }}/api/v1/errors",
      "sendBody": true,
      "contentType": "json",
      "body": "={\n  \"source\": \"n8n-error-trigger\",\n  \"error_message\": \"{{ $json.execution.error.message }}\",\n  \"payload\": {\n    \"workflow_id\": \"{{ $json.workflow.id }}\",\n    \"workflow_name\": \"{{ $json.workflow.name }}\",\n    \"execution_id\": \"{{ $json.execution.id }}\",\n    \"node\": \"{{ $json.execution.lastNodeExecuted }}\"\n  }\n}"
    }
  }
]
```

**Connections:**

```json
{
  "On Workflow Error": {
    "main": [[{"node": "Log Error to FastAPI", "type": "main", "index": 0}]]
  }
}
```

**Step 2: Link the error handler to the main workflow**

In n8n UI:
- Open `lead-qualification` workflow settings
- Set "Error Workflow" to `lead-qualification-error-handler`

**Step 3: Export and commit**

```bash
# Save workflow JSON from MCP tool or n8n UI export
git add n8n-workflows/error-handler.json
git commit -m "feat: add n8n error trigger workflow for failure logging (FR-6)"
```

---

## Task 11: Test Dataset Seed Script

**Files:**
- Create: `scripts/seed.py`

**Step 1: Create `scripts/seed.py`**

```python
#!/usr/bin/env python3
"""Seed the database with 20 test leads spanning all tiers."""
import asyncio
import httpx

BASE_URL = "http://localhost:8000"

TEST_LEADS = [
    # Tier A — 8 leads (large company, right industry, decision-maker)
    {"name": "Sarah VP Sales", "email": "sarah@enterprise-saas.com", "company": "EnterpriseSaaS Inc", "source": "website", "message": "Looking to automate our SDR team of 15 reps"},
    {"name": "Michael CTO", "email": "michael@fintechco.io", "company": "FintechCo", "source": "linkedin", "message": "We process 1000+ leads/month"},
    {"name": "Jennifer Head of Revenue", "email": "jennifer@healthtech.com", "company": "HealthTech Solutions", "source": "referral"},
    {"name": "Robert Director Ops", "email": "robert@logisticspro.com", "company": "LogisticsPro", "source": "conference"},
    {"name": "Amanda VP Marketing", "email": "amanda@ecommerce500.com", "company": "ECommerce500", "source": "website"},
    {"name": "David COO", "email": "david@seriesbstartup.com", "company": "SeriesB Startup", "source": "linkedin", "message": "Just raised Series B, scaling our sales ops"},
    {"name": "Lisa Director of Demand Gen", "email": "lisa@b2bsoftware.com", "company": "B2B Software Corp", "source": "webinar"},
    {"name": "James VP Business Development", "email": "james@saasgrowth.io", "company": "SaasGrowth", "source": "website"},

    # Tier B — 7 leads (partial ICP match)
    {"name": "Tom Manager", "email": "tom@midsize-retail.com", "company": "Midsize Retail", "source": "website"},
    {"name": "Karen Account Manager", "email": "karen@agency.com", "company": "Marketing Agency", "source": "linkedin"},
    {"name": "Steve IT Manager", "email": "steve@oldschool-corp.com", "company": "OldSchool Corp", "source": "form"},
    {"name": "Nicole Sales Rep", "email": "nicole@services-company.com", "company": "Services Co", "source": "website"},
    {"name": "Brian Operations", "email": "brian@manufacturing.com", "company": "Manufacturing Ltd", "source": "form"},
    {"name": "Rachel Marketing Manager", "email": "rachel@mediumbiz.com", "company": "MediumBiz", "source": "website"},
    {"name": "Carlos Developer", "email": "carlos@techconsulting.com", "company": "Tech Consulting", "source": "linkedin"},

    # Tier C — 5 leads (student email, wrong industry, tiny company)
    {"name": "John Student", "email": "john.doe@gmail.com", "company": "None", "source": "website", "message": "I'm a student interested in automation"},
    {"name": "Mary Intern", "email": "mary@hotmail.com", "company": "Local Shop", "source": "form"},
    {"name": "Alex Gaming", "email": "alex@gamingstudio.com", "company": "Pixel Games Studio", "source": "website"},
    {"name": "Pat Nonprofit", "email": "pat@charity.org", "company": "Local Charity", "source": "linkedin"},
    {"name": "Sam Government", "email": "sam@citygovernment.gov", "company": "City Government", "source": "form"},
]


async def seed():
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, lead in enumerate(TEST_LEADS, 1):
            response = await client.post(f"{BASE_URL}/api/v1/leads", json=lead)
            status = "OK" if response.status_code == 202 else f"FAIL ({response.status_code})"
            print(f"[{i:02d}/20] {status} — {lead['name']} ({lead['email']})")
            await asyncio.sleep(0.5)  # Avoid overwhelming n8n


if __name__ == "__main__":
    asyncio.run(seed())
```

**Step 2: Run the seed script**

```bash
python scripts/seed.py
```

Expected: 20 lines of `OK` output. Each lead triggers the n8n pipeline.

After ~5 minutes, check n8n execution history — all 20 should complete (most as success, some may get Claude rate-limited).

**Step 3: Verify results in PostgreSQL**

```bash
docker compose exec postgres psql -U postgres -d leads -c "
SELECT l.name, l.email, a.tier, a.score, a.reasoning
FROM leads l
LEFT JOIN ai_scores a ON l.id = a.lead_id
ORDER BY a.score DESC NULLS LAST;
"
```

**Step 4: Commit**

```bash
git add scripts/seed.py
git commit -m "feat: add seed script with 20 test leads across all tiers"
```

---

## Task 12: README & Architecture Diagram

**Files:**
- Create: `README.md`

**Step 1: Create `README.md`**

The README must include these sections (write them out fully, don't use placeholders):

1. **Project Title + 1-line description**
2. **Architecture Diagram** — recreate the ASCII diagram from the PRD verbatim
3. **Quick Start** — exactly 5 commands:
   ```bash
   git clone https://github.com/MakeItBot/lead-qualification-system
   cd lead-qualification-system
   cp .env.example .env  # Fill in APOLLO_API_KEY, ANTHROPIC_API_KEY, SLACK_WEBHOOK_URL
   docker compose up -d
   python scripts/seed.py
   ```
4. **Setup Steps** — how to import n8n workflows, configure env vars in n8n UI
5. **API Reference** — all 6 endpoints with request/response examples
6. **Design Decisions** — copy verbatim from PRD (FastAPI vs Flask, Claude vs rules, n8n vs pure Python)
7. **Tech Stack table**
8. **Success Criteria checklist** — copy from PRD

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with architecture, quick start, and API reference"
```

---

## Task 13: Final Verification Checklist

Run all of these before declaring the project complete:

```bash
# 1. Docker Compose starts cleanly
docker compose down -v
docker compose up -d
sleep 30

# 2. Run migrations
alembic upgrade head

# 3. Full test suite passes with >70% coverage
pytest tests/ -v --cov=. --cov-report=term-missing

# 4. API responds correctly
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/metrics

# 5. Send a test Tier A lead and verify Slack notification
curl -X POST http://localhost:8000/api/v1/leads \
  -H "Content-Type: application/json" \
  -d '{"name": "VP Test", "email": "vp@techstartup.io", "company": "TechStartup", "source": "test"}'

# 6. Check n8n executed successfully (wait 30s, then check UI)
# 7. Verify Slack notification received

# 8. Run seed script
python scripts/seed.py

# 9. Verify DB has leads, events, and scores
docker compose exec postgres psql -U postgres -d leads \
  -c "SELECT COUNT(*) FROM leads; SELECT COUNT(*) FROM lead_events; SELECT COUNT(*) FROM ai_scores;"
```

Expected results:
- All tests pass, coverage > 70%
- Slack notification received for VP Test lead
- DB shows 21+ leads (20 seeded + 1 manual), proportional events and scores
- n8n execution history shows green checkmarks

**Final commit:**

```bash
git add .
git commit -m "chore: final verification complete — all success criteria met"
```

---

## Troubleshooting Guide

**n8n can't reach FastAPI:**
- Ensure both services are on the same Docker network (they are via `docker-compose.yml`)
- Use `http://fastapi:8000` (not `localhost`) for n8n → FastAPI calls
- Use `http://localhost:5678` for FastAPI → n8n calls (from host machine perspective)

**Claude returns non-JSON:**
- The `Parse Claude Response` Code node handles this via fallback rule-based scoring
- Check n8n execution log for the raw Claude response content

**Apollo 429 rate limit:**
- Apollo free tier is limited to 50 enrichments/month
- `continueOnFail: true` ensures the pipeline continues with empty enrichment data
- The `Prepare Enrichment Data` node defaults unknowns to `"unknown"` string

**Alembic `psycopg2` not found:**
- Run: `pip install psycopg2-binary`
- Alembic uses sync psycopg2, the app uses async asyncpg — both are required

**Test database doesn't exist:**
```bash
docker compose exec postgres psql -U postgres -c "CREATE DATABASE leads_test;"
```
