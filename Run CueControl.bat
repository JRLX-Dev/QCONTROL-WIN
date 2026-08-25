@echo off
setlocal EnableExtensions
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

REM --- Find a real Python (avoid Windows Store stub) ---
set "PYLAUNCH="
where py >nul 2>&1
if not errorlevel 1 set "PYLAUNCH=py -3"

if not defined PYLAUNCH (
    where python >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python was not found.
        echo Install Python 3.10+ from https://www.python.org/downloads/
        echo Check "Add python.exe to PATH" during setup.
        pause
        exit /b 1
    )
    set "PYLAUNCH=python"
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment .venv ...
    %PYLAUNCH% -m venv .venv
    if errorlevel 1 (
        echo ERROR: Could not create .venv.
        echo Use python.org Python, not the Microsoft Store shortcut.
        pause
        exit /b 1
    )
)

echo Installing / updating packages (first run can take a few minutes^)...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if exist "requirements.txt" (
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
) else (
    ".venv\Scripts\python.exe" -m pip install "PySide6>=6.6" numpy soundfile python-osc
)
if errorlevel 1 (
    echo ERROR: pip install failed. Check internet / firewall and try again.
    pause
    exit /b 1
)

echo.
echo Starting CueControl...
echo.
if exist "CueControl_launch.py" (
    ".venv\Scripts\python.exe" "CueControl_launch.py"
) else (
    ".venv\Scripts\python.exe" "Main.py"
)
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
    echo.
    echo CueControl exited with code %ERR%.
    pause
)
exit /b %ERR%
