# LocalWeb Leads — free local setup

## What runs locally

- PostgreSQL stores campaigns and leads.
- gosom/google-maps-scraper runs in Docker as a local service at http://127.0.0.1:8080.
- FastAPI sends search jobs to that local service and imports its CSV results.
- Next.js provides the search dashboard.
- Google Sheets export is optional and uses a Google service account.

No Google Places API key, Geocoding API key, SerpApi key, paid proxy, or hosted scraping account is needed for the local workflow.

## Start the services

From the repository root:

```bash
docker compose up -d
```

This starts PostgreSQL and the local Maps scraper. The scraper uses one worker and telemetry is disabled by the Compose environment setting.

Check Docker:

```bash
docker compose ps
docker compose logs --tail=100 maps-scraper
```

The local scraper API is available at http://127.0.0.1:8080. The built-in UI is also available at http://127.0.0.1:8080.

## Backend environment

Copy the sample file:

```bash
cp backend/.env.example backend/.env
```

Set at least:

- MAPS_SCRAPER_API_URL=http://127.0.0.1:8080
- DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/leadforge

For Google Sheets export only, also set:

- GOOGLE_SERVICE_ACCOUNT_JSON (raw JSON or base64 JSON)
- GOOGLE_SPREADSHEET_ID
- GOOGLE_SHEET_TAB_NAME=Leads

Do not commit backend/.env or service-account keys. You do not need to enable Places API, Geocoding API, or billing for this configuration. Enable Google Sheets API only if you use the export feature.

## Search behavior and limits

Searches use a category plus city/state query and run through the self-hosted gosom scraper. Results are imported into the existing PostgreSQL database, deduplicated globally by Place ID (with a stable fallback key when a Place ID is absent), and filtered to records without a website listed in the Maps result.

A single search request is capped at 120 requested businesses. Actual results depend on Maps coverage, duplicate records, query quality, and the scraper's ability to retrieve results. A Maps result with no website field does not prove that the business has no website elsewhere.

The scraper is configured with one worker and no proxy rotation. It does not attempt to bypass CAPTCHAs or access restrictions. Google may change its site behavior or block automated access; availability is not guaranteed.

## Contacts

Phone numbers are imported when present in the Maps result. Email and Instagram are not reliably provided for businesses with no website listed. The results page therefore provides direct web-search links; verify the match and use **Edit contacts** to save a phone number, email, or Instagram profile. Saved values are included in the Google Sheets export.

## Google Sheets columns

Number | Business Name | Category | Google Maps Link | Contacts | City | State

The exporter appends to one tab named Leads, skips records already present, and continues numbering from the highest existing row. It does not delete previous rows or create a new spreadsheet per campaign.

## Important note

gosom/google-maps-scraper is a separate MIT-licensed open-source project. Its license does not override the terms of external websites. Review applicable Google terms before using automated extraction, and do not try to evade blocks or access controls.
