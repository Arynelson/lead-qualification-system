**Author:** Ary Hauffe Neto

# Project — Lead Qualification System

## What it is
An n8n-based pipeline that ingests inbound leads from multiple sources, enriches them with external data, scores them with AI, and routes qualified leads to CRM with full audit trail.

## Market Context

### Who builds this commercially?
- **Qualified.com** — AI pipeline qualification for enterprise (>$50k/yr contracts)
- **MadKudu** — predictive lead scoring SaaS (Series A, enterprise-focused)
- **Clearbit Reveal** — enrichment + scoring (acquired by HubSpot 2023)
- **n8n templates** — generic "webhook to CRM" templates exist but are shallow
- **Zapier / Make (Integromat)** — can replicate basic routing, but no AI scoring built-in

### What these solutions get wrong
- Qualified and MadKudu are SaaS black boxes — no visibility into scoring logic
- Zapier/Make templates are shallow: no error handling, no retry, no monitoring
- Most open-source alternatives require significant data science expertise to configure
- None of them are designed to be *understood* by a recruiter in 5 minutes

## Differentiation Angle (Portfolio Positioning)
> "Unlike SaaS black boxes, this system is fully transparent and self-hosted. Every scoring decision is logged, every failure is retried with alerting, and the entire workflow is readable in n8n's visual interface."

### What makes this portfolio project stand out
- Built end-to-end by one person (demonstrates full-stack automation skill)
- Real .NET backend, not just n8n alone — shows API design ability
- Explicit error handling and monitoring (most demos skip this entirely)
- Architecture diagram shows employer you think in systems, not just scripts

## Target Employers Who Care About This
- Startups with inbound lead volume > 500/month looking to automate SDR triage
- RevOps teams at Series A–C companies
- n8n consulting firms (Automatisch partners, etc.)
- Companies migrating from Zapier/HubSpot Workflows to self-hosted automation

## Key Messages for Case Study
1. Problem: SDRs spending 40% of their time manually qualifying leads that don't convert
2. Solution: n8n pipeline that handles enrichment, scoring, and routing in under 30 seconds
3. Technical highlight: AI scoring with Claude, not heuristics — adapts to ICP changes
4. Business result: Eliminates ~8 hours/week of manual SDR work per rep

---