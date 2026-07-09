# Migrate IRS data from SQLite (db.sqlite3) to PostgreSQL (DATABASE_URL in .env).
# Usage (from kmc-irs/):  .\scripts\migrate_to_postgres.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path "db.sqlite3")) {
    Write-Host "No db.sqlite3 found - running migrations on PostgreSQL only."
    python manage.py migrate
    exit 0
}

$dumpFile = "sqlite_export.json"
Write-Host "Exporting data from SQLite..."
$env:USE_SQLITE = "1"
python manage.py dumpdata `
    --natural-foreign `
    --natural-primary `
    -e contenttypes `
    -e auth.permission `
    --indent 2 `
    --output $dumpFile
Remove-Item Env:USE_SQLITE -ErrorAction SilentlyContinue

Write-Host "Applying migrations on PostgreSQL..."
python manage.py migrate

Write-Host "Loading data into PostgreSQL..."
python manage.py loaddata $dumpFile

Write-Host "Done. PostgreSQL is ready. You can archive or remove db.sqlite3 when satisfied."
