# Local development on Windows 10/11: starts Postgres (Docker), the API (:8000) and the web app (:5173).
# Easiest: double-click dev.bat. Or in PowerShell: powershell -ExecutionPolicy Bypass -File .\dev.ps1
# Needs: Docker Desktop (running), Python 3.12+, Node.js 20+.
# The API and web app open in their own windows; close those windows to stop them.
#   docker compose -f docker-compose.dev.yml down   # to stop the DB too

# -NoDemo (or double-click dev_without_data.bat) never loads demo data: an empty database gets only the
# first admin login, the cash account and the chart of accounts; a database with data is left as it is.
param([switch]$NoDemo)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

function Fail($msg) {
    Write-Host ""
    Write-Host "ERROR: $msg" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}
function Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Need($cmd, $hint) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { Fail "$cmd was not found. $hint" }
}

Need docker "Install Docker Desktop from https://www.docker.com/products/docker-desktop and start it."
Need node "Install Node.js 20 LTS from https://nodejs.org"
Need npm "Install Node.js 20 LTS from https://nodejs.org"

# Prefer the Python launcher (py -3.12); fall back to python on PATH.
$Py = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.12 --version *> $null
    if ($LASTEXITCODE -eq 0) { $Py = @("py", "-3.12") }
}
if (-not $Py -and (Get-Command python -ErrorAction SilentlyContinue)) { $Py = @("python") }
if (-not $Py) { Fail "Python 3.12 was not found. Install it from https://www.python.org (tick 'Add python.exe to PATH')." }

# Native commands do not throw in PowerShell, so check exit codes ourselves.
$ErrorActionPreference = "Continue"

Step "Starting database"
docker info *> $null
if ($LASTEXITCODE -ne 0) { Fail "Docker is not running. Start Docker Desktop, wait until it says 'running', then try again." }
docker compose -f docker-compose.dev.yml up -d
if ($LASTEXITCODE -ne 0) { Fail "Could not start the database container." }
$tries = 0
do {
    Start-Sleep -Seconds 1
    docker compose -f docker-compose.dev.yml exec -T db pg_isready -U hisaab *> $null
    $tries++
} while ($LASTEXITCODE -ne 0 -and $tries -lt 60)
if ($LASTEXITCODE -ne 0) { Fail "The database did not become ready within 60 seconds." }

Set-Location "$Root\backend"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Step "Created backend\.env from .env.example"
}

$VenvPy = "$Root\backend\.venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
    Step "Creating Python environment (first run, takes a few minutes)"
    $exe = $Py[0]; $pyArgs = @($Py | Select-Object -Skip 1)
    & $exe @pyArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) { Fail "Could not create the Python virtual environment." }
    & $VenvPy -m pip install --upgrade pip
    & $VenvPy -m pip install -e ".[dev]"
    if ($LASTEXITCODE -ne 0) { Fail "Installing backend packages failed (see the messages above)." }
}

Step "Migrating database"
& $VenvPy -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Fail "Database migration failed (see the messages above)." }

if ($NoDemo) {
    Step "No demo data: making sure the first admin, cash account and chart exist"
    & $VenvPy -m app.bootstrap
    if ($LASTEXITCODE -ne 0) { Fail "Setting up the first admin failed (see the messages above)." }
} else {
    Step "Loading demo data (skipped if the database already has data)"
    & $VenvPy -m app.seed
}

Set-Location "$Root\frontend"
if (-not (Test-Path "node_modules")) {
    Step "Installing web app packages (first run, takes a few minutes)"
    npm ci
    if ($LASTEXITCODE -ne 0) { Fail "npm ci failed (see the messages above)." }
}

Step "Starting API on http://127.0.0.1:8000 (new window)"
Start-Process powershell -WorkingDirectory "$Root\backend" -ArgumentList @(
    "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle = 'Hisaab API'; & '$VenvPy' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
)

Step "Starting web app on http://127.0.0.1:5173 (new window)"
Start-Process powershell -WorkingDirectory "$Root\frontend" -ArgumentList @(
    "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle = 'Hisaab Web'; npm run dev -- --host 127.0.0.1"
)

Start-Sleep -Seconds 6
Start-Process "http://127.0.0.1:5173/admin/login"

Write-Host ""
Write-Host "Hisaab Portal is starting:" -ForegroundColor Green
Write-Host "  Web app : http://127.0.0.1:5173"
if ($NoDemo) {
    Write-Host "  Owner   : http://127.0.0.1:5173/admin/login       (BOOTSTRAP_ADMIN_PHONE / _PASSWORD in backend\.env)"
    Write-Host "  Munshi  : http://127.0.0.1:5173/accountant/login  (create the munshi in Admin > Users)"
} else {
    Write-Host "  Owner   : http://127.0.0.1:5173/admin/login       (admin / admin12345)"
    Write-Host "  Munshi  : http://127.0.0.1:5173/accountant/login  (munshi / munshi12345)"
}
Write-Host "  API docs: http://127.0.0.1:8000/api/docs"
Write-Host ""
Write-Host "Close the 'Hisaab API' and 'Hisaab Web' windows to stop."
Read-Host "Press Enter to close this window"
