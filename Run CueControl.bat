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

if exist "update_cuecontrol.py" (
    "%APP_PY%" "update_cuecontrol.py"
    if errorlevel 1 (
        echo ERROR: Could not prepare CueControl.
        pause
        exit /b 1
    )
) else (
    echo Installing / updating packages...
    "%APP_PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: pip install failed. First run needs internet.
        pause
        exit /b 1
    )
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
