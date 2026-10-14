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

REM How long (seconds) to wait for the SSH/SCP connection to establish
REM before giving up -- keeps a dead/unreachable host from hanging the
REM script for the OS's much longer default TCP timeout.
set CONNECT_TIMEOUT=4

REM Try the hostname first (works whether that resolves over Ethernet or
REM WiFi); if it can't be reached, fall back to the known WiFi IP.
set PI_TARGET=%PI_HOST%

echo.
echo ===== Syncing code to Pi (%PI_TARGET%) =====
scp -o ConnectTimeout=%CONNECT_TIMEOUT% -r "%LOCAL_DIR%\*" %PI_USER%@%PI_TARGET%:%PI_DIR%/

if not errorlevel 1 goto :sync_ok

echo.
echo Could not reach "%PI_HOST%" - retrying via %PI_HOST_FALLBACK% ...
set PI_TARGET=%PI_HOST_FALLBACK%

echo.
echo ===== Syncing code to Pi (%PI_TARGET%) =====
scp -o ConnectTimeout=%CONNECT_TIMEOUT% -r "%LOCAL_DIR%\*" %PI_USER%@%PI_TARGET%:%PI_DIR%/

if errorlevel 1 (
    echo.   
    echo File transfer FAILED on both "%PI_HOST%" and %PI_HOST_FALLBACK%.
    echo Check the Pi is powered on and reachable on your current network.
    pause
    exit /b 1
)

:sync_ok
echo.
echo ===== Restarting GUI on Pi (%PI_TARGET%) =====
ssh -o ConnectTimeout=%CONNECT_TIMEOUT% %PI_USER%@%PI_TARGET% "bash %PI_DIR%/restart_gui.sh"

echo.
echo ===== Done =====
