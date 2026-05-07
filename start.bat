@echo off
setlocal enabledelayedexpansion

title MarketRadar Launcher

echo ========================================
echo   MarketRadar Trading System
echo ========================================
echo.

REM Check if in project root
if not exist "m7_scheduler\cli.py" (
    echo [ERROR] Please run this script from project root directory
    pause
    exit /b 1
)

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.9+
    pause
    exit /b 1
)

echo [1/3] Checking scheduler status...
python -m m7_scheduler.cli status >nul 2>&1
if errorlevel 1 (
    echo       Scheduler is not running
) else (
    echo       Scheduler is already running
    echo.
    set /p restart="Restart scheduler? (Y/N): "
    if /i "!restart!"=="N" goto :skip_start
    if /i "!restart!"=="Y" (
        echo [2/3] Stopping old scheduler...
        python -m m7_scheduler.cli stop
        timeout /t 2 >nul
    )
)

echo [2/3] Starting scheduler...
python -m m7_scheduler.cli start --background
if errorlevel 1 (
    echo [ERROR] Failed to start scheduler
    pause
    exit /b 1
)

:skip_start
echo [3/3] Verifying status...
timeout /t 3 >nul
python -m m7_scheduler.cli status 2>nul
if errorlevel 1 (
    echo [WARNING] Status check failed, but scheduler may be running
    echo           Check log: data\logs\scheduler.log
)

echo.
echo ========================================
echo   Startup Complete!
echo ========================================
echo.
echo Scheduler log: data\logs\scheduler.log
echo Check status:  python -m m7_scheduler.cli status
echo Stop system:   python -m m7_scheduler.cli stop
echo Web panel:     python -m pipeline.dashboard
echo.
echo Press any key to open menu...
pause >nul

:menu
cls
echo ========================================
echo   MarketRadar Menu
echo ========================================
echo.
echo [1] Check scheduler status
echo [2] View real-time log
echo [3] Start Web Dashboard
echo [4] Manual M12 scan
echo [5] Manual signal processing
echo [6] Stop scheduler
echo [0] Exit
echo.
set /p choice="Select function (0-6): "

if "%choice%"=="1" goto :status
if "%choice%"=="2" goto :logs
if "%choice%"=="3" goto :dashboard
if "%choice%"=="4" goto :m12_scan
if "%choice%"=="5" goto :signal
if "%choice%"=="6" goto :stop
if "%choice%"=="0" exit /b 0
echo Invalid choice, please retry
timeout /t 2 >nul
goto :menu

:status
cls
echo ======== Scheduler Status ========
python -m m7_scheduler.cli status
echo.
pause
goto :menu

:logs
cls
echo ======== Real-time Log (Ctrl+C to exit) ========
powershell -Command "Get-Content data\logs\scheduler.log -Wait -Tail 50"
goto :menu

:dashboard
cls
echo ======== Starting Web Dashboard V2 ========
echo Browser will open automatically at: http://localhost:8501
echo Press Ctrl+C to stop
streamlit run dashboard_v2\Home.py
goto :menu

:m12_scan
cls
echo ======== Manual M12 Scan ========
echo [1] A-Share scan
echo [2] HK scan
echo [3] US scan
echo [0] Back
set /p scan_choice="Select: "
if "%scan_choice%"=="1" python -m m7_scheduler.cli run m12_a_share_scan
if "%scan_choice%"=="2" python -m m7_scheduler.cli run m12_hk_scan
if "%scan_choice%"=="3" python -m m7_scheduler.cli run m12_us_scan
if "%scan_choice%"=="0" goto :menu
pause
goto :menu

:signal
cls
echo ======== Manual Signal Processing ========
python -m m7_scheduler.cli run signal_pipeline
pause
goto :menu

:stop
cls
echo ======== Stopping Scheduler ========
python -m m7_scheduler.cli stop
echo Scheduler stopped
pause
goto :menu
