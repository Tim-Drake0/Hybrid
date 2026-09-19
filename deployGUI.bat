
deploy.bat
@echo off
setlocal
 
REM ============================================
REM  CONFIG - edit these if paths/hostnames change
REM ============================================
set PI_USER=tim
set PI_HOST=groundstation
set PI_DIR=/home/tim/ground-station-gui
set LOCAL_DIR=C:\Git\Hybrid\Python GUI
 
echo.
echo ===== Syncing code to Pi =====
scp -r "%LOCAL_DIR%\*" %PI_USER%@%PI_HOST%:%PI_DIR%/
 
if errorlevel 1 (
    echo.
    echo File transfer FAILED. Check your Ethernet connection / Pi hostname.
    pause
    exit /b 1
)
 
echo.
echo ===== Restarting GUI on Pi =====
ssh %PI_USER%@%PI_HOST% "bash %PI_DIR%/restart_gui.sh"
 
echo.
echo ===== Done =====
 