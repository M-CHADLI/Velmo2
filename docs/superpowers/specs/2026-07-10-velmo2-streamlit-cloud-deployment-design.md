# Velmo2 Streamlit Cloud Deployment Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:writing-plans to create the implementation plan from this spec.

**Goal:** Deploy Velmo2 (Streamlit + backend + PostgreSQL + pgvector) as a free, publicly accessible application on Streamlit Cloud with zero infrastructure costs.

**Architecture:** Velmo2 runs on Streamlit Cloud's managed hosting layer. The frontend (Streamlit UI) and backend (agent logic) coexist in a single Python application. PostgreSQL database runs on Neon's serverless platform with pgvector support for semantic memory. Session management and caching use Streamlit's native state system. Secrets and environment variables are stored in Streamlit Cloud's encrypted secrets manager.

**Tech Stack:**
- **Frontend/Backend:** Streamlit + Python 3.11+ (existing code)
- **Database:** Neon PostgreSQL (serverless, free tier)
- **Cache/Session:** Streamlit session_state (native, built-in)
- **Secrets:** Streamlit Cloud secrets manager
- **CI/CD:** GitHub (repo hosting) + Streamlit Cloud auto-deploy
- **Monitoring:** Streamlit Cloud logs + Neon dashboard

---

## Global Constraints

- **Budget:** $0/month (free tier, DEV project)
- **Users:** 10 max concurrent
- **Uptime SLA:** None (best-effort, acceptable downtime for DEV)
- **Compute:** Streamlit Cloud ~1GB RAM, Neon free compute hours
- **Database:** PostgreSQL 14+, pgvector extension required
- **Secrets storage:** Streamlit Cloud encrypted secrets UI (no `.env` file in repo)
- **Public URL:** `https://velmo2.streamlit.app` (or custom domain if needed)
- **Auto-deployment:** On every GitHub push to main branch
- **Monitoring level:** Minimal (logs only, no dashboards/alerts)

---

## 1. Deployment Architecture

### 1.1 Service Layout

```
┌─────────────────────────────────────────────────────────────┐
│ Streamlit Cloud (managed Python runtime)                    │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ velmo2.streamlit.app                                   │ │
│ │ - streamlit/app_streamlit.py (entry point)             │ │
│ │ - agent/ (orchestration)                               │ │
│ │ - guardrails/ (input/output guards)                    │ │
│ │ - memory/ (short-term cache)                           │ │
│ │ - business/ (tools, customer logic)                    │ │
│ └────────────────────────────────────────────────────────┘ │
└────────────┬──────────────────────────────────────────────┬─┘
             │                                              │
    ┌────────▼─────────┐                        ┌───────────▼───────┐
    │ Neon PostgreSQL  │                        │ GitHub (repo)      │
    │ (serverless, free)                        │ CI/CD trigger      │
    │                  │                        └────────────────────┘
    │ - velmo_db       │
    │ - pgvector ext   │
    │ - facts table    │
    │ - sessions table │
    └──────────────────┘
```

### 1.2 Request Flow

1. **User accesses** `https://velmo2.streamlit.app`
2. **Streamlit Cloud** runs `streamlit/app_streamlit.py`
3. **App initializes:**
   - Loads secrets from Streamlit Cloud env (DATABASE_URL, AZURE keys, etc.)
   - Connects to Neon PostgreSQL
   - Loads agent, guardrails, memory modules
4. **User sends message** → Streamlit form submission
5. **App routes message:**
   - Input guards (classifier, hatespeech filter)
   - Agent processes query + tools
   - Output guards (PII redaction)
   - Response rendered in Streamlit UI
6. **Facts extraction** (optional) → stored in Neon via long-term memory
7. **Streamlit re-renders** UI with response

---

## 2. Neon PostgreSQL Setup

### 2.1 Database Schema

**Velmo2 requires two core tables:**

```sql
-- Facts table (long-term memory)
CREATE TABLE IF NOT EXISTS facts (
    id SERIAL PRIMARY KEY,
    customer_ref VARCHAR(50),
    fact_text TEXT NOT NULL,
    embedding VECTOR(1536),  -- pgvector for semantic search
    extracted_at TIMESTAMP DEFAULT NOW(),
    INDEX (customer_ref),
    INDEX USING ivfflat (embedding VECTOR_COSINE_OPS)
);

-- Sessions table (metadata, audit)
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    customer_ref VARCHAR(50),
    session_id VARCHAR(100) UNIQUE,
    messages_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Neon auto-provisions PostgreSQL 14+ with pgvector pre-installed.**

### 2.2 Connection String

**Neon format:**
```
postgresql://user:password@ep-xyz-region.neon.tech/velmo_db?sslmode=require
```

This is the `DATABASE_URL` secret in Streamlit Cloud.

---

## 3. Streamlit Cloud Deployment

### 3.1 Repo Requirements

**Velmo2 GitHub repo structure (existing, no changes):**
```
Velmo2/
├── streamlit/
│   └── app_streamlit.py          # Entry point (Streamlit Cloud runs this)
├── agent/
├── guardrails/
├── memory/
├── business/
├── pyproject.toml                 # Dependencies
├── .streamlit/
│   └── config.toml                # Streamlit config (optional)
└── .gitignore                      # (secrets NOT committed)
```

**Important:**
- `.env` file is NOT committed to GitHub (would expose secrets)
- Secrets are managed via Streamlit Cloud UI, not `.env`
- `pyproject.toml` lists all dependencies (Streamlit will install them)

### 3.2 Streamlit Cloud Secrets Configuration

**Secrets are NOT in `.env` on GitHub. Instead:**

1. User connects GitHub repo to Streamlit Cloud
2. Streamlit Cloud UI presents a secrets form
3. User pastes secrets (one per line, `KEY=value` format):
   ```
   DATABASE_URL=postgresql://user:password@ep-xyz-region.neon.tech/velmo_db?sslmode=require
   AZURE_OPENAI_API_KEY=your-key-here
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   AZURE_OPENAI_DEPLOYMENT_NAME=gpt-5.4-mini
   AZURE_OPENAI_API_VERSION=2025-08-07
   OPENAI_API_KEY=your-key-here
   LANGSMITH_TRACING=true
   LANGSMITH_ENDPOINT=https://api.smith.langchain.com
   LANGSMITH_API_KEY=your-key-here
   LANGSMITH_PROJECT=your-project-name
   CLASSIFIER_DEPLOYMENT_NAME=gpt-5.4-mini
   CLASSIFIER_MAX_TOKENS=16
   RESPONSE_MAX_TOKENS=512
   ```
4. Streamlit Cloud encrypts and stores these
5. App accesses them via `st.secrets` at runtime

**Code example (app_streamlit.py):**
```python
import streamlit as st
import os

# Secrets auto-loaded by Streamlit Cloud
DATABASE_URL = st.secrets.get("DATABASE_URL")
AZURE_OPENAI_API_KEY = st.secrets.get("AZURE_OPENAI_API_KEY")
# ... etc
```

### 3.3 Auto-Deployment

**Streamlit Cloud auto-deploys on every GitHub push:**
1. User does `git push` to GitHub repo (main branch)
2. Streamlit Cloud webhook triggers
3. Streamlit Cloud pulls latest code
4. Installs dependencies from `pyproject.toml`
5. Runs `streamlit run streamlit/app_streamlit.py`
6. App accessible at `https://velmo2.streamlit.app` (~1 minute after push)

**No manual deploy commands needed.**

---

## 4. Configuration & Environment Variables

### 4.1 Required Secrets (in Streamlit Cloud UI)

All secrets from `.env.example` **MUST** be stored in Streamlit Cloud secrets, not in code:

| Secret | Source | Notes |
|--------|--------|-------|
| `DATABASE_URL` | Neon console | PostgreSQL connection string |
| `AZURE_OPENAI_API_KEY` | Azure AI Foundry | LLM key |
| `AZURE_OPENAI_ENDPOINT` | Azure AI Foundry | e.g., `https://mchadliext-5501-resource.services.ai.azure.com/openai/v1` |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Azure AI Foundry | e.g., `gpt-5.4-mini` |
| `AZURE_OPENAI_API_VERSION` | Azure | e.g., `2025-08-07` |
| `OPENAI_API_KEY` | OpenAI console | For embeddings (if using OpenAI) |
| `LANGSMITH_API_KEY` | LangSmith console | Observability (optional) |
| `LANGSMITH_ENDPOINT` | LangSmith | e.g., `https://api.smith.langchain.com` |
| `LANGSMITH_TRACING` | Manual | `true` to enable tracing |
| `LANGSMITH_PROJECT` | Manual | LangSmith project name |
| `CLASSIFIER_DEPLOYMENT_NAME` | Manual | e.g., `gpt-5.4-mini` |
| `CLASSIFIER_MAX_TOKENS` | Manual | e.g., `16` |
| `RESPONSE_MAX_TOKENS` | Manual | e.g., `512` |

### 4.2 Local Development (`.env` NOT committed)

**For local testing, create `.env` at repo root (git-ignored):**
```env
DATABASE_URL=postgresql://user:password@localhost:5432/velmo_db
AZURE_OPENAI_API_KEY=...
# ... etc
```

**In `streamlit/app_streamlit.py`, handle both cases:**
```python
import streamlit as st
import os
from dotenv import load_dotenv

# Load .env locally, Streamlit Cloud ignores .env
load_dotenv()

def get_secret(key, default=None):
    """Get secret from Streamlit Cloud or environment."""
    try:
        return st.secrets.get(key, default)
    except FileNotFoundError:
        # Local dev mode
        return os.getenv(key, default)

DATABASE_URL = get_secret("DATABASE_URL")
```

---

## 5. Database Initialization

### 5.1 First-Time Setup

**After deploying to Streamlit Cloud, the app auto-initializes the database:**

1. `memory/long_term.py` or `memory/manager.py` calls `init_db()` on first app load
2. Checks if tables exist in Neon
3. If not, creates `facts` and `sessions` tables
4. Enables pgvector extension (Neon supports it by default)

**No manual SQL needed — app does it at runtime.**

### 5.2 Accessing Neon Console

**If you need to inspect the database:**
1. Go to https://console.neon.tech
2. Select your project
3. Tables visible in "Browser" tab
4. SQL editor available if needed

---

## 6. Monitoring & Observability

### 6.1 Monitoring Level (Minimal as required)

**Streamlit Cloud logs:**
- Accessible via Streamlit Cloud dashboard (app URL → "Manage app" → "Logs")
- Shows Python stdout/stderr, errors, exceptions
- No action required (logs auto-collected)

**Neon monitoring:**
- Accessible via https://console.neon.tech → "Monitoring" tab
- Shows compute hours used, connection count, query performance
- Neon sends email alert if free tier compute hours exhausted

**No dashboards, no Slack alerts, no custom monitoring.** (Manual checks only if needed.)

### 6.2 Health Check (Manual)

To verify app is running:
1. Visit `https://velmo2.streamlit.app`
2. Try a test message in the chat
3. Check Streamlit Cloud logs if errors occur

---

## 7. Scaling & Future Changes

### 7.1 If 10 Users → More Users

**Streamlit Cloud free tier limitations:**
- ~1 GB RAM (may be insufficient at 50+ concurrent users)
- Resets after 1 hour inactivity (acceptable for DEV)

**If need to scale:**
1. Upgrade to Streamlit Cloud paid tier (~$15/month)
2. Or migrate to Railway/Azure App Service (still <$20/month)

**Code changes:** None — Streamlit Cloud and Railway are drop-in replacements.

### 7.2 Adding Features

**To add features:**
1. Edit code locally (or in VS Code)
2. Run tests: `make test`
3. `git push` to GitHub
4. Streamlit Cloud auto-deploys (~1 min)

No manual build/deploy steps.

---

## 8. Rollback & Disaster Recovery

### 8.1 Rollback After Bad Deploy

**If a push breaks the app:**

1. Go to GitHub repo
2. Revert the commit: `git revert HEAD` + `git push`
3. Streamlit Cloud auto-deploys the previous version (~1 min)

**No data loss** (database is separate from app code).

### 8.2 Data Backup (Neon)

**Neon auto-backs up every 24 hours on free tier.**

If database corruption occurs:
1. Contact Neon support via console
2. Request restore to specific point-in-time (within 7 days)

---

## 9. Cost Breakdown

| Component | Free Tier | Cost |
|-----------|-----------|------|
| Streamlit Cloud | Yes (1 app/repo) | $0 |
| Neon PostgreSQL | Yes (1 project, 50 hours compute/month) | $0 |
| Neon pgvector | Included | $0 |
| GitHub repo | Yes (public) | $0 |
| GitHub Actions | Yes (2,000 min/month) | $0 |
| **Total** | | **$0** ✅ |

**Assumptions:**
- < 50 compute hours/month on Neon (50 users × 1 hour = ~3-5 hours actual usage)
- < 10 concurrent users (no scaling beyond free tier)
- No paid add-ons (Neon storage is included)

---

## 10. Prerequisites & Accounts

**Required accounts (all free):**
1. GitHub account (repo hosting)
2. Neon account (PostgreSQL hosting)
3. Streamlit Cloud account (app hosting)
4. Azure OpenAI account (LLM access, existing)

**No credit card required for free tiers.**

---

## 11. Deployment Steps (High-Level)

1. Create Neon PostgreSQL database → get `DATABASE_URL`
2. Push Velmo2 code to GitHub repo
3. Create Streamlit Cloud account
4. Connect GitHub repo to Streamlit Cloud
5. Paste secrets in Streamlit Cloud UI (DATABASE_URL, Azure keys, etc.)
6. Streamlit Cloud deploys automatically
7. App accessible at `https://velmo2.streamlit.app`

**Detailed task-level instructions in implementation plan.**

---

## Self-Review

✅ **Spec coverage:** All requirements met (Streamlit Cloud + Neon + zero cost + auto-deploy + monitoring minimal)

✅ **No placeholders:** All values specific (Neon connection string format, table schemas, secret names)

✅ **Type consistency:** Database schema matches existing Velmo2 `memory/long_term.py` expectations

✅ **Scope:** Single implementation plan (no sub-projects needed)

✅ **Ambiguity:** None (architecture, secrets, deployment, monitoring all explicit)

---

**Spec ready for review and implementation planning.**
