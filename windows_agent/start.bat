@echo off
echo ============================================
echo  Windows Remote Network Monitor - Starting
echo ============================================
echo.

:: Check for admin privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script must be run as Administrator!
    echo Right-click start.bat and select "Run as administrator"
    pause
    exit /b 1
)

echo [OK] Running as Administrator
echo.

:: Start the agent
cd /d "%~dp0"
python agent.py

:: If it exits, pause so we can see any errors
echo.
echo Agent stopped. Press any key to exit...
pause
