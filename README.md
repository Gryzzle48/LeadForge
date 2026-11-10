<div align="center">
  <h1>LocalWeb Leads</h1>
  <p><strong>Find local businesses with no website listed and organize leads in one Google Sheet.</strong></p>
  <p>Adapted from LeadForge for LocalWeb Studio.</p>
</div>

## Features

- Search US businesses by category, city, state, and maximum result count.
- Use Google Places API (New) for structured business search.
- Keep businesses that do not have a website listed in the search response.
- Capture business name, category, Place ID, Google Maps link, and phone when available.
- Deduplicate globally by Google Place ID before saving leads.
- Keep campaigns and leads in PostgreSQL.
- Append new businesses to one existing Google spreadsheet tab named Leads.
- Skip rows already present in the target sheet.
- No automated email generation or sending in the LocalWeb workflow.

## Architecture

- Frontend: Next.js 14 / React 18.
- Backend: FastAPI / Python 3.11.
- Database: PostgreSQL / SQLAlchemy async.
- Search: Google Places API (New) and Geocoding API.
- Export: Google Sheets API v4 using a Google service account.

## Local setup

1. Enable Places API (New), Geocoding API, and Google Sheets API in a Google Cloud project.
2. Create a Google Maps API key and a Google service account with access to the destination spreadsheet.
3. Create one Google spreadsheet and one tab named Leads.
4. Share the spreadsheet with the service account email as an Editor.
5. Copy backend/.env.example to backend/.env and fill in the values.
6. Start PostgreSQL with docker compose up -d.
7. Install backend packages with pip install -r backend/requirements.txt.
8. Start the API from the repository root with uvicorn backend.main:app --reload --port 8000.
9. Install frontend packages with cd frontend && npm install.
10. Start the frontend with npm run dev.

## Environment variables

- GOOGLE_MAPS_API_KEY: key used by Places and Geocoding APIs.
- GOOGLE_SERVICE_ACCOUNT_JSON: raw or base64 service-account JSON.
- GOOGLE_SPREADSHEET_ID: ID of your existing, permanent spreadsheet.
- GOOGLE_SHEET_TAB_NAME: destination tab name; defaults to Leads.
- DATABASE_URL: PostgreSQL connection string.
- API_KEY: optional backend API key. Set it before any public deployment.
- CORS_ORIGINS: comma-separated allowed frontend origins.

## Search workflow

1. Enter a business category, US city, state, and maximum number of businesses (1–500).
2. The backend geocodes the complete city/state/country location.
3. Search results with a website listed are excluded.
4. Existing Place IDs are skipped across all previous campaigns.
5. Review the remaining leads and their Maps links.
6. Export to append new rows to the configured Leads tab.

## Google Sheets layout

The exporter maintains the following seven visible columns:

1. Number
2. Business Name
3. Category
4. Google Maps Link
5. Contacts
6. City
7. State

The Contacts cell contains available public contact values as newline-separated text (Phone, Email, Instagram). The current Places search captures a phone number when provided. Email and Instagram enrichment are not included yet; empty values are not fabricated.

The exporter uses the Google Maps Place ID as the database deduplication key and checks Maps URLs plus business/city/state as spreadsheet-level duplicate safeguards.

## Notes

- “No website listed” means the search provider did not return a website field. It does not prove that the business has no website.
- Google Places search results are capped by the provider per request. A requested maximum is an upper limit, not a guarantee that the search will find that many eligible, unique businesses.
- Do not commit API keys, service-account credentials, or .env files.
- Original MIT license is retained.
