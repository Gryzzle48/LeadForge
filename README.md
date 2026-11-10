# LocalWeb Leads

Local-first lead research dashboard for finding businesses whose Google Maps listing does not show a website, reviewing their contact details, and appending verified leads to one Google Sheets tab.

## Free local stack

- **Maps data collection:** [gosom/google-maps-scraper](https://github.com/gosom/google-maps-scraper), self-hosted in Docker (MIT-licensed).
- **Backend:** Python 3.11+, FastAPI, SQLAlchemy, PostgreSQL.
- **Frontend:** Next.js 14, React 18.
- **Spreadsheet export:** Google Sheets API using a service account (optional).
- No Google Places API key, Geocoding API key, SerpApi key, paid proxy, or hosted scraper account is required for the local setup.

The scraper runs with one worker, local storage, and telemetry disabled. It does not rotate proxies or attempt to bypass CAPTCHAs or access restrictions. Automated access to external websites may be blocked and remains subject to their terms.

## Features

- Search by business category, US city, state, and result limit (up to 120 per query).
- Import name, category, address, phone, rating, Place ID, and Maps URL.
- Keep entries whose Maps result contains no website field.
- Global duplicate prevention using Place ID, with a stable fallback key when Place ID is missing.
- Manually look up email and Instagram from each row using free web-search links.
- Edit and save phone, email, and Instagram details in PostgreSQL.
- Append to one permanent Google Sheets tab named `Leads`; skip duplicate rows and continue sequential numbering.
- No automated email sending.

## Quick start (Linux)

Requirements: Docker Engine + Compose, Python 3.11, Node.js 22+, npm, and Git.

Clone the working branch:

```bash
git clone -b localweb-adaptation https://github.com/Gryzzle48/LeadForge.git
cd LeadForge
```

Start PostgreSQL and the local Maps scraper:

```bash
docker compose up -d
docker compose ps
docker compose logs --tail=100 maps-scraper
```

The local scraper API and its UI are available at http://127.0.0.1:8080.

Set up the backend:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
```

For local use, the sample environment defaults are enough to search. Open `backend/.env` only if you want to configure Google Sheets export:

- `GOOGLE_SERVICE_ACCOUNT_JSON`: raw or base64-encoded service-account JSON.
- `GOOGLE_SPREADSHEET_ID`: spreadsheet ID.
- `GOOGLE_SHEET_TAB_NAME=Leads`.

Share the spreadsheet with the service-account email as Editor. You only need to enable Google Sheets API if you use export; Places and Geocoding APIs and billing are not required.

Run the backend from the repository root:

```bash
source .venv/bin/activate
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
cd frontend
npm ci
cat > .env.local <<'EOF'
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_KEY=
EOF
npm run dev
```

Open http://localhost:3000.

## Use

1. Enter category, city, state, and a maximum of 1–120 businesses.
2. Wait for the campaign status to become Completed. Scraper searches can take a few minutes.
3. Review phone numbers and Maps links.
4. Use **Find email** or **Find Instagram** to open a regular web search.
5. Verify the result, select **Edit contacts**, and save the contact details.
6. Select **Add to Google Sheets** to append results to the configured `Leads` tab.

## Contact data limitations

Phone numbers may be present in Maps results. Businesses with no website listed often do not expose an email or Instagram profile in the Maps record. The app therefore does not claim to discover every email or social account automatically. Manual verified entry is free and is included in exports.

## Configuration

| Variable | Purpose |
|---|---|
| `MAPS_SCRAPER_API_URL` | Local scraper URL (default `http://127.0.0.1:8080`) |
| `DATABASE_URL` | PostgreSQL connection |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Optional Sheets service account |
| `GOOGLE_SPREADSHEET_ID` | Optional target spreadsheet |
| `GOOGLE_SHEET_TAB_NAME` | Target tab (default `Leads`) |
| `API_KEY` | Optional backend API authentication |

Do not commit `backend/.env`, `frontend/.env.local`, or service-account credentials.

## Limits and troubleshooting

- One local Maps query is capped at 120 requested results; actual results depend on coverage, query wording, duplicates, and scraper availability.
- If the campaign fails, check `docker compose logs --tail=200 maps-scraper`.
- If the backend cannot connect to the scraper, confirm `MAPS_SCRAPER_API_URL=http://127.0.0.1:8080` and that port 8080 is listening.
- If PostgreSQL is disconnected, run `docker compose ps` and check the `postgres` logs.
- If Sheets export fails, verify the Sheets API is enabled and the service-account email has Editor access.

## Project docs

- [Local setup and data behavior](LOCALWEB_SETUP.md)
- [Free manual contact lookup](CONTACT_FINDER_SETUP.md)
- [Upstream Maps scraper](https://github.com/gosom/google-maps-scraper)

