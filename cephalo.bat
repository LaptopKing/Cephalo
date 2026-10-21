@echo off
setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"

:: 1. Check known local Python 3.12 / 3.11 / 3.10 installs first (bypassing Windows Store 0-byte stub)
for %%V in (Python312 Python311 Python313 Python310) do (
    if exist "%LOCALAPPDATA%\Programs\Python\%%V\python.exe" (
        "%LOCALAPPDATA%\Programs\Python\%%V\python.exe" "%SCRIPT_DIR%brain.py" %*
        goto :eof
    )
)

:: 2. Check Program Files
for %%V in (Python312 Python311 Python313 Python310) do (
    if exist "%ProgramFiles%\Python\%%V\python.exe" (
        "%ProgramFiles%\Python\%%V\python.exe" "%SCRIPT_DIR%brain.py" %*
        goto :eof
    )
)

:: 3. Check py launcher
where py >nul 2>nul
if %errorlevel% equ 0 (
    py "%SCRIPT_DIR%brain.py" %*
    goto :eof
)

:: 4. Fallback to python on PATH
python "%SCRIPT_DIR%brain.py" %*
if %errorlevel% equ 0 goto :eof

echo Error: Python 3.10+ was not found on your system.
echo Please install Python from https://www.python.org/downloads/
exit /b 1
