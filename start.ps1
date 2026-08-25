# ============================================================
#  TIDE Registry - One-Command Project Launcher
#  Starts all services in separate windows:
#    M5  - Backend Hub          (port 8000)
#    M1  - AI/ML Intelligence   (port 8001)
#    M2  - Digital Twin / GIS   (port 8002)
#    BC  - Blockchain HardHat   (port 8545)
#  Then opens the frontend in your default browser.
# ============================================================

$Root    = $PSScriptRoot
$Venv    = "$Root\venv\Scripts\python.exe"
$Node    = "$Root\blockchain\node_modules\.bin\hardhat"
$Browser = "http://localhost:8000"

# ── Colour helpers ──────────────────────────────────────────
function Write-Header { param($msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok     { param($msg) Write-Host "    [OK] $msg"  -ForegroundColor Green }
function Write-Warn   { param($msg) Write-Host "    [!]  $msg"  -ForegroundColor Yellow }
function Write-Err    { param($msg) Write-Host "    [X]  $msg"  -ForegroundColor Red }

# ── Preflight checks ────────────────────────────────────────
Write-Header "TIDE Registry Startup - Preflight Checks"

$allGood = $true

if (-not (Test-Path $Venv)) {
    Write-Err  "Python venv not found at: $Venv"
    Write-Warn "Fix: python -m venv venv && .\venv\Scripts\Activate.ps1"
    Write-Warn "     pip install -r backend\requirements.txt"
    Write-Warn "     pip install -r ai\requirements.txt"
    Write-Warn "     pip install -r digital-twin\requirements.txt"
    $allGood = $false
} else {
    Write-Ok "Python venv found"
}

if (-not (Test-Path "$Root\blockchain\node_modules")) {
    Write-Err  "Blockchain node_modules missing"
    Write-Warn "Fix: cd blockchain && npm install"
    $allGood = $false
} else {
    Write-Ok "Blockchain node_modules found"
}

if (-not $allGood) {
    Write-Host "`n  Fix the issues above and re-run start.ps1" -ForegroundColor Red
    exit 1
}

# ── Launch M5 - Backend Hub (port 8000) ─────────────────────
Write-Header "Starting M5 - Backend Hub  (port 8000)"
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "& { `$Host.UI.RawUI.WindowTitle = 'TIDE | Backend :8000'; " +
    "Write-Host 'M5 Backend Hub - port 8000' -ForegroundColor Cyan; " +
    "Set-Location '$Root\backend'; " +
    "& '$Venv' -m uvicorn api:app --reload --host 0.0.0.0 --port 8000 }"
)
Write-Ok "Backend window launched"

# ── Launch M1 - AI/ML Intelligence (port 8001) ──────────────
Write-Header "Starting M1 - AI/ML Service (port 8001)"
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "& { `$Host.UI.RawUI.WindowTitle = 'TIDE | AI/ML :8001'; " +
    "Write-Host 'M1 AI/ML Service - port 8001' -ForegroundColor Magenta; " +
    "Set-Location '$Root\ai'; " +
    "& '$Venv' -m uvicorn api:app --reload --host 0.0.0.0 --port 8001 }"
)
Write-Ok "AI/ML window launched"

# ── Launch M2 - Digital Twin / GIS Engine (port 8002) ───────
Write-Header "Starting M2 - Digital Twin  (port 8002)"
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "& { `$Host.UI.RawUI.WindowTitle = 'TIDE | DigTwin :8002'; " +
    "Write-Host 'M2 Digital Twin - port 8002' -ForegroundColor Yellow; " +
    "Set-Location '$Root\digital-twin'; " +
    "& '$Venv' -m uvicorn api:app --reload --host 0.0.0.0 --port 8002 }"
)
Write-Ok "Digital Twin window launched"

# ── Launch BC - Blockchain Hardhat Node (port 8545) ─────────
Write-Header "Starting BC - Blockchain Hardhat Node (port 8545)"
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "& { `$Host.UI.RawUI.WindowTitle = 'TIDE | Blockchain :8545'; " +
    "Write-Host 'BC Hardhat Node - port 8545' -ForegroundColor Blue; " +
    "Set-Location '$Root\blockchain'; " +
    "npx hardhat node }"
)
Write-Ok "Blockchain node window launched"

# ── Wait for services to bind, then open browser ────────────
Write-Header "Waiting 4 s for services to bind..."
Start-Sleep -Seconds 4

Write-Ok "Opening browser at $Browser"
Start-Process $Browser

# -- Summary --------------------------------------------------
Write-Host ""
Write-Host "  +----------------------------------------------+" -ForegroundColor DarkCyan
Write-Host "  |   TIDE Registry - All Services Launched      |" -ForegroundColor DarkCyan
Write-Host "  +----------------------------------------------+" -ForegroundColor DarkCyan
Write-Host "  |  Backend    ->  http://localhost:8000        |" -ForegroundColor White
Write-Host "  |  AI/ML      ->  http://localhost:8001/docs   |" -ForegroundColor White
Write-Host "  |  DigTwin    ->  http://localhost:8002/docs   |" -ForegroundColor White
Write-Host "  |  Blockchain ->  http://localhost:8545        |" -ForegroundColor White
Write-Host "  +----------------------------------------------+" -ForegroundColor DarkCyan
Write-Host ""
Write-Host "  Close individual windows or press Ctrl+C to stop each service." -ForegroundColor DarkGray
Write-Host ""
