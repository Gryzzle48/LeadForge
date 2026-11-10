# Getting started

The short way: install Docker, then run `./start.sh` (Windows: `start.bat`). That starts the database, the maps scraper, the API, and the website, and opens http://localhost:3000. Stop with `./stop.sh` or `stop.bat`.

## What you need

- Docker
- Python 3.11+
- Node.js 18+

Search uses a self-hosted [gosom](https://github.com/gosom/google-maps-scraper) server. You do not need a Google Maps or Places API key.

## Install and run

From the project folder:

```bash
docker compose up -d
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
```

`backend/.env` should contain `MAPS_SCRAPER_API_URL=http://localhost:8080`. The scraper is the `gmaps` service from Docker Compose. The first start downloads a browser.

Sheets export is optional. To append into a spreadsheet you already have, set `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_SPREADSHEET_ID`, and `GOOGLE_SHEET_TAB_NAME`, and share that sheet with the service account.

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

1. Type a business type and a city. A search can take several minutes.
2. Open the leads. These are businesses whose Maps listing has no real website.
3. Export appends them to your Google Sheet and skips ones already on it.
4. Type email addresses yourself. The optional script only creates Gmail drafts. You send them.

If a search fails, the page shows why: the scraper is not running, Google blocked it, or it did not finish in time.
