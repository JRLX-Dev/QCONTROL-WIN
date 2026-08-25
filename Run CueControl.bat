@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

title CueControl Windows
echo.
echo  CueControl Windows
echo  Folder: %cd%
echo.

if not exist "Main.py" (
    echo ERROR: Main.py not found in this folder.
    echo Extract the full GitHub ZIP so Main.py, requirements.txt, and this .bat sit together.
    pause
    exit /b 1
)

REM --- Get a real Python 3.10+ (download official installer into runtime\ if needed) ---
if exist "Install Python.bat" (
    call "%~dp0Install Python.bat"
    if errorlevel 1 (
        pause
        exit /b 1
    )
)

set "BOOT_PY="
if exist "runtime\python.exe.path" (
    set /p BOOT_PY=<"runtime\python.exe.path"
)

set "APP_PY="
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>nul
    if not errorlevel 1 set "APP_PY=%cd%\.venv\Scripts\python.exe"
)

if not defined APP_PY (
    if not defined BOOT_PY (
        echo ERROR: Python was not found and Install Python.bat is missing.
        echo Put Install Python.bat next to this file, or install Python 3.10+ from python.org.
        pause
        exit /b 1
    )
    echo Creating virtual environment .venv ...
    "%BOOT_PY%" -m venv .venv
    if exist ".venv\Scripts\python.exe" (
        set "APP_PY=%cd%\.venv\Scripts\python.exe"
    ) else (
        echo venv not available on this Python — using the bundled copy directly.
        set "APP_PY=%BOOT_PY%"
    )
)

echo Installing / updating packages (first run can take a few minutes^)...
"%APP_PY%" -m pip install --upgrade pip
if exist "requirements.txt" (
    "%APP_PY%" -m pip install -r requirements.txt
) else (
    "%APP_PY%" -m pip install "PySide6>=6.6" numpy soundfile python-osc
)
if errorlevel 1 (
    echo ERROR: pip install failed. Check internet / firewall and try again.
    pause
    exit /b 1
)

echo.
echo Starting CueControl...
echo.
"%APP_PY%" "Main.py"
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
    echo.
    echo CueControl exited with code %ERR%.
    pause
)
exit /b %ERR%
