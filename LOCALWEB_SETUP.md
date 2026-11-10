# LocalWeb Leads — setup checklist

## Required Google configuration

1. Enable Places API (New), Geocoding API, and Google Sheets API in a Google Cloud project.
2. Create a server-side API key for Places and Geocoding. Restrict it to the APIs used by the backend.
3. Create a service account for Sheets API access.
4. Create one spreadsheet and add (or let the app create) a tab named Leads.
5. Share the spreadsheet with the service account email as Editor.
6. Copy the spreadsheet ID from the URL into GOOGLE_SPREADSHEET_ID.

## Backend environment

Set the following in backend/.env:

- GOOGLE_MAPS_API_KEY
- GOOGLE_SERVICE_ACCOUNT_JSON (raw JSON or base64 JSON)
- GOOGLE_SPREADSHEET_ID
- GOOGLE_SHEET_TAB_NAME=Leads
- DATABASE_URL
- API_KEY (recommended for non-local deployment)
- CORS_ORIGINS

Do not commit backend/.env or service-account keys.

## Search behavior

The search uses a business category, city, state, and a maximum requested result count. The maximum is an upper bound. Actual counts depend on the search results returned by Google Places, geographic coverage, and how many businesses already exist in the database.

The website filter means that the Places response did not contain a website field. It does not prove that the business has no website elsewhere.

The current Places response provides phone numbers where available. It does not provide email addresses or Instagram handles as standard Place fields; these are left blank rather than guessed. A separately sourced contact-enrichment stage is required for those fields.

## Google Sheets columns

Number | Business Name | Category | Google Maps Link | Contacts | City | State

Contacts are newline-separated entries containing whichever values are available, such as Phone, Email, and Instagram.

## Deduplication

- Database: Google Place ID is globally unique across campaigns.
- Spreadsheet: existing Google Maps URLs are checked before appending.
- Fallback: existing rows without a Maps link are compared by normalized business name, city, and state.
- Numbers continue from the highest existing Number in the sheet.

The application appends to the same Leads tab. It does not create a new spreadsheet per campaign.
