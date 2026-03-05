#!/usr/bin/env python3
"""Seed the database with 20 test leads spanning all tiers.

Usage:
    python scripts/seed.py
    python scripts/seed.py --url http://localhost:8000  # custom base URL
"""
import asyncio
import sys
import httpx

BASE_URL = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--url" else "http://localhost:8000"

TEST_LEADS = [
    # Tier A — 8 leads (large company, right industry, decision-maker title)
    {
        "name": "Sarah Chen",
        "email": "sarah.chen@enterprise-saas.com",
        "company": "EnterpriseSaaS Inc",
        "source": "website",
        "message": "Looking to automate our SDR team of 15 reps. We process 500+ inbound leads/month.",
    },
    {
        "name": "Michael Torres",
        "email": "michael.torres@fintechco.io",
        "company": "FintechCo",
        "source": "linkedin",
        "message": "VP Engineering here. We raised Series B last month and are scaling sales ops.",
    },
    {
        "name": "Jennifer Walsh",
        "email": "jennifer@healthtech-solutions.com",
        "company": "HealthTech Solutions",
        "source": "referral",
        "message": "Head of Revenue Ops. Need to qualify 200 leads/week without adding headcount.",
    },
    {
        "name": "Robert Kim",
        "email": "robert.kim@logisticspro.com",
        "company": "LogisticsPro",
        "source": "conference",
        "message": "Director of Operations. Saw your demo at SaaStr. Very interested.",
    },
    {
        "name": "Amanda Foster",
        "email": "amanda@ecommerce500.com",
        "company": "ECommerce500",
        "source": "website",
    },
    {
        "name": "David Park",
        "email": "david.park@seriesb-startup.com",
        "company": "SeriesB Startup",
        "source": "linkedin",
        "message": "COO. Just raised Series B, scaling our sales ops from 3 to 10 reps.",
    },
    {
        "name": "Lisa Nguyen",
        "email": "lisa@b2bsoftware.com",
        "company": "B2B Software Corp",
        "source": "webinar",
        "message": "Director of Demand Generation. Attended your webinar on lead automation.",
    },
    {
        "name": "James Morrison",
        "email": "james.morrison@saasgrowth.io",
        "company": "SaasGrowth",
        "source": "website",
        "message": "VP Business Development. Growing from 50 to 200 employees this year.",
    },
    # Tier B — 7 leads (partial ICP match — wrong title, wrong industry, or unclear signals)
    {
        "name": "Tom Bradley",
        "email": "tom.bradley@midsize-retail.com",
        "company": "Midsize Retail Co",
        "source": "website",
        "message": "Operations Manager looking for lead management tools.",
    },
    {
        "name": "Karen Mills",
        "email": "karen@creative-agency.com",
        "company": "Creative Marketing Agency",
        "source": "linkedin",
        "message": "Account Manager. We have about 30 clients and need better lead tracking.",
    },
    {
        "name": "Steve Robinson",
        "email": "steve.robinson@oldschool-corp.com",
        "company": "OldSchool Corp",
        "source": "form",
    },
    {
        "name": "Nicole Davis",
        "email": "nicole@services-company.com",
        "company": "Professional Services Co",
        "source": "website",
        "message": "Sales Representative. My manager asked me to evaluate automation tools.",
    },
    {
        "name": "Brian Chang",
        "email": "brian.chang@manufacturing-ltd.com",
        "company": "Manufacturing Ltd",
        "source": "form",
        "message": "Operations lead at a 150-person manufacturing company.",
    },
    {
        "name": "Rachel Green",
        "email": "rachel@mediumbiz-consulting.com",
        "company": "MediumBiz Consulting",
        "source": "website",
    },
    {
        "name": "Carlos Mendez",
        "email": "carlos.mendez@techconsulting.com",
        "company": "Tech Consulting Partners",
        "source": "linkedin",
        "message": "Senior Developer evaluating tools for our clients.",
    },
    # Tier C — 5 leads (student email, wrong industry, tiny company, government)
    {
        "name": "John Smith",
        "email": "john.smith123@gmail.com",
        "company": "N/A",
        "source": "website",
        "message": "Hi, I'm a student studying business automation. This looks cool!",
    },
    {
        "name": "Mary Johnson",
        "email": "mary.johnson@hotmail.com",
        "company": "Local Coffee Shop",
        "source": "form",
        "message": "Small business owner. I have maybe 5 leads per month.",
    },
    {
        "name": "Alex Turner",
        "email": "alex@pixel-games-studio.com",
        "company": "Pixel Games Studio",
        "source": "website",
        "message": "Indie game studio, 8 employees. Looking for any sales tool really.",
    },
    {
        "name": "Pat Rivera",
        "email": "pat.rivera@local-charity.org",
        "company": "Local Community Charity",
        "source": "linkedin",
        "message": "We're a nonprofit looking for free tools to track our donor leads.",
    },
    {
        "name": "Sam Wilson",
        "email": "sam.wilson@citygovernment.gov",
        "company": "City Government Office",
        "source": "form",
        "message": "Municipal employee looking for procurement options.",
    },
]


async def seed(base_url: str = BASE_URL) -> None:
    print(f"Seeding 20 test leads to {base_url}/api/v1/leads")
    print("-" * 60)

    success_count = 0
    fail_count = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, lead in enumerate(TEST_LEADS, 1):
            try:
                response = await client.post(f"{base_url}/api/v1/leads", json=lead)
                if response.status_code == 202:
                    data = response.json()
                    print(f"[{i:02d}/20] OK  — {lead['name']} ({lead['email']}) → lead_id={data.get('lead_id', '?')}")
                    success_count += 1
                else:
                    print(f"[{i:02d}/20] FAIL ({response.status_code}) — {lead['name']} — {response.text[:80]}")
                    fail_count += 1
            except httpx.ConnectError:
                print(f"[{i:02d}/20] ERROR — Cannot connect to {base_url}. Is FastAPI running?")
                fail_count += 1
                break
            except Exception as e:
                print(f"[{i:02d}/20] ERROR — {lead['name']}: {e}")
                fail_count += 1

            # Small delay to avoid overwhelming n8n with concurrent executions
            await asyncio.sleep(0.5)

    print("-" * 60)
    print(f"Done: {success_count} succeeded, {fail_count} failed")
    if success_count > 0:
        print("\nExpected tiers after n8n processing (~30s each):")
        print("  Tier A: 8 leads (sarah, michael, jennifer, robert, amanda, david, lisa, james)")
        print("  Tier B: 7 leads (tom, karen, steve, nicole, brian, rachel, carlos)")
        print("  Tier C: 5 leads (john, mary, alex, pat, sam)")
        print("\nCheck n8n execution history at http://localhost:5678")


if __name__ == "__main__":
    asyncio.run(seed())
