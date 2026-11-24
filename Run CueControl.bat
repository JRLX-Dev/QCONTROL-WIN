@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title CueControl Windows
set "LOG=%~dp0launch_log.txt"
echo ===== %DATE% %TIME% ===== > "%LOG%"
echo Folder: %cd%>> "%LOG%"

echo.
echo  CueControl Windows
echo  Folder: %cd%
echo.

if not exist "Main.py" (
    echo ERROR: Main.py not found in this folder.
    echo Extract the full GitHub ZIP so Main.py, requirements.txt, and this .bat sit together.
    echo ERROR: Main.py not found>> "%LOG%"
    pause
    exit /b 1
)

if exist "Install Python.bat" (
    echo Preparing Python in runtime\ ...
    echo Preparing Python...>> "%LOG%"
    call "%~dp0Install Python.bat" >> "%LOG%" 2>&1
    if errorlevel 1 (
        echo.
        echo Python setup did not finish. Last lines from launch_log.txt:
        echo ----------------------------------------
        powershell -NoProfile -Command "Get-Content -LiteralPath '%LOG%' -Tail 25"
        echo ----------------------------------------
        pause
        exit /b 1
    )
)

set "APP_PY=%~dp0runtime\python\python.exe"
if not exist "%APP_PY%" (
    echo ERROR: Bundled Python missing at:
    echo   %APP_PY%
    echo Run Install Python.bat on a PC with internet, then try again.
    echo ERROR: python.exe missing>> "%LOG%"
    pause
    exit /b 1
)

echo Using: %APP_PY%
echo Using: %APP_PY%>> "%LOG%"

REM Update + packages. Failure here must not block the show.
if exist "update_cuecontrol.py" (
    echo Checking updates and packages...
    echo Running update_cuecontrol.py>> "%LOG%"
    "%APP_PY%" "update_cuecontrol.py" >> "%LOG%" 2>&1
    if errorlevel 1 (
        echo.
        echo Update or package step reported a problem. Starting the local copy anyway.
        echo See launch_log.txt next to this file if the app does not open.
        echo WARN: update_cuecontrol.py returned non-zero>> "%LOG%"
    )
)

echo.
echo Starting CueControl...
echo Starting Main.py>> "%LOG%"
echo.
"%APP_PY%" "Main.py"
set "ERR=%ERRORLEVEL%"
echo Main.py exit %ERR%>> "%LOG%"
if not "%ERR%"=="0" (
    echo.
    echo CueControl exited with code %ERR%.
    echo The console text above and launch_log.txt are what to send.
    pause
)
exit /b %ERR%
