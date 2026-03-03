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
            # Fire-and-forget: log but don't fail the API response
            print(f"[WARNING] Failed to trigger n8n: {e}")
