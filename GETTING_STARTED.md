# Getting started

## What you need

- Python 3.11+
- Node.js 18+
- Docker, for the local database
- A Google Cloud API key with **Places API (New)** enabled

Sheets export also needs a service account. See the README for the JSON key, Sheets API, and Drive API.

## Install and run

From the project folder (not from inside `backend`):

```bash
docker compose up -d
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
```

Edit `backend/.env` and paste your Places API key into `GOOGLE_MAPS_API_KEY`.

Terminal 1:

```bash
uvicorn backend.main:app --reload --port 8000
```

Terminal 2:

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000.

## Use it

1. Type a business type and a city, then choose a radius, rating, or review count if you want.
2. Open the leads. These are businesses Google does not list a website for.
3. Export a Google Sheet when you have set `GOOGLE_SERVICE_ACCOUNT_JSON`.
4. Type email addresses into the sheet yourself. The optional script only creates Gmail drafts. You send them.

If a search fails, the page shows the reason. A missing API key, a city Google cannot find, and a Places error are reported instead of returning an empty or wrong list.
