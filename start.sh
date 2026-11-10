#!/usr/bin/env bash
# Start LeadForge: Postgres, the maps scraper, the API, and the website.
set -euo pipefail

cd "$(dirname "$0")"

say() {
  printf '%s\n' "$*"
}

if ! command -v docker >/dev/null 2>&1; then
  say "Docker is not installed."
  say "Install Docker Desktop from https://docs.docker.com/get-docker/ and run ./start.sh again."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  say "Docker is installed, but it is not running."
  say "Start Docker Desktop, then run ./start.sh again."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  say "Docker Compose is not available."
  say "Update Docker Desktop, then run ./start.sh again."
  exit 1
fi

mkdir -p secrets

if [[ ! -f backend/.env ]]; then
  cp backend/.env.example backend/.env
  say "Created backend/.env from the example. Nothing in it was printed."
  say ""
  say "You can use the app now. Google Sheets export is optional."
  say "When you want it, edit backend/.env and set:"
  say "  GOOGLE_SERVICE_ACCOUNT_JSON=./secrets/service-account.json"
  say "  GOOGLE_SPREADSHEET_ID=the id from the sheet URL"
  say "  GOOGLE_SHEET_TAB_NAME=Leads"
  say "Save the key file as secrets/service-account.json. That folder is not committed."
  say "API_KEY is optional. Leave it empty unless you want a password on the API."
  say "Inside Docker, the database and the scraper address are set for you."
  say ""
else
  say "Using the existing backend/.env. Its values are not printed."
fi

api_key=""
if line="$(grep -E '^API_KEY=' backend/.env | tail -n 1 || true)"; then
  api_key="${line#API_KEY=}"
  api_key="${api_key%$'\r'}"
  api_key="${api_key#\"}"
  api_key="${api_key%\"}"
  api_key="${api_key#\'}"
  api_key="${api_key%\'}"
fi
export NEXT_PUBLIC_API_URL="http://backend:8000"
export NEXT_PUBLIC_API_KEY="$api_key"
unset api_key

say "Building and starting the stack. The first build can take several minutes."
docker compose up -d --build

http_code() {
  local url="$1"
  local code="000"
  if command -v curl >/dev/null 2>&1; then
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$url" || true)"
  else
    code="$(python3 - "$url" <<'PY' || true
import sys, urllib.request
try:
    with urllib.request.urlopen(sys.argv[1], timeout=5) as resp:
        print(resp.status, end="")
except Exception:
    print("000", end="")
PY
)"
  fi
  if [[ -z "$code" || "$code" == "000" ]]; then
    printf '000'
  else
    printf '%s' "$code"
  fi
}

http_body() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -fsS --max-time 5 "$url" 2>/dev/null || true
  else
    python3 - "$url" <<'PY' || true
import sys, urllib.request
try:
    print(urllib.request.urlopen(sys.argv[1], timeout=5).read().decode("utf-8", "replace"))
except Exception:
    pass
PY
  fi
}

say "Waiting for the API and the website..."
ready=0
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40; do
  body="$(http_body "http://127.0.0.1:8000/api/health")"
  site="$(http_code "http://127.0.0.1:3000/")"
  if [[ "$body" == *'"database": "connected"'* || "$body" == *'"database":"connected"'* ]]; then
    if [[ "$site" == 2* || "$site" == 3* ]]; then
      ready=1
      break
    fi
  fi
  sleep 3
done

if [[ "$ready" -ne 1 ]]; then
  say "The API or the website did not become ready."
  say "See what is happening with: docker compose logs -f"
  say "Stop the stack with: ./stop.sh"
  exit 1
fi

scraper="$(http_code "http://127.0.0.1:8080/api/docs")"
if [[ ! "$scraper" =~ ^[23] ]]; then
  say "The website is up. The maps scraper is still starting."
  say "Open http://localhost:8080/api/docs in a minute. Searches need that page to load."
fi

say ""
say "LeadForge is running."
say "  App            http://localhost:3000"
say "  API health     http://localhost:8000/api/health"
say "  Scraper docs   http://localhost:8080/api/docs"
say ""
say "Watch logs with: docker compose logs -f"
say "Stop with:       ./stop.sh"

if command -v open >/dev/null 2>&1; then
  open "http://localhost:3000" >/dev/null 2>&1 || true
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "http://localhost:3000" >/dev/null 2>&1 || true
else
  say "Open http://localhost:3000 in your browser."
fi
