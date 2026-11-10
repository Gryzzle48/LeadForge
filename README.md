<div align="center">

# LeadForge

Find local businesses that have **no website**, save them to a Google Sheet, and draft outreach you send yourself.

</div>

LeadForge searches with a [gosom Google Maps scraper](https://github.com/gosom/google-maps-scraper) you run yourself. It does not call the paid Google Places API. You pick a business type and a city. The scraper reads Google Maps. LeadForge drops businesses that already list their own website and writes the rest to a spreadsheet with five columns: `#`, Name, Category, Google Maps, and Contacts. Draft emails stay in the app. Nothing is emailed automatically.

A blank website, a Maps link, or a social profile (Facebook, Instagram, and similar) counts as no website, because the scraper has already opened the place page.

## Quick start: one command

Install [Docker Desktop](https://docs.docker.com/get-docker/) and leave it running. Then, from this folder:

```bash
./start.sh
```

On Windows, double-click `start.bat` or run it from a command prompt.

The script checks that Docker is running, creates `backend/.env` the first time, builds the stack, and opens the app.

| | |
| --- | --- |
| App | http://localhost:3000 |
| API health | http://localhost:8000/api/health |
| Scraper docs | http://localhost:8080/api/docs |

Stop it with `./stop.sh` (Windows: `stop.bat`). Watch logs with `docker compose logs -f`.

To erase saved searches and start the local database over, run `./reset-db.sh` (Windows: `reset-db.bat`) and type `YES`. That drops the app tables in the compose Postgres database and restarts the API so empty tables are created again. It does not change your Google Sheet or the gosom scraper data.

Sheets export is optional. To turn it on, put your service-account JSON at `secrets/service-account.json` and set these in `backend/.env` (the file is not committed):

```env
GOOGLE_SERVICE_ACCOUNT_JSON=./secrets/service-account.json
GOOGLE_SPREADSHEET_ID=the id from the sheet URL
GOOGLE_SHEET_TAB_NAME=Leads
```

Inside Docker, the API talks to the scraper at `http://gmaps:8080` and to Postgres on the compose network. You do not put those addresses in `.env`. The website is built with `NEXT_PUBLIC_API_URL=http://backend:8000` so the site container can reach the API. Building the image by itself, without Compose, defaults that address to `http://localhost:8000`.

## What you need

- Docker Desktop (or Docker Engine with Compose). That is enough for the one-command start.
- Python 3.11+ and Node.js 18+ only if you run the API or the website outside Docker
- A Google service account only if you export to a spreadsheet you already have

## 1. Start everything

`./start.sh` (or `start.bat` on Windows) is the normal way. It runs Postgres, the maps scraper, the API, and the website.

A search can take several minutes. The scraper docs are at http://localhost:8080/api/docs.

`docker-compose.yml` runs four services: `postgres`, `gmaps`, `backend`, and `frontend`. The API container uses `http://gmaps:8080` and the compose Postgres hostname. Those override `backend/.env` while the containers are running.

## 2. Backend settings

```bash
cp backend/.env.example backend/.env
```

| Variable | Required | What to put |
| --- | --- | --- |
| `MAPS_SCRAPER_API_URL` | Yes, outside Docker | Scraper base URL, for example `http://localhost:8080`. Compose replaces this with `http://gmaps:8080` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Only to export | The JSON itself, that JSON in base64, or `./secrets/service-account.json` |
| `GOOGLE_SPREADSHEET_ID` | Only to export | The id in the sheet URL: `docs.google.com/spreadsheets/d/<this>/edit` |
| `GOOGLE_SHEET_TAB_NAME` | No | Tab to append to. Defaults to `Leads`. Share that spreadsheet with the service account email as an editor |
| `DATABASE_URL` | Yes | Postgres. A Railway `postgres://...?sslmode=require` URL is accepted |
| `API_KEY` | No | If set, every API call except `/api/health` must send it as `X-API-Key` |
| `CORS_ORIGINS` | No | Comma-separated sites, if something calls the API directly |

Optional Google Sheets export (no Maps or search API key required). If `GOOGLE_SPREADSHEET_ID` is set, each export appends new rows to that tab. The columns are exactly `#`, Name, Category, Google Maps, and Contacts. `#` keeps counting from the last row already on the sheet. A business already listed (same Maps link, or the same name and contacts when there is no link) is skipped. Contacts puts phone, email, and a social link such as Facebook or Instagram on separate lines. Draft text stays in LeadForge, not in the sheet.

The tab is written only when it is empty or its header is already those five names in that order. If the tab has an older header, it is left unchanged and the rows go to a tab named `{that name} (LeadForge)` instead. If that tab also has a different header, the export stops and asks you to set `GOOGLE_SHEET_TAB_NAME` to a new empty tab. If the spreadsheet id is empty, LeadForge can still create a new spreadsheet. Set `GOOGLE_SHEET_SHARE_EMAIL` only for that fallback, so the new file is shared with you.

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

1. Enter a business type and a city. The search covers the whole city, not one radius. Optional: a target number of businesses with no website, plus minimum rating and minimum or maximum review count. Leave the target blank to keep going until the city is covered.
2. The city outline comes from OpenStreetMap (Nominatim). No Google key. The city is split into tiles, and each tile is one gosom job (`lat`, `lon`, `zoom`, `radius`, `depth`). Tiles run one at a time.
3. The search stops when the target is reached, when several tiles in a row add no new businesses, when every tile is done, or when the time or tile cap is hit (`SEARCH_MAX_SECONDS`, `SEARCH_MAX_TILES`).
4. Leads are saved as each tile finishes, show up on the campaign page while the search is still running, and are appended to the Google Sheet when a spreadsheet id is set. You can cancel a running search.
5. Businesses with their own website are left out. Blank websites, Maps links, and social-only pages are kept. The same place is not saved twice.
6. Draft emails are written from the category templates. They are drafts only. Nothing is sent.

If the scraper is down or blocked, the search is marked failed and the page shows the reason. It does not stay on "running".

## Sending mail

Draft emails stay on the lead in LeadForge. The sheet is only the contact list, so there is no email or draft column to send from. Copy a contact from the sheet and send the draft yourself.

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

- The scraper is slow, and Google Maps can block it. Each tile waits up to `SEARCH_TILE_SECONDS` (default 180). A whole-city search stops after `SEARCH_MAX_SECONDS` (default 5400) or `SEARCH_MAX_TILES` (default 40).
- Tile size starts at `SEARCH_TILE_KM` (default 3). `SEARCH_EMPTY_TILES` (default 3) is how many areas in a row with no new businesses end the search early.
- `SEARCH_TILE_DEPTH` (default 4) is how far gosom scrolls each tile.
- A spreadsheet export needs the sheet shared with the service account. Enable the Google Sheets API for that project.

## License

MIT. See [LICENSE](LICENSE).
