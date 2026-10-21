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
    Write-Host "[1/6] Cloning Cephalo repository..." -ForegroundColor Yellow
    if (Get-Command git -ErrorAction SilentlyContinue) {
        git clone https://github.com/LaptopKing/Cephalo.git $TargetDir
    } else {
        Write-Error "Git is required to install Cephalo. Please install Git first."
    }
} else {
    Write-Host "[1/6] Using Cephalo at $TargetDir" -ForegroundColor Green
}

# 3. Locate Python (Bypassing Windows Store 0-byte stub)
$KnownPythons = @(
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
    "$env:ProgramFiles\Python\Python312\python.exe",
    "$env:ProgramFiles\Python\Python311\python.exe"
)

$PythonCmd = $null
foreach ($p in $KnownPythons) {
    if (Test-Path $p) {
        $PythonCmd = $p
        break
    }
}

if (-not $PythonCmd) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $PythonCmd = "py"
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $testVer = & python --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $PythonCmd = "python"
        }
    }
}

if (-not $PythonCmd) {
    Write-Error "Python 3.10+ is required. Please install Python from https://www.python.org/downloads/."
}

Write-Host "[2/6] Installing core dependencies..." -ForegroundColor Yellow
& $PythonCmd -m pip install --quiet --upgrade pip
& $PythonCmd -m pip install --quiet -r (Join-Path $TargetDir "requirements.txt")

# 4. Install Chromium browser for Playwright dynamic crawler
Write-Host "[3/6] Setting up Chromium crawler engine..." -ForegroundColor Yellow
& $PythonCmd -m playwright install chromium

# 5. Add to User PATH & Antigravity bin if available
Write-Host "[4/6] Configuring 'cephalo' CLI command..." -ForegroundColor Yellow
$AgyBin = Join-Path $HOME ".gemini\antigravity\bin"
if (Test-Path $AgyBin) {
    Copy-Item (Join-Path $TargetDir "cephalo.bat") (Join-Path $AgyBin "cephalo.bat") -Force
    Write-Host "      Configured cephalo.bat into Antigravity bin ($AgyBin)." -ForegroundColor Gray
}

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$TargetDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$TargetDir", "User")
    $env:Path = "$env:Path;$TargetDir"
    Write-Host "      Added $TargetDir to User PATH." -ForegroundColor Gray
}

# 6. Automatic Agent Harness Integration (Google Antigravity & Claude Code)
Write-Host "[5/6] Configuring Agent Harness integrations..." -ForegroundColor Yellow

# A. Google Antigravity Global Rule
$AgyBase = Join-Path $HOME ".gemini"
if (Test-Path $AgyBase) {
    $AgyRulesDir = Join-Path $AgyBase "config\rules"
    if (-not (Test-Path $AgyRulesDir)) {
        New-Item -ItemType Directory -Path $AgyRulesDir -Force | Out-Null
    }

    $TemplatePath = Join-Path $TargetDir "integrations\antigravity\cephalo_second_brain.md"
    if (Test-Path $TemplatePath) {
        $RuleContent = (Get-Content -Path $TemplatePath -Raw -Encoding UTF8) -replace '\{\{CEPHALO_DIR\}\}', $TargetDir
    } else {
        $RuleContent = "# Cephalo Second Brain & Autonomous Memory Policy`n`nLocated at: $TargetDir`n`nAlways consult $TargetDir\USER_PROFILE.md and use 'cephalo search <query>' before answering."
    }

    $AgyRuleTarget = Join-Path $AgyRulesDir "cephalo_second_brain.md"
    Set-Content -Path $AgyRuleTarget -Value $RuleContent -Encoding UTF8
    Write-Host "      Configured Antigravity global rule at: $AgyRuleTarget" -ForegroundColor Green
}

# 7. Verify Installation & Database Health
Write-Host "[6/6] Initializing Cephalo..." -ForegroundColor Yellow
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
