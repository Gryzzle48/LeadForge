# Stop LeadForge. Saved searches stay on disk.
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

function Say([string]$Message) {
    Write-Host $Message
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Say "Docker is not installed, so there is nothing to stop."
    exit 1
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Say "Docker is not running, so the stack is already stopped."
    exit 0
}

docker compose stop
if ($LASTEXITCODE -ne 0) {
    Say "Docker could not stop the stack."
    Say "See what is happening with: docker compose logs -f"
    exit 1
}

Say "LeadForge is stopped. Your saved searches are still there."
Say "Start again with: start.bat"
Say "Watch logs with:  docker compose logs -f"
