@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title CueControl — Build portable kit
echo.
echo  CueControl portable kit builder
echo  No admin required. Output: dist\CueControl-Portable\
echo.

if not exist "Main.py" (
    echo ERROR: Main.py not found. Run this from the CueControl source folder.
    pause
    exit /b 1
)
if not exist "CueControl_launch.py" (
    echo ERROR: CueControl_launch.py not found.
    pause
    exit /b 1
)
if not exist "CueControl.spec" (
    echo ERROR: CueControl.spec not found.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv is missing.
    echo Double-click "Run CueControl.bat" once first so packages install, then retry.
    pause
    exit /b 1
)

echo Installing PyInstaller into .venv ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install "pyinstaller>=6.0"
if errorlevel 1 (
    echo ERROR: Could not install PyInstaller.
    pause
    exit /b 1
)

echo.
echo Building CueControl.exe (several minutes, do not close this window^)...
echo.
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean CueControl.spec
if errorlevel 1 (
    echo.
    echo BUILD FAILED. Scroll up for the PyInstaller error.
    pause
    exit /b 1
)

echo.
echo Assembling USB folder ...
".venv\Scripts\python.exe" assemble_kit.py
if errorlevel 1 (
    echo ERROR: assemble_kit.py failed.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  DONE
echo.
echo  Copy this folder onto your flash drive or SSD:
echo    %cd%\dist\CueControl-Portable
echo.
echo  On the drive, double-click CueControl.exe
echo  Put media in Media\   Save shows in Shows\
echo ============================================================
echo.
if exist "dist\CueControl-Portable" explorer "dist\CueControl-Portable"
pause
exit /b 0
