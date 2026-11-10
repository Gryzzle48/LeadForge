<div align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Next.js-14-black?style=flat-square&logo=next.js" alt="Next.js">
  <img src="https://img.shields.io/badge/FastAPI-0.115-green?style=flat-square&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="MIT License">
  <img src="https://img.shields.io/badge/status-active-success?style=flat-square" alt="Status">


  <h1>LocalWeb Leads</h1>
  <p><strong>Find local businesses with no website listed and organize leads in one Google Sheet.</strong></p>
  <p>A LeadForge adaptation for LocalWeb Studio. Search businesses by category and US location, review leads, remove duplicates, and append new records to a permanent Google Sheets tab.</p>

  <p>
    <a href="#features">Features</a> •
    <a href="#quick-start">Quick Start</a> •
    <a href="#deployment">Deployment</a> •
    <a href="#usage">Usage</a> •
    <a href="#api">API Reference</a> •
    <a href="#faq">FAQ</a>
  </p>
</div>

---

## Features

- **Google Places API (New)** — Search businesses by category and US city/state
- **No-Website-Listed Filter** — Keep results where the Places response contains no website field
- **Global Duplicate Prevention** — Deduplicate by Google Place ID across campaigns
- **Google Maps Links** — Keep a direct Maps link for each business
- **Permanent Google Sheets Export** — Append new results to one configured Leads tab
- **Contacts** — Include available phone values; email and Instagram can be added after a separate enrichment stage
- **Background Processing** — Search runs asynchronously; poll campaign status from the dashboard
- **Manual Review** — Review results before exporting; no automated email sending in the LocalWeb workflow
- **CI/CD** — GitHub Actions runs backend + frontend tests on configured pushes and pull requests

## Architecture

```
                  ┌──────────────────────────────────────┐
                  │         Vercel (Frontend)            │
                  │       Next.js 14 Dashboard           │
                  └────────────────┬─────────────────────┘
                                   │ /api/*
                  ┌────────────────▼─────────────────────┐
                  │      Railway.app (Backend)           │
                  │           FastAPI (Python)            │
                  ├──────────────────────────────────────┤
                  │  ┌──────────────────────────────────┐  │
                  │  │ Postgres (Leads + Campaigns)    │  │
                  │  └──────────────────────────────────┘  │
                  └────────────────┬─────────────────────┘
                                   │ HTTP
    ┌──────────────────────────────┼──────────────────────────┐
    │                              │                          │
    ▼                              ▼                          ▼
Google Places API          Google Sheets API          Google Apps Script
(Lead sourcing)            (Export)                   (Email sending)
```

### Data Flow

```
Search Form → POST /api/search → Grid Search (Places API)
    → Filter results with no website field → Dedup by Place ID
    → Review new leads in the dashboard
    → Append campaign results to the permanent Google Sheets Leads tab
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL |
| **Frontend** | Next.js 14, React 18, Tailwind CSS, Framer Motion |
| **Background Tasks** | FastAPI BackgroundTasks (async) |
| **APIs** | Google Places API (New), Google Sheets API v4 |
| **Automation** | Google Apps Script (Gmail send, quota-aware) |
| **Infrastructure** | Railway.app, Vercel, Docker Compose (local dev) |
| **CI/CD** | GitHub Actions (backend + frontend tests on push) |
| **Testing** | pytest (backend), Jest + RTL (frontend) |

## Quick Start

### 1. Enable Google APIs

In [Google Cloud Console](https://console.cloud.google.com/), create a project and enable:

- [Places API (New)](https://console.cloud.google.com/apis/library/places.googleapis.com) — for lead sourcing
- [Sheets API](https://console.cloud.google.com/apis/library/sheets.googleapis.com) — for spreadsheet export

Create an **API key** (for Places API) and a **Service Account JSON key** (for Sheets API).

### 2. Deploy Backend (Railway)

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/leadforge)

Or manually:
1. Fork/clone this repo
2. Create a Railway project → **Deploy from GitHub repo**
3. Add **PostgreSQL** plugin → auto-links `DATABASE_URL`
4. Set env vars:

```env
GOOGLE_MAPS_API_KEY=your_places_api_key
GOOGLE_SERVICE_ACCOUNT_JSON=your_base64_or_raw_json
API_KEY=your_secret_key          # optional — set to enable X-API-Key auth
```

### 3. Deploy Frontend (Vercel)

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/abeermeer/LeadForge&root-directory=frontend)

Set env vars in Vercel:

```env
NEXT_PUBLIC_API_URL=https://your-backend.up.railway.app
NEXT_PUBLIC_API_KEY=your_secret_key   # only if API_KEY is set on backend
```

### 4. Or Run Locally

```bash
git clone https://github.com/abeermeer/LeadForge.git
cd LeadForge
docker compose up -d            # starts Postgres
cd backend && pip install -r requirements.txt
cp .env.example .env            # fill in your keys
uvicorn backend.main:app --reload --port 8000  # terminal 1
cd ../frontend && npm install
npm run dev                     # terminal 2 — http://localhost:3000
```

## Deployment

### Frontend (Vercel)

```bash
cd frontend
npm run build
vercel --prod
```

Set `NEXT_PUBLIC_API_URL` to your Railway backend URL (e.g. `https://leadforge-production-xxxx.up.railway.app`).

### Backend (Railway)

1. Push to GitHub
2. Create a Railway project → "Deploy from GitHub repo" → select `abeermeer/LeadForge`
3. Add **PostgreSQL** plugin (DATABASE_URL auto-injected)
4. Set remaining env vars: `GOOGLE_MAPS_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `API_KEY`
5. Railway builds using the `Dockerfile` at repo root

The included `railway.json` configures Dockerfile builder with 1 replica and ON_FAILURE restart policy.

## Usage

### 1. Search for Leads

Enter a business type (e.g. "restaurant", "dentist", "plumber") and location (e.g. "Austin, TX"). Adjust radius and minimum rating. The engine:

- Subdivides the area into overlapping circles (Places API cap: 60 results per query)
- Searches each circle
- Filters out businesses with a listed website
- Deduplicates against all previous campaigns

### 2. Review & Edit

The results table shows each lead with its generated email. You can edit subject lines and body text inline. Each lead gets a personalized email from a rotating angle bank:

| Vertical | Angles |
|----------|--------|
| **Restaurants / Cafes** | Lost traffic, competition edge, delivery trends |
| **Clinics / Salons** | Trust building, online booking, credibility |
| **Retail / Shops** | Google visibility, Instagram limits, product catalog |
| **Generic** | Missed opportunity, competitor advantage, credibility gap |

### 3. Export

Click "Add to Google Sheets" to append new businesses to the existing spreadsheet ID configured by GOOGLE_SPREADSHEET_ID. The exporter uses one tab (Leads by default), skips records already present, and continues numbering from the highest existing row.

### 4. Review and contact manually

The LocalWeb workflow does not generate or send emails automatically. Review each business and its Maps link, verify whether a website exists, then decide whether to contact the business.

## API Reference

All endpoints (except `/api/health`) require `X-API-Key` header if `API_KEY` is set. POST `/api/search` is rate-limited to 5 requests per minute.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check (no auth required) |
| `POST` | `/api/search` | Create search campaign (rate-limited: 5/min) |
| `GET` | `/api/search/{id}` | Poll campaign status |
| `GET` | `/api/campaigns/{id}/leads` | List leads for campaign |
| `PATCH` | `/api/leads/{id}` | Update lead email fields |
| `POST` | `/api/campaigns/{id}/export` | Export to Google Sheets |

### POST /api/search

```json
{
  "query": "pizza",
  "location": "New York, NY",
  "lat": 40.7128,
  "lng": -74.006,
  "radius": 50000,
  "min_rating": 3.5
}
```

Returns `{"campaign_id": 1, "status": "pending"}`.

### PATCH /api/leads/{id}

Allowlisted fields: `email`, `email_subject`, `email_body`, `angle_used`, `email_status`.

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_MAPS_API_KEY` | Google Places API (New) key | ✅ |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Service account key (base64 or raw JSON) | ✅ |
| `GOOGLE_SPREADSHEET_ID` | ID of the permanent spreadsheet | ✅ |
| `GOOGLE_SHEET_TAB_NAME` | Destination tab name (default: Leads) | No |
| `API_KEY` | API key for auth (set to enable) | ❌ |
| `DATABASE_URL` | PostgreSQL with async driver | ✅ |
| `NEXT_PUBLIC_API_URL` | Backend URL (frontend only) | ✅ |
| `NEXT_PUBLIC_API_KEY` | Must match `API_KEY` for frontend auth (frontend only) | ❌ |

## Project Structure

```
LeadForge/
├── backend/
│   ├── main.py                  # FastAPI entry point
│   ├── config.py                # Environment config
│   ├── auth.py                  # API key authentication + client IP
│   ├── database.py              # SQLAlchemy async engine
│   ├── models/
│   │   ├── campaign.py          # Campaign + CampaignStatus (PENDING/RUNNING/COMPLETED/FAILED)
│   │   ├── lead.py              # Lead table
│   │   └── audit_log.py         # Audit log table
│   ├── routers/
│   │   ├── search.py            # POST /api/search, GET /api/search/{id}, GET /api/campaigns
│   │   ├── leads.py             # GET/PATCH leads, POST regenerate-email
│   │   └── export.py            # POST /api/campaigns/{id}/export
│   ├── workers/
│   │   ├── grid_search.py       # Geocoding + Places API grid search + dedup
│   │   ├── email_writer.py      # Angle bank template engine
│   │   └── sheet_exporter.py    # Google Sheets export
│   ├── templates/               # Angle bank JSON files (restaurant, clinic, retail, generic)
│   └── tests/                   # pytest (12 tests)
├── frontend/
│   ├── pages/
│   │   ├── index.tsx            # Search form + polling
│   │   ├── campaigns/index.tsx  # Campaign history list
│   │   ├── campaigns/[id].tsx   # Campaign detail + results
│   │   └── export/[id].tsx      # Sheets export + Apps Script
│   ├── components/
│   │   ├── Layout.tsx           # Sidebar nav
│   │   ├── SearchForm.tsx       # Search input with filters
│   │   ├── ResultsTable.tsx     # Inline editable leads + regenerate email
│   │   ├── ScriptDisplay.tsx    # Apps Script copy/instructions
│   │   └── StatusBadge.tsx      # Campaign status indicator
│   └── lib/api.ts              # apiFetch wrapper (auto-adds X-API-Key)
├── scripts/
│   └── apps_script.gs
├── .github/workflows/ci.yml    # GitHub Actions (pytest + Jest, Postgres service)
├── docker-compose.yml
├── Dockerfile
├── railway.json
└── .gitignore
```

## Limitations

| Area | Detail |
|------|--------|
| **Gmail quota** | 100 emails/day for free accounts. Google Workspace removes this |
| **Places API cap** | 60 results per query. Grid search covers large areas with overlapping circles |
| **Email discovery** | Google Maps doesn't expose emails. Manual entry may be needed |
| **Places API costs** | Free tier covers ~$200/month usage (~50,000+ text searches) |

## FAQ

**Places API vs scraping?**  
Scraping violates Google ToS, gets IPs banned, and breaks on UI changes. Places API is legal, stable, and returns structured data.

**Do I need an AI key?**  
No. Email generation uses category-specific angle banks with rotating templates. No AI API required.

**How are emails sent?**  
Leads export to Google Sheets → paste the provided Apps Script → run `setupTrigger()`. It sends 8 emails every 20 minutes from your Gmail account.

**Duplicate prevention?**  
Deduplication is enforced at the database level with a unique constraint on Google Place ID. Never contact the same business twice.

**Is this CAN-SPAM compliant?**  
The generated emails include an unsubscribe option and sender identity as a good-faith effort. Consult a legal professional to ensure your specific use case meets compliance requirements.

## License

MIT License — see [LICENSE](LICENSE).

---

<div align="center">
  <sub>Built with Python, Next.js, Google APIs, and ❤️</sub>
</div>
