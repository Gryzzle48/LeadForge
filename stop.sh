#!/usr/bin/env bash
# Stop LeadForge. Your database and scraper data stay on disk.
set -euo pipefail

cd "$(dirname "$0")"

say() {
  printf '%s\n' "$*"
}

if ! command -v docker >/dev/null 2>&1; then
  say "Docker is not installed, so there is nothing to stop."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  say "Docker is not running, so the stack is already stopped."
  exit 0
fi

docker compose stop
say "LeadForge is stopped. Your saved searches are still there."
say "Start again with: ./start.sh"
say "Watch logs with:  docker compose logs -f"
