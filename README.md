<div align="center">

# LeadForge

Find local businesses that have **no website**, save them to a Google Sheet, and draft outreach you send yourself.

</div>

LeadForge searches with a [gosom Google Maps scraper](https://github.com/gosom/google-maps-scraper) you run yourself. It does not call the paid Google Places API. You pick a business type and a city. The scraper reads Google Maps. LeadForge drops businesses that already list their own website and writes the rest to a spreadsheet: name, category, address, phone, Maps link, rating, and review count, plus a draft email. Nothing is emailed automatically.

A blank website, a Maps link, or a social profile (Facebook, Instagram, and similar) counts as no website, because the scraper has already opened the place page.

## What you need

- Docker, for Postgres and the maps scraper
- Python 3.11+ and Node.js 18+
- A Google service account only if you export to a spreadsheet you already have

## 1. Start Postgres and the scraper

From the project root:

```bash
docker compose up -d
```

That starts:

- Postgres on port 5432
- gosom on port 8080 (`MAPS_SCRAPER_API_URL=http://localhost:8080`)

The scraper's first start downloads a browser. A search often takes several minutes. Open http://localhost:8080/api/docs to see the scraper API.

The compose service is:

```yaml
gmaps:
  image: gosom/google-maps-scraper:latest
  command: ["-data-folder", "/gmapsdata", "-addr", ":8080"]
  ports:
    - "8080:8080"
  shm_size: "1gb"
  volumes:
    - gmapsdata:/gmapsdata
```

## 2. Backend settings

```bash
cp backend/.env.example backend/.env
```

| Variable | Required | What to put |
| --- | --- | --- |
| `MAPS_SCRAPER_API_URL` | Yes | Scraper base URL, for example `http://localhost:8080`. No trailing path |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Only to export | Service-account JSON, that JSON in base64, or a path to the file |
| `GOOGLE_SPREADSHEET_ID` | Only to export | The id in the sheet URL: `docs.google.com/spreadsheets/d/<this>/edit` |
| `GOOGLE_SHEET_TAB_NAME` | No | Tab to append to. Defaults to `Leads`. Share that spreadsheet with the service account email as an editor |
| `DATABASE_URL` | Yes | Postgres. A Railway `postgres://...?sslmode=require` URL is accepted |
| `API_KEY` | No | If set, every API call except `/api/health` must send it as `X-API-Key` |
| `CORS_ORIGINS` | No | Comma-separated sites, if something calls the API directly |

Optional Google Sheets export (no Maps or search API key required). If `GOOGLE_SPREADSHEET_ID` is set, each export appends new rows to that tab and skips businesses already listed (same place id, Maps link, or name and phone). The header row is written when the tab is empty. If the spreadsheet id is empty, LeadForge can still create a new spreadsheet. Set `GOOGLE_SHEET_SHARE_EMAIL` only for that fallback, so the new file is shared with you.

`backend/.env` is loaded even if you start the server from the project root. Do not commit it.

## 3. Run the app

Terminal 1, from the project root:

```bash
pip install -r backend/requirements.txt
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

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_KEY=
```

`NEXT_PUBLIC_API_KEY` must match `API_KEY` when you set one. Start the API from the project root with `uvicorn backend.main:app`.

## How a search works

1. Enter a business type and a city. Optional filters: radius, minimum rating, and minimum or maximum review count. The rating and review filters use the numbers you typed.
2. LeadForge asks the scraper to search for `{type} in {city}` and polls until the job is `ok` or `failed`. There is no Google Places API key.
3. Businesses with their own website are left out. Blank websites, Maps links, and social-only pages are kept.
4. The same place is not saved twice.
5. Draft emails are written from the category templates. They are drafts only.
6. Export appends to your spreadsheet. It does not clear rows already there.

If the scraper is down, blocked, or still working when the time limit runs out, the search is marked failed and the page shows the reason. It does not stay on "running".

## Sending mail

The sheet usually has no email address. Type one into the Email column, then optionally paste `scripts/apps_script.gs` into Extensions → Apps Script and run `createDrafts`. That creates Gmail drafts. You send them yourself. The script does not send mail and does not install a timer.

## Checks

```bash
python -m pytest backend/tests -q
cd frontend && npm test && npm run build
```

## Layout

```
backend/workers/gosom.py          Scraper client, website check, filters
backend/workers/grid_search.py    Runs one search and saves leads
backend/workers/sheet_exporter.py Appends to your sheet, or creates one
backend/workers/email_writer.py   Draft text only
frontend/                         Next.js site
scripts/apps_script.gs            Optional Gmail drafts
```

## Limits

- The scraper is slow, and Google Maps can block it. One search waits up to `MAPS_SCRAPER_MAX_TIME_SECONDS` (default 15 minutes, minimum 3). Use a smaller radius if a job does not finish.
- Scroll depth defaults to 10 (`MAPS_SCRAPER_DEPTH`). That is the scraper's own page depth, not a Places API page size.
- A spreadsheet export needs the sheet shared with the service account. Enable the Google Sheets API for that project.

## License

MIT. See [LICENSE](LICENSE).
