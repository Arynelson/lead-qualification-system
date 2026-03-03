from fastapi import FastAPI
from routers import leads, metrics

app = FastAPI(title="Lead Qualification System", version="1.0.0")

app.include_router(leads.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
