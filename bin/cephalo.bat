@echo off
setlocal enabledelayedexpansion
set "SECOND_BRAIN_DIR=%~dp0.."

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
