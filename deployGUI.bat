@echo off
setlocal

REM ============================================
REM  CONFIG - edit these if paths/hostnames change
REM ============================================
set PI_USER=tim
set PI_HOST=groundstation
set PI_HOST_FALLBACK=192.168.1.25
set PI_DIR=/home/tim/ground-station-gui
set LOCAL_DIR=C:\Git\Hybrid\Python GUI

REM How long (seconds) to wait for the SSH connection to establish
REM before giving up -- keeps a dead/unreachable host from hanging the
REM script for the OS's much longer default TCP timeout.
set CONNECT_TIMEOUT=4

REM Records what was sent on the last successful deploy, so only new or
REM changed files get sent next time. Run "deployGUI.bat full" (or delete
REM this file) to force a full re-sync, e.g. after wiping the Pi folder.
set MANIFEST=%~dp0.deploy_manifest
set FILE_LIST=%TEMP%\deployGUI_files.txt

REM Use Windows' built-in tar, not any other tar that may be on PATH.
set TAR=%SystemRoot%\System32\tar.exe

if /i "%~1"=="full" (
    echo Forcing full sync.
    if exist "%MANIFEST%" del "%MANIFEST%"
)

echo.
echo ===== Checking for changed files =====
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy_diff.ps1" -LocalDir "%LOCAL_DIR%" -Manifest "%MANIFEST%" -ListOut "%FILE_LIST%"
if errorlevel 1 (
    echo.
    echo Failed to build the list of changed files.
    pause
    exit /b 1
)

REM Try the hostname first (works whether that resolves over Ethernet or
REM WiFi); if it can't be reached, fall back to the known WiFi IP.
set PI_TARGET=%PI_HOST%

REM Nothing to send - just make sure the Pi is reachable for the restart.
for %%F in ("%FILE_LIST%") do if %%~zF==0 goto :no_changes

call :sync
if not errorlevel 1 goto :sync_ok

echo.
echo Could not reach "%PI_HOST%" - retrying via %PI_HOST_FALLBACK% ...
set PI_TARGET=%PI_HOST_FALLBACK%
call :sync

if errorlevel 1 (
    echo.
    echo File transfer FAILED on both "%PI_HOST%" and %PI_HOST_FALLBACK%.
    echo Check the Pi is powered on and reachable on your current network.
    pause
    exit /b 1
)

:sync_ok
move /y "%MANIFEST%.new" "%MANIFEST%" >nul
goto :restart

:no_changes
del "%MANIFEST%.new" 2>nul
ssh -o ConnectTimeout=%CONNECT_TIMEOUT% %PI_USER%@%PI_TARGET% "true" 2>nul
if not errorlevel 1 goto :restart
set PI_TARGET=%PI_HOST_FALLBACK%

:restart
echo.
echo ===== Restarting GUI on Pi (%PI_TARGET%) =====
ssh -o ConnectTimeout=%CONNECT_TIMEOUT% %PI_USER%@%PI_TARGET% "bash %PI_DIR%/restart_gui.sh"

echo.
echo ===== Done =====
exit /b 0

REM --------------------------------------------
REM  Stream the changed files to the Pi as a tar archive over one SSH
REM  connection. Exit code is the remote tar's (or 255 if SSH failed).
REM --------------------------------------------
:sync
echo.
echo ===== Syncing changed files to Pi (%PI_TARGET%) =====
"%TAR%" -cf - -C "%LOCAL_DIR%" -T "%FILE_LIST%" | ssh -o ConnectTimeout=%CONNECT_TIMEOUT% %PI_USER%@%PI_TARGET% "mkdir -p %PI_DIR% && tar -xf - -C %PI_DIR%"
exit /b %errorlevel%
