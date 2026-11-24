@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

REM Official python.org 3.12.10 — 64-bit, no admin.
REM Always lives in runtime\python\ ON THIS FOLDER so a USB/SSD can move PCs.
REM Host Python is ignored on purpose (it would not travel with the drive).
set "PY_VER=3.12.10"
set "PY_DIR=%~dp0runtime\python"
set "CACHE=%~dp0runtime\cache"

if /I "%PROCESSOR_ARCHITECTURE%"=="ARM64" (
    set "PY_ARCH=arm64"
) else (
    set "PY_ARCH=amd64"
)
set "INSTALLER_EXE=python-%PY_VER%-amd64.exe"
if /I "%PY_ARCH%"=="arm64" set "INSTALLER_EXE=python-%PY_VER%-arm64.exe"
set "INSTALLER_URL=https://www.python.org/ftp/python/%PY_VER%/%INSTALLER_EXE%"
set "EMBED_ZIP=python-%PY_VER%-embed-%PY_ARCH%.zip"
set "EMBED_URL=https://www.python.org/ftp/python/%PY_VER%/%EMBED_ZIP%"

echo.
echo  CueControl — bundled Python
echo  Folder: %cd%
echo.

echo %cd% | find " " >nul
if not errorlevel 1 (
    echo WARNING: this folder path contains a space.
    echo The quiet Python installer often fails on spaces.
    echo Prefer a path like D:\CueControl\
    echo.
)

call :check_exe "%PY_DIR%\python.exe"
if not errorlevel 1 (
    echo Using bundled runtime\python\  ^(travels with this folder^)
    "%PY_DIR%\python.exe" -m pip --version >nul 2>&1
    if errorlevel 1 (
        echo Bundled Python has no pip. Bootstrapping...
        goto NEED_PIP
    )
    exit /b 0
)

echo No bundled Python in runtime\ yet.
echo Downloading the official python.org installer into this folder.
echo No admin. Nothing in Program Files. Drive letter can change later.
echo   %INSTALLER_URL%
echo.

mkdir "%CACHE%" 2>nul
set "INSTALLER=%CACHE%\%INSTALLER_EXE%"
if exist "%INSTALLER%" call :reject_empty "%INSTALLER%"
if not exist "%INSTALLER%" (
    call :download "%INSTALLER_URL%" "%INSTALLER%"
    if errorlevel 1 (
        echo Official installer download failed. Trying embeddable package...
        goto EMBED
    )
)

echo Installing Python %PY_VER% into:
echo   %PY_DIR%
echo This can take a minute. SmartScreen may blink — allow it if asked.
echo.
"%INSTALLER%" /quiet InstallAllUsers=0 PrependPath=0 Include_launcher=0 Include_test=0 Include_doc=0 Include_dev=0 Shortcuts=0 AssociateFiles=0 CompileAll=0 TargetDir="%PY_DIR%"
if errorlevel 1 (
    echo Quiet installer did not finish. Trying embeddable package...
    goto EMBED
)
call :check_exe "%PY_DIR%\python.exe"
if errorlevel 1 (
    echo Installer finished but python.exe is missing. Trying embeddable package...
    goto EMBED
)
"%PY_DIR%\python.exe" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo Official Python has no pip. Bootstrapping...
    goto NEED_PIP
)
echo Bundled Python is ready.
exit /b 0

:EMBED
echo.
echo Downloading python.org embeddable package...
set "ZIP=%CACHE%\%EMBED_ZIP%"
if exist "%ZIP%" call :reject_empty "%ZIP%"
if not exist "%ZIP%" (
    call :download "%EMBED_URL%" "%ZIP%"
    if errorlevel 1 (
        echo.
        echo ERROR: Could not download Python into this folder.
        echo First run needs internet to python.org.
        echo Format the drive NTFS if the installer failed on a flash drive.
        exit /b 1
    )
)
mkdir "%PY_DIR%" 2>nul
tar.exe -xf "%ZIP%" -C "%PY_DIR%"
if errorlevel 1 (
    echo ERROR: Could not unpack the embeddable zip ^(tar.exe missing, or the drive is FAT32^).
    echo Format the USB/SSD as NTFS and try again.
    exit /b 1
)

:NEED_PIP
mkdir "%CACHE%" 2>nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Get-ChildItem -LiteralPath '%PY_DIR%' -Filter '*.pth' | Select-Object -First 1; if (-not $p) { exit 0 }; $t = Get-Content -LiteralPath $p.FullName -Raw; $t = $t -replace '#import site','import site'; if ($t -notmatch 'site-packages') { $t = \"Lib\\site-packages`r`n\" + $t }; Set-Content -LiteralPath $p.FullName -Value $t -NoNewline"
echo Getting pip...
set "GETPIP=%CACHE%\get-pip.py"
if exist "%GETPIP%" call :reject_empty "%GETPIP%"
call :download "https://bootstrap.pypa.io/get-pip.py" "%GETPIP%"
if errorlevel 1 (
    echo ERROR: Could not download get-pip.py. First run needs internet to bootstrap.pypa.io.
    exit /b 1
)
"%PY_DIR%\python.exe" "%GETPIP%" --no-warn-script-location
if errorlevel 1 (
    echo ERROR: get-pip failed. First run needs internet to bootstrap.pypa.io.
    exit /b 1
)
call :check_exe "%PY_DIR%\python.exe"
if errorlevel 1 exit /b 1
"%PY_DIR%\python.exe" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: pip still missing after bootstrap.
    exit /b 1
)
echo Bundled Python is ready.
exit /b 0

:download
set "URL=%~1"
set "OUT=%~2"
if exist "%OUT%" exit /b 0
echo Fetching:
echo   %URL%
where curl.exe >nul 2>&1
if not errorlevel 1 (
    curl.exe --fail --location --retry 3 --retry-delay 2 --output "%OUT%" "%URL%"
    if not errorlevel 1 if exist "%OUT%" exit /b 0
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "Invoke-WebRequest -Uri '%URL%' -OutFile '%OUT%' -UseBasicParsing"
if not exist "%OUT%" exit /b 1
call :reject_empty "%OUT%"
if not exist "%OUT%" exit /b 1
exit /b 0

:reject_empty
set "FILE=%~1"
if not exist "%FILE%" exit /b 0
for %%A in ("%FILE%") do if %%~zA LSS 1024 (
    echo Removing empty or truncated download: %FILE%
    del /f /q "%FILE%" 2>nul
)
exit /b 0

:check_exe
set "EXE=%~1"
if not exist "%EXE%" exit /b 1
echo %EXE% | find /I "WindowsApps" >nul && exit /b 1
"%EXE%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>nul
exit /b %errorlevel%
