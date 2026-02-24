@echo off
echo ============================================
echo  Windows Remote Network Monitor - Installer
echo ============================================
echo.

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Check for Npcap
if exist "C:\Windows\System32\Npcap" (
    echo [OK] Npcap detected.
) else if exist "C:\Program Files\Npcap" (
    echo [OK] Npcap detected.
) else (
    echo WARNING: Npcap not detected.
    echo Download from: https://npcap.com
    echo During install, check "WinPcap API-compatible mode"
    echo.
    echo Press any key to continue anyway, or Ctrl+C to cancel...
    pause >nul
)

:: Install Python dependencies
echo.
echo Installing Python dependencies...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Installation complete!
echo.
echo  Next steps:
echo  1. Edit config.py with your settings
echo  2. Run start.bat as Administrator
echo ============================================
pause
