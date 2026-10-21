# ==============================================================================
# Cephalo - 1-Command Automated Installer (Windows PowerShell)
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "   ____ _____ ____  _   _    _    _     ___  " -ForegroundColor Cyan
Write-Host "  / ___| ____|  _ \| | | |  / \  | |   / _ \ " -ForegroundColor Cyan
Write-Host " | |   |  _| | |_) | |_| | / _ \ | |  | | | |" -ForegroundColor Cyan
Write-Host " | |___| |___|  __/|  _  |/ ___ \| |__| |_| |" -ForegroundColor Cyan
Write-Host "  \____|_____|_|   |_| |_/_/   \_\_____\___/ " -ForegroundColor Cyan
Write-Host ""
Write-Host "  >> Sovereign Local Memory & Cognitive Coprocessor <<" -ForegroundColor Gray
Write-Host ""

# 1. Determine Target Directory
$TargetDir = if (Test-Path "brain.py") {
    (Get-Location).Path
} else {
    Join-Path $HOME ".cephalo"
}

# 2. Clone if not in repo
if (-not (Test-Path (Join-Path $TargetDir "brain.py"))) {
    Write-Host "[1/5] Cloning Cephalo repository..." -ForegroundColor Yellow
    if (Get-Command git -ErrorAction SilentlyContinue) {
        git clone https://github.com/LaptopKing/Cephalo.git $TargetDir
    } else {
        Write-Error "Git is required to install Cephalo. Please install Git first."
    }
} else {
    Write-Host "[1/5] Using Cephalo at $TargetDir" -ForegroundColor Green
}

# 3. Locate Python
$PythonCmd = if (Get-Command python -ErrorAction SilentlyContinue) {
    "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    "py"
} else {
    Write-Error "Python 3.10+ is required. Please install Python from https://www.python.org/downloads/."
}

Write-Host "[2/5] Installing core dependencies..." -ForegroundColor Yellow
& $PythonCmd -m pip install --quiet --upgrade pip
& $PythonCmd -m pip install --quiet -r (Join-Path $TargetDir "requirements.txt")

# 4. Install Chromium browser for Playwright dynamic crawler
Write-Host "[3/5] Setting up Chromium crawler engine..." -ForegroundColor Yellow
& $PythonCmd -m playwright install chromium

# 5. Add to User PATH
Write-Host "[4/5] Configuring 'cephalo' CLI command..." -ForegroundColor Yellow
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$TargetDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$TargetDir", "User")
    $env:Path = "$env:Path;$TargetDir"
    Write-Host "      Added $TargetDir to User PATH." -ForegroundColor Gray
}

# 6. Verify Installation
Write-Host "[5/5] Initializing Cephalo..." -ForegroundColor Yellow
& $PythonCmd (Join-Path $TargetDir "brain.py") status

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  [+] Cephalo Installed Successfully!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "You can now run 'cephalo' from any terminal window:" -ForegroundColor White
Write-Host "  cephalo status           # Check memory & database health" -ForegroundColor Gray
Write-Host "  cephalo search <query>   # Query Cephalo with hybrid search" -ForegroundColor Gray
Write-Host "  cephalo web <query>      # Live web research" -ForegroundColor Gray
Write-Host "  cephalo record <text>    # Store a memory with zero-leak privacy" -ForegroundColor Gray
Write-Host ""
