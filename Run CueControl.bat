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

REM Python lives in runtime\ on this drive — not the host PC, not .venv.
if exist "Install Python.bat" (
    call "%~dp0Install Python.bat"
    if errorlevel 1 (
        pause
        exit /b 1
    )
)

set "APP_PY=%~dp0runtime\python\python.exe"
if not exist "%APP_PY%" (
    echo ERROR: Bundled Python missing at:
    echo   %APP_PY%
    echo Run Install Python.bat on a PC with internet, then copy this whole folder.
    pause
    exit /b 1
)

echo Installing / updating packages (first run can take a few minutes^)...
"%APP_PY%" -m pip install --upgrade pip
if exist "requirements.txt" (
    "%APP_PY%" -m pip install -r requirements.txt
) else (
    "%APP_PY%" -m pip install "PySide6>=6.6" numpy soundfile python-osc
)
if errorlevel 1 (
    echo ERROR: pip install failed. First run needs internet.
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
