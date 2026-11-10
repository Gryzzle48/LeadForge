@echo off
cd /d "%~dp0"
echo This deletes every saved search and lead in the local database.
echo It does not change your Google Sheet or the scraper data.
set /p ANSWER=Type YES to continue: 
if not "%ANSWER%"=="YES" (
  echo Cancelled. Nothing was deleted.
  exit /b 1
)
docker compose exec -T postgres psql -U postgres -d leadforge -v ON_ERROR_STOP=1 -c "DROP TABLE IF EXISTS leads CASCADE; DROP TABLE IF EXISTS audit_logs CASCADE; DROP TABLE IF EXISTS campaigns CASCADE;"
if errorlevel 1 exit /b 1
docker compose restart backend
if errorlevel 1 exit /b 1
echo Local searches were deleted. The API will recreate empty tables as it starts.
echo Your Google Sheet and the scraper data were not touched.
