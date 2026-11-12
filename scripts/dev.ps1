# One command to run RAG Galaxy locally on Windows:  .\scripts\dev.ps1
# The Windows twin of dev.sh: starts Postgres (Docker), creates the tables,
# then the API and the frontend. Ctrl+C stops the API and frontend;
# `docker compose down` stops Postgres.
# If PowerShell refuses to run it:  powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

# Stop at the first command that fails, like `set -e` in dev.sh.
function Check($what) { if ($LASTEXITCODE -ne 0) { throw "$what failed (exit code $LASTEXITCODE)" } }

foreach ($tool in 'docker', 'python', 'npm') {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "$tool was not found. Install Docker Desktop, Python 3.11+ and Node 20+ first (see the README)."
    }
}

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host 'Created .env from .env.example; add your ANTHROPIC_API_KEY to it.'
}

docker compose up -d --wait db; Check 'docker compose'

Set-Location backend
if (-not (Test-Path .venv)) { python -m venv .venv; Check 'python -m venv' }
& .venv\Scripts\python.exe -m pip install -q -r requirements-dev.txt; Check 'pip install'
& .venv\Scripts\python.exe -m pipeline init-db; Check 'init-db'
$api = Start-Process -FilePath (Resolve-Path .venv\Scripts\python.exe) -NoNewWindow -PassThru `
    -ArgumentList '-m', 'uvicorn', 'app.main:app', '--reload', '--port', '8000'

try {
    Set-Location ..\frontend
    if (-not (Test-Path node_modules)) { npm install; Check 'npm install' }
    npm run dev
}
finally {
    # --reload runs the server in a child process, so stop the whole tree.
    if ($api -and -not $api.HasExited) { taskkill /PID $api.Id /T /F | Out-Null }
}
