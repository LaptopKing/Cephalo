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
$TargetDir = if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot "brain.py"))) {
    $PSScriptRoot
} elseif (Test-Path (Join-Path $HOME ".gemini\antigravity\scratch\second-brain\brain.py")) {
    Join-Path $HOME ".gemini\antigravity\scratch\second-brain"
} elseif (Test-Path "brain.py") {
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

# Generate deterministic cephalo.bat with bound target directory
$BatContent = @"
@echo off
setlocal enabledelayedexpansion
set "SECOND_BRAIN_DIR=$TargetDir"

if not exist "%SECOND_BRAIN_DIR%\brain.py" (
    echo Error: Cephalo brain.py not found at "%SECOND_BRAIN_DIR%\brain.py"
    exit /b 1
)

pushd "%SECOND_BRAIN_DIR%"

for %%V in (Python312 Python311 Python313 Python310) do (
    if exist "%LOCALAPPDATA%\Programs\Python\%%V\python.exe" (
        "%LOCALAPPDATA%\Programs\Python\%%V\python.exe" "%SECOND_BRAIN_DIR%\brain.py" %*
        popd
        goto :eof
    )
)

for %%V in (Python312 Python311 Python313 Python310) do (
    if exist "%ProgramFiles%\Python\%%V\python.exe" (
        "%ProgramFiles%\Python\%%V\python.exe" "%SECOND_BRAIN_DIR%\brain.py" %*
        popd
        goto :eof
    )
)

where py >nul 2>nul
if %errorlevel% equ 0 (
    py "%SECOND_BRAIN_DIR%\brain.py" %*
    popd
    goto :eof
)

python "%SECOND_BRAIN_DIR%\brain.py" %*
if %errorlevel% equ 0 (
    popd
    goto :eof
)

popd
echo Error: Python 3.10+ was not found on your system.
exit /b 1
"@

Set-Content -Path (Join-Path $TargetDir "cephalo.bat") -Value $BatContent -Encoding ASCII

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

# 6. Automatic Multi-Harness Integrations (Antigravity, Claude Code, Cursor, Codex)
Write-Host "[5/6] Configuring Multi-Harness Agent integrations..." -ForegroundColor Yellow

# A. Google Antigravity Integration (Plugin, Skills, Rules, Lifecycle Hooks)
$AgyBase = Join-Path $HOME ".gemini"
if (Test-Path $AgyBase) {
    # 1. Antigravity Plugin (~/.gemini/config/plugins/cephalo)
    $PluginDir = Join-Path $AgyBase "config\plugins\cephalo"
    $PluginRulesDir = Join-Path $PluginDir "rules"
    $PluginSkillsDir = Join-Path $PluginDir "skills\cephalo"
    New-Item -ItemType Directory -Path $PluginRulesDir -Force | Out-Null
    New-Item -ItemType Directory -Path $PluginSkillsDir -Force | Out-Null

    # Plugin Manifest
    $PluginManifest = @{
        name = "cephalo"
        description = "Cephalo Omnipresent Autonomous Second Brain and Personal Memory Engine"
    } | ConvertTo-Json
    Set-Content -Path (Join-Path $PluginDir "plugin.json") -Value $PluginManifest -Encoding UTF8

    # Skill File into plugin & global skills
    $SkillSource = Join-Path $TargetDir "integrations\antigravity\SKILL.md"
    if (Test-Path $SkillSource) {
        Copy-Item $SkillSource (Join-Path $PluginSkillsDir "SKILL.md") -Force
        $GlobalSkillsDir = Join-Path $AgyBase "config\skills\cephalo"
        New-Item -ItemType Directory -Path $GlobalSkillsDir -Force | Out-Null
        Copy-Item $SkillSource (Join-Path $GlobalSkillsDir "SKILL.md") -Force
        Write-Host "      Configured Antigravity Cephalo Skill in plugin & global skills." -ForegroundColor Green
    }

    # Consolidated Rules into plugin
    $TemplatePath = Join-Path $TargetDir "integrations\antigravity\cephalo_second_brain.md"
    if (Test-Path $TemplatePath) {
        $RuleContent = (Get-Content -Path $TemplatePath -Raw -Encoding UTF8) -replace '\{\{CEPHALO_DIR\}\}', $TargetDir
    } else {
        $RuleContent = "# Cephalo Second Brain & Autonomous Memory Policy`n`nLocated at: $TargetDir`n`nAlways consult $TargetDir\USER_PROFILE.md and use 'cephalo search <query>' before answering."
    }

    Set-Content -Path (Join-Path $PluginRulesDir "AGENTS.md") -Value $RuleContent -Encoding UTF8
    Set-Content -Path (Join-Path $PluginRulesDir "GEMINI.md") -Value $RuleContent -Encoding UTF8

    # Global Rules
    $AgyRulesDir = Join-Path $AgyBase "config\rules"
    New-Item -ItemType Directory -Path $AgyRulesDir -Force | Out-Null
    Set-Content -Path (Join-Path $AgyRulesDir "cephalo_second_brain.md") -Value $RuleContent -Encoding UTF8
    Write-Host "      Configured Antigravity global rules." -ForegroundColor Green

    # Lifecycle Hooks configuration (SessionStart, PreInvocation, Stop)
    $AutoHarvestPath = Join-Path $TargetDir "auto_harvest.py"
    $HooksJson = @"
{
  "cephalo-autonomous-brain": {
    "enabled": true,
    "SessionStart": [
      {
        "type": "command",
        "command": "\"$PythonCmd\" \"$AutoHarvestPath\" --session-start",
        "timeout": 15
      }
    ],
    "PreInvocation": [
      {
        "type": "command",
        "command": "\"$PythonCmd\" \"$AutoHarvestPath\" --pre-invocation",
        "timeout": 15
      }
    ],
    "Stop": [
      {
        "type": "command",
        "command": "\"$PythonCmd\" \"$AutoHarvestPath\" --stop-hook",
        "timeout": 15
      }
    ]
  }
}
"@
    Set-Content -Path (Join-Path $PluginDir "hooks.json") -Value $HooksJson -Encoding UTF8
    Set-Content -Path (Join-Path $AgyBase "config\hooks.json") -Value $HooksJson -Encoding UTF8
    Write-Host "      Configured Antigravity autonomous lifecycle hooks (SessionStart, PreInvocation, Stop)." -ForegroundColor Green

    # Register in config.json
    $ConfigFile = Join-Path $AgyBase "config\config.json"
    if (Test-Path $ConfigFile) {
        try {
            $ConfigObj = Get-Content -Path $ConfigFile -Raw -Encoding UTF8 | ConvertFrom-Json
            if (-not $ConfigObj.plugins) {
                $ConfigObj | Add-Member -NotePropertyName "plugins" -NotePropertyValue (New-Object PSObject)
            }
            if (-not $ConfigObj.plugins.cephalo) {
                $ConfigObj.plugins | Add-Member -NotePropertyName "cephalo" -NotePropertyValue ([PSCustomObject]@{ enabled = $true })
            } else {
                $ConfigObj.plugins.cephalo.enabled = $true
            }
            $ConfigObj | ConvertTo-Json -Depth 5 | Set-Content -Path $ConfigFile -Encoding UTF8
            Write-Host "      Registered and enabled Cephalo plugin in config.json." -ForegroundColor Green
        } catch {}
    }
}

# B. Claude Code Integration
$ClaudeDir = Join-Path $HOME ".claude"
if (Test-Path $ClaudeDir) {
    $ClaudeRuleTarget = Join-Path $ClaudeDir "CLAUDE.md"
    Copy-Item (Join-Path $TargetDir "CLAUDE.md") $ClaudeRuleTarget -Force
    Write-Host "      Configured Claude Code global policy: $ClaudeRuleTarget" -ForegroundColor Green
}

# C. Universal Harness Specifications (AGENTS.md & GEMINI.md)
$UniversalAgentsFile = Join-Path $HOME "AGENTS.md"
Copy-Item (Join-Path $TargetDir "AGENTS.md") $UniversalAgentsFile -Force
$UniversalGeminiFile = Join-Path $HOME "GEMINI.md"
Copy-Item (Join-Path $TargetDir "AGENTS.md") $UniversalGeminiFile -Force
Write-Host "      Configured Universal AGENTS.md and GEMINI.md in home directory." -ForegroundColor Green

# 7. Verify Installation & Database Health
Write-Host "[6/6] Initializing Cephalo..." -ForegroundColor Yellow
& $PythonCmd (Join-Path $TargetDir "brain.py") status

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  [+] Cephalo Installed & Configured Across Agent Harnesses!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "Autonomous Features Active:" -ForegroundColor White
Write-Host "  • All user prompts automatically audited and logged." -ForegroundColor Gray
Write-Host "  • Token-efficient dynamic context injection (silent on new topics)." -ForegroundColor Gray
Write-Host "  • Antigravity PreInvocation & Stop lifecycle hooks enabled." -ForegroundColor Gray
Write-Host "  • Multi-harness support (Antigravity, Claude Code, Cursor, Codex)." -ForegroundColor Gray
Write-Host ""
Write-Host "Manual CLI commands available anywhere:" -ForegroundColor White
Write-Host "  cephalo status           # System & LanceDB health" -ForegroundColor Gray
Write-Host "  cephalo search <query>   # Query Cephalo with hybrid search" -ForegroundColor Gray
Write-Host "  cephalo harvest          # Audit past conversation transcripts" -ForegroundColor Gray
Write-Host "  cephalo record <text>    # Explicitly store memory" -ForegroundColor Gray
Write-Host ""
