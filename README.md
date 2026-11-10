<div align="center">

# LeadForge

Find local businesses that have **no website**, save them to a Google Sheet, and draft outreach you send yourself.

</div>

LeadForge is a small search tool for a web design studio. You pick a business type and a city. It asks Google Places for matching businesses, drops the ones that already have a website, and writes the rest to a spreadsheet: name, category, address, phone, Maps link, rating, and review count, plus a draft email. Nothing is emailed automatically.

## What you need

- A Google Cloud project with billing enabled (Places has a monthly credit)
- Python 3.11+ and Node.js 18+ for local development
- Docker, only if you want the included Postgres for local development

## 1. Turn on the Google APIs

In [Google Cloud Console](https://console.cloud.google.com/):

1. Create a project.
2. Enable **Places API (New)**. The older "Places API" is a different product and will not work.
3. Enable **Google Sheets API** and **Google Drive API** (Drive is used only to share the sheet with you).
4. Create an **API key** for Places. Restrict it to Places API (New) if you want.
5. Create a **service account**, give it no special project role, and download its JSON key. You will paste that JSON into the backend settings. Do not commit the file.

You do **not** need the Geocoding API. City names are looked up with Places.

## 2. Backend settings

Copy the example file and fill it in:

```bash
cp backend/.env.example backend/.env
```

| Variable | Required | What to put |
| --- | --- | --- |
| `GOOGLE_MAPS_API_KEY` | Yes | The Places API (New) key |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Yes, to export | The service-account JSON, on one line, or that JSON encoded as base64, or a path to the file |
| `GOOGLE_SHEET_SHARE_EMAIL` | Strongly recommended | Your Gmail address. Each sheet is shared with this address as an editor. If you leave it empty, anyone with the link can edit the sheet |
| `DATABASE_URL` | Yes | Postgres URL. `postgres://` and `?sslmode=require` (as Railway provides) are accepted |
| `API_KEY` | No | If set, every API call except `/api/health` must send the same value in the `X-API-Key` header |
| `CORS_ORIGINS` | No | Comma-separated sites, if something calls the API directly. The Vercel app proxies `/api`, so the browser does not need this |

`backend/.env` is loaded even if you start the server from the project root. Do not commit it.

## 3. Run it locally

From the project root:

```bash
docker compose up -d
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env    # then edit it
uvicorn backend.main:app --reload --port 8000
```

In a second terminal:

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000.

`frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_KEY=
```

`NEXT_PUBLIC_API_KEY` must match `API_KEY` when you set one. Leave both empty for local use.

Start the API from the **project root**, not from inside `backend/`. The command is `uvicorn backend.main:app`.

## 4. Deploy

**API (Railway)**

1. Deploy this repo with the root `Dockerfile`.
2. Add Postgres. Railway sets `DATABASE_URL` for you.
3. Set `GOOGLE_MAPS_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_JSON`, and `GOOGLE_SHEET_SHARE_EMAIL`.
4. Copy the public `https://….up.railway.app` URL. Do not use a `*.railway.internal` hostname.

**Site (Vercel)**

1. Import the repo and set the root directory to `frontend`.
2. Set `NEXT_PUBLIC_API_URL` to that public Railway URL, with no trailing slash.
3. Set `NEXT_PUBLIC_API_KEY` only if the backend has `API_KEY`.
4. Deploy again after changing those variables. Next.js reads them at build time.

The live site at `https://leadforge-tawny-rho.vercel.app` only works after `NEXT_PUBLIC_API_URL` points at the public API. If it is missing, or points at a private host, Vercel answers API calls with `DNS_HOSTNAME_RESOLVED_PRIVATE` and searches do nothing.

## How a search works

1. Enter a business type (plumber, dentist, cafe) and a city. Optional filters: radius (100 m to 50 km), minimum rating, and minimum or maximum review count.
2. The city is located with Places. If that lookup fails, the search stops and says so. It does not quietly search another city.
3. The area is searched with the official Places API (New). Each request asks for 20 results and follows the next page, up to 60 (the API cap). If a patch of the map comes back full, it is split into smaller patches so smaller businesses are not skipped.
4. A business is kept only when it has no real website. A Google Maps link does not count as a website. If the search result omits the website, Place Details is checked before the business is saved, so a listed site is not treated as "no website."
5. Permanently closed businesses are skipped. Rating and review filters are applied to the number you typed. Places rounds ratings up to the next 0.5, which used to drop businesses you asked to keep; the exact cutoff is applied here.
6. Draft emails are written from the category templates. They are drafts only.
7. Export creates a **new** sheet (it does not overwrite an older one) with name, category, address, phone, Maps link, rating, reviews, website, email, subject, and draft. Phone numbers are stored as text.

Each finished search includes a short note: how many were saved, how many were left out because they have a website, and whether Google returned an error.

The same Google place is not saved twice. A business found in an earlier search stays in that search.

## Sending mail

The sheet does not contain email addresses. Google does not provide them. Type the address into the Email column, then optionally paste `scripts/apps_script.gs` into Extensions → Apps Script and run `createDrafts`. That creates Gmail drafts. You read them and send them yourself.

The script does not send email and does not install a timer. If you previously installed a timer from an older copy, run `removeAllTriggers` in Apps Script.

## Checks

```bash
python -m pytest backend/tests -q
cd frontend && npm test && npm run build
```

## Layout

```
backend/main.py                 API
backend/workers/places.py       Places paging, website check, filters
backend/workers/grid_search.py  Runs a search and saves leads
backend/workers/sheet_exporter.py
backend/workers/email_writer.py Draft text only
frontend/                       Next.js site
scripts/apps_script.gs          Optional Gmail drafts
```

## Limits

- Places returns at most 60 results per patch of the map. Very large, dense areas can still miss some businesses. The search stops after a fixed number of calls so one click cannot run up a large bill, and the note tells you when that happens. Use a smaller radius to cover an area more completely.
- Place Details is called for businesses that look like they have no website. That is a paid Places request. At most 200 of those checks run per search.
- A sheet created by the service account is private until it is shared. Set `GOOGLE_SHEET_SHARE_EMAIL`.
- Outreach stays manual. This app will not send messages for you.

## License

MIT. See [LICENSE](LICENSE).
