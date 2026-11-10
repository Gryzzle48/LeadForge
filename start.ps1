# Start LeadForge: Postgres, the maps scraper, the API, and the website.
# Continue, not Stop: Docker writes progress to stderr, and that must not abort the script.
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

function Say([string]$Message) {
    Write-Host $Message
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Say "Docker is not installed."
    Say "Install Docker Desktop from https://docs.docker.com/get-docker/ and run start.bat again."
    exit 1
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Say "Docker is installed, but it is not running."
    Say "Start Docker Desktop, then run start.bat again."
    exit 1
}

docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    Say "Docker Compose is not available."
    Say "Update Docker Desktop, then run start.bat again."
    exit 1
}

New-Item -ItemType Directory -Force -Path "secrets" | Out-Null

$envFile = Join-Path "backend" ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path "backend" ".env.example") $envFile
    Say "Created backend/.env from the example. Nothing in it was printed."
    Say ""
    Say "You can use the app now. Google Sheets export is optional."
    Say "When you want it, edit backend/.env and set:"
    Say "  GOOGLE_SERVICE_ACCOUNT_JSON=./secrets/service-account.json"
    Say "  GOOGLE_SPREADSHEET_ID=the id from the sheet URL"
    Say "  GOOGLE_SHEET_TAB_NAME=Leads"
    Say "Save the key file as secrets\service-account.json. That folder is not committed."
    Say "API_KEY is optional. Leave it empty unless you want a password on the API."
    Say "Inside Docker, the database and the scraper address are set for you."
    Say ""
} else {
    Say "Using the existing backend/.env. Its values are not printed."
}

$apiKey = ""
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^API_KEY=(.*)$') {
        $apiKey = $Matches[1].Trim().Trim('"').Trim("'")
    }
}
$env:NEXT_PUBLIC_API_URL = "http://backend:8000"
$env:NEXT_PUBLIC_API_KEY = $apiKey
Remove-Variable apiKey

Say "Building and starting the stack. The first build can take several minutes."
docker compose up -d --build
if ($LASTEXITCODE -ne 0) {
    Say "Docker did not start the stack."
    Say "See what is happening with: docker compose logs -f"
    exit 1
}

function Get-StatusCode([string]$Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        return [int]$response.StatusCode
    } catch {
        return 0
    }
}

function Get-Body([string]$Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        return [string]$response.Content
    } catch {
        return ""
    }
}

Say "Waiting for the API and the website..."
$ready = $false
for ($i = 0; $i -lt 40; $i++) {
    $body = Get-Body "http://127.0.0.1:8000/api/health"
    $site = Get-StatusCode "http://127.0.0.1:3000/"
    if ($body -match '"database"\s*:\s*"connected"' -and $site -ge 200 -and $site -lt 400) {
        $ready = $true
        break
    }
    Start-Sleep -Seconds 3
}

if (-not $ready) {
    Say "The API or the website did not become ready."
    Say "See what is happening with: docker compose logs -f"
    Say "Stop the stack with: stop.bat"
    exit 1
}

$scraper = Get-StatusCode "http://127.0.0.1:8080/api/docs"
if ($scraper -lt 200 -or $scraper -ge 400) {
    Say "The website is up. The maps scraper is still starting."
    Say "Open http://localhost:8080/api/docs in a minute. Searches need that page to load."
}

Say ""
Say "LeadForge is running."
Say "  App            http://localhost:3000"
Say "  API health     http://localhost:8000/api/health"
Say "  Scraper docs   http://localhost:8080/api/docs"
Say ""
Say "Watch logs with: docker compose logs -f"
Say "Stop with:       stop.bat"

Start-Process "http://localhost:3000"
