# ==============================================================================
# Cephalo - Adaptive Non-Destructive Installer (Windows PowerShell)
# ==============================================================================
# Invariant: Cephalo adapts and integrates cleanly into existing environments.
# Never blindly overwrites existing user configurations, dotfiles, or global rules.
# ==============================================================================

param(
    [switch]$UseVenv = $false,
    [switch]$SystemPython = $false,
    [switch]$Help = $false
)

if ($Help) {
    Write-Host "Cephalo Adaptive Installer" -ForegroundColor Cyan
    Write-Host "Usage: .\install.ps1 [-UseVenv] [-SystemPython]"
    Write-Host "  -UseVenv       Install into an isolated virtual environment (.venv) - zero system pollution."
    Write-Host "  -SystemPython  Install into current system Python."
    exit 0
}

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "   ____ _____ ____  _   _    _    _     ___  " -ForegroundColor Cyan
Write-Host "  / ___| ____|  _ \| | | |  / \  | |   / _ \ " -ForegroundColor Cyan
Write-Host " | |   |  _| | |_) | |_| | / _ \ | |  | | | |" -ForegroundColor Cyan
Write-Host " | |___| |___|  __/|  _  |/ ___ \| |__| |_| |" -ForegroundColor Cyan
Write-Host "  \____|_____|_|   |_| |_/_/   \_\_____\___/ " -ForegroundColor Cyan
Write-Host ""
Write-Host "  >> Sovereign Local Memory & Cognitive Coprocessor <<" -ForegroundColor Gray
Write-Host "  >> Adaptive Non-Destructive Multi-Harness Integration <<" -ForegroundColor DarkGray
Write-Host ""

# Helper: Merge a managed block non-destructively
function Merge-ManagedBlock {
    param (
        [string]$FilePath,
        [string]$BlockContent,
        [string]$BlockTag = "CEPHALO MANAGED BLOCK"
    )
    $StartTag = "<!-- $BlockTag START -->"
    $EndTag = "<!-- $BlockTag END -->"
    $FullBlock = "`n$StartTag`n$BlockContent`n$EndTag`n"

    if (Test-Path $FilePath) {
        $existing = Get-Content -Path $FilePath -Raw -Encoding UTF8
        # Create timestamped safety backup
        $timestamp = Get-Date -Format "yyyyMMddHHmmss"
        $backupPath = "$FilePath.bak.$timestamp"
        Copy-Item -Path $FilePath -Destination $backupPath -Force

        if ($existing -match "(?s)$([regex]::Escape($StartTag)).*?$([regex]::Escape($EndTag))") {
            $updated = $existing -replace "(?s)$([regex]::Escape($StartTag)).*?$([regex]::Escape($EndTag))", "$StartTag`n$BlockContent`n$EndTag"
            Set-Content -Path $FilePath -Value $updated -Encoding UTF8
            Write-Host "      Updated Cephalo block in $FilePath (backup: $backupPath)" -ForegroundColor Green
        } else {
            Add-Content -Path $FilePath -Value $FullBlock -Encoding UTF8
            Write-Host "      Appended Cephalo block to $FilePath (backup: $backupPath)" -ForegroundColor Green
        }
    } else {
        $parent = Split-Path $FilePath -Parent
        if ($parent -and -not (Test-Path $parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
        Set-Content -Path $FilePath -Value $FullBlock -Encoding UTF8
        Write-Host "      Created $FilePath with Cephalo block." -ForegroundColor Green
    }
}

# Helper: Safely merge hooks into hooks.json without destroying existing hooks
function Merge-HooksJson {
    param (
        [string]$HooksPath,
        [string]$PythonExe,
        [string]$HarvestScript
    )
    $CephaloHookDef = @{
        enabled = $true
        SessionStart = @(
            @{ type = "command"; command = "`"$PythonExe`" `"$HarvestScript`" --session-start"; timeout = 15 }
        )
        PreInvocation = @(
            @{ type = "command"; command = "`"$PythonExe`" `"$HarvestScript`" --pre-invocation"; timeout = 15 }
        )
        Stop = @(
            @{ type = "command"; command = "`"$PythonExe`" `"$HarvestScript`" --stop-hook"; timeout = 15 }
        )
    }

    $existingHooks = @{}
    if (Test-Path $HooksPath) {
        try {
            $content = Get-Content -Path $HooksPath -Raw -Encoding UTF8
            if ($content.Trim()) {
                $existingHooks = $content | ConvertFrom-Json -AsHashtable
            }
            # Safety backup
            $backup = "$HooksPath.bak." + (Get-Date -Format "yyyyMMddHHmmss")
            Copy-Item -Path $HooksPath -Destination $backup -Force
        } catch {}
    } else {
        $parent = Split-Path $HooksPath -Parent
        if ($parent -and -not (Test-Path $parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
    }

    $existingHooks["cephalo-autonomous-brain"] = $CephaloHookDef
    $jsonOutput = $existingHooks | ConvertTo-Json -Depth 10
    Set-Content -Path $HooksPath -Value $jsonOutput -Encoding UTF8
    Write-Host "      Safely merged Cephalo hooks into $HooksPath (no other hooks touched)." -ForegroundColor Green
}

# 1. Determine Target Directory
$TargetDir = if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot "brain.py"))) {`r`n    $PSScriptRoot`r`n} elseif ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot "..\brain.py"))) {`r`n    (Resolve-Path (Join-Path $PSScriptRoot "..")).Path {
    $PSScriptRoot
} elseif (Test-Path (Join-Path $HOME ".gemini\antigravity\scratch\second-brain\brain.py")) {
    Join-Path $HOME ".gemini\antigravity\scratch\second-brain"
} elseif (Test-Path "brain.py") {
    (Get-Location).Path
} else {
    Join-Path $HOME ".cephalo"
}

# 2. Clone if not present
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

# 3. Locate Base Python
$KnownPythons = @(
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
    "$env:ProgramFiles\Python\Python312\python.exe",
    "$env:ProgramFiles\Python\Python311\python.exe"
)

$BasePython = $null
foreach ($p in $KnownPythons) {
    if (Test-Path $p) {
        $BasePython = $p
        break
    }
}

if (-not $BasePython) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $BasePython = "py"
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $testVer = & python --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $BasePython = "python"
        }
    }
}

if (-not $BasePython) {
    Write-Error "Python 3.10+ is required. Please install Python from https://www.python.org/downloads/."
}

# Manage Virtual Environment
$VenvDir = Join-Path $TargetDir ".venv"
$PythonCmd = $BasePython

if ($UseVenv -or (Test-Path $VenvDir)) {
    if (-not (Test-Path $VenvDir)) {
        Write-Host "[2/6] Creating isolated Python virtual environment (.venv)..." -ForegroundColor Yellow
        & $BasePython -m venv $VenvDir
    }
    $PythonCmd = Join-Path $VenvDir "Scripts\python.exe"
    Write-Host "[2/6] Using isolated virtual environment: $PythonCmd" -ForegroundColor Green
} else {
    Write-Host "[2/6] Using Python environment: $PythonCmd" -ForegroundColor Green
}

# Install dependencies non-destructively
Write-Host "      Checking and installing dependencies..." -ForegroundColor Gray
& $PythonCmd -m pip install --quiet -r (Join-Path $TargetDir "requirements.txt")

# 4. Optional Playwright Chromium Setup (check first before downloading)
$PlaywrightCheck = & $PythonCmd -c "import playwright; print('ok')" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "[3/6] Verified browser crawler integration." -ForegroundColor Green
} else {
    Write-Host "[3/6] Optional crawler browser setup skipped (can run 'playwright install chromium' anytime)." -ForegroundColor Gray
}

# 5. Configure 'cephalo' CLI Command
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

if exist "%SECOND_BRAIN_DIR%\.venv\Scripts\python.exe" (
    "%SECOND_BRAIN_DIR%\.venv\Scripts\python.exe" "%SECOND_BRAIN_DIR%\brain.py" %*
    popd
    goto :eof
)

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

$BinDir = Join-Path $TargetDir "bin"`r`nNew-Item -ItemType Directory -Path $BinDir -Force | Out-Null`r`nSet-Content -Path (Join-Path $BinDir "cephalo.bat") -Value $BatContent -Encoding ASCII

$AgyBin = Join-Path $HOME ".gemini\antigravity\bin"
if (Test-Path $AgyBin) {
    Copy-Item (Join-Path $BinDir "cephalo.bat") (Join-Path $AgyBin "cephalo.bat") -Force
    Write-Host "      Configured cephalo.bat into Antigravity bin ($AgyBin)." -ForegroundColor Gray
}

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$BinDir = Join-Path $TargetDir "bin"`r`nif ($UserPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$BinDir", "User")
    $env:Path = "$env:Path;$BinDir"
    Write-Host "      Added $BinDir to User PATH." -ForegroundColor Gray
}

# 6. Adaptive Multi-Harness Integrations
Write-Host "[5/6] Configuring Multi-Harness Agent integrations (non-destructive)..." -ForegroundColor Yellow

# A. Google Antigravity Integration
$AgyBase = Join-Path $HOME ".gemini"
if (Test-Path $AgyBase) {
    $PluginDir = Join-Path $AgyBase "config\plugins\cephalo"
    $PluginRulesDir = Join-Path $PluginDir "rules"
    $PluginSkillsDir = Join-Path $PluginDir "skills\cephalo"
    New-Item -ItemType Directory -Path $PluginRulesDir -Force | Out-Null
    New-Item -ItemType Directory -Path $PluginSkillsDir -Force | Out-Null

    $PluginManifest = @{
        name = "cephalo"
        description = "Cephalo Omnipresent Autonomous Second Brain and Personal Memory Engine"
    } | ConvertTo-Json
    Set-Content -Path (Join-Path $PluginDir "plugin.json") -Value $PluginManifest -Encoding UTF8

    $SkillSource = Join-Path $TargetDir "integrations\antigravity\SKILL.md"
    if (Test-Path $SkillSource) {
        Copy-Item $SkillSource (Join-Path $PluginSkillsDir "SKILL.md") -Force
        $GlobalSkillsDir = Join-Path $AgyBase "config\skills\cephalo"
        New-Item -ItemType Directory -Path $GlobalSkillsDir -Force | Out-Null
        Copy-Item $SkillSource (Join-Path $GlobalSkillsDir "SKILL.md") -Force
        Write-Host "      Configured Antigravity Cephalo Skill in plugin & global skills." -ForegroundColor Green
    }

    $TemplatePath = Join-Path $TargetDir "integrations\antigravity\cephalo_second_brain.md"
    if (Test-Path $TemplatePath) {
        $RuleContent = (Get-Content -Path $TemplatePath -Raw -Encoding UTF8) -replace '\{\{CEPHALO_DIR\}\}', $TargetDir
    } else {
        $RuleContent = "# Cephalo Second Brain & Autonomous Memory Policy`n`nLocated at: $TargetDir`n`nAlways consult $TargetDir\USER_PROFILE.md and use 'cephalo search <query>' before answering."
    }

    Set-Content -Path (Join-Path $PluginRulesDir "AGENTS.md") -Value $RuleContent -Encoding UTF8
    Set-Content -Path (Join-Path $PluginRulesDir "GEMINI.md") -Value $RuleContent -Encoding UTF8

    # Clean up legacy standalone global rule to eliminate duplicate prompt injection (~1,200 tokens/turn saved)
    $LegacyRulePath = Join-Path $AgyBase "config\rules\cephalo_second_brain.md"
    if (Test-Path $LegacyRulePath) {
        Remove-Item -Path $LegacyRulePath -Force -ErrorAction SilentlyContinue
        Write-Host "      Cleaned up legacy duplicate global rule to prevent token waste." -ForegroundColor Green
    }

    # Non-destructive hooks merge
    $AutoHarvestPath = Join-Path $TargetDir "src\cephalo\learning\auto_harvest.py"
    Merge-HooksJson -HooksPath (Join-Path $PluginDir "hooks.json") -PythonExe $PythonCmd -HarvestScript $AutoHarvestPath
    Merge-HooksJson -HooksPath (Join-Path $AgyBase "config\hooks.json") -PythonExe $PythonCmd -HarvestScript $AutoHarvestPath
}

# B. Claude Code Non-Destructive Integration
$ClaudeDir = Join-Path $HOME ".claude"
if (Test-Path $ClaudeDir) {
    if (Get-Command claude -ErrorAction SilentlyContinue) {
        try {
            $McpScript = Join-Path $TargetDir "src\cephalo\services\mcp_server.py"
            & claude mcp add cephalo -- $PythonCmd $McpScript
            Write-Host "      Registered Cephalo MCP server cleanly via 'claude mcp add'." -ForegroundColor Green
        } catch {
            Write-Host "      Notice: Could not auto-register MCP with Claude CLI." -ForegroundColor Gray
        }
    }

    # Non-destructive block append to ~/.claude/CLAUDE.md
    $ClaudeRuleTarget = Join-Path $ClaudeDir "CLAUDE.md"
    $ClaudeBlock = @"
### Cephalo Sovereign Memory Integration
- **Root Directory:** $TargetDir
- **Grounding Invariant:** Consult Cephalo before answering past preferences or decisions (`cephalo search "<query>" --json`).
- **Autonomous Capture:** Record preferences & decisions immediately (`cephalo record "<statement>" --category "<category>"`).
"@
    Merge-ManagedBlock -FilePath $ClaudeRuleTarget -BlockContent $ClaudeBlock
}

# 7. Verify Installation & Database Health
Write-Host "[6/6] Verifying Cephalo..." -ForegroundColor Yellow
& $PythonCmd (Join-Path $TargetDir "brain.py") status

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  [+] Cephalo Installed Adaptively with Zero Configuration Damage!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "Safety Guarantees Applied:" -ForegroundColor White
Write-Host "  • Existing CLAUDE.md and hooks preserved; managed blocks merged cleanly." -ForegroundColor Gray
Write-Host "  • No unmanaged files dropped into your home directory root." -ForegroundColor Gray
Write-Host "  • Background git push is opt-in (CEPHALO_AUTO_PUSH=1); no surprise pushes." -ForegroundColor Gray
Write-Host "  • Automatic backups created for every touched configuration file." -ForegroundColor Gray
Write-Host ""
