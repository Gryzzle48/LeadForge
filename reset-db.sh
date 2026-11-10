#!/usr/bin/env bash
# Delete saved searches and leads in the local Docker database.
# Does not change the Google Sheet or the gosom scraper data.
set -euo pipefail

cd "$(dirname "$0")"

printf '%s\n' "This deletes every saved search and lead in the local database."
printf '%s\n' "It does not change your Google Sheet or the scraper data."
printf '%s' "Type YES to continue: "
read -r answer
if [[ "$answer" != "YES" ]]; then
  printf '%s\n' "Cancelled. Nothing was deleted."
  exit 1
fi

if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  printf '%s\n' "Docker is not running. Start it, then run ./reset-db.sh again."
  exit 1
fi

docker compose exec -T postgres psql -U postgres -d leadforge -v ON_ERROR_STOP=1 \
  -c "DROP TABLE IF EXISTS leads CASCADE; DROP TABLE IF EXISTS audit_logs CASCADE; DROP TABLE IF EXISTS campaigns CASCADE;"
docker compose restart backend
printf '%s\n' "Local searches were deleted. The API will recreate empty tables as it starts."
printf '%s\n' "Your Google Sheet and the scraper data were not touched."
