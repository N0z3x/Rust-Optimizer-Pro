@echo off
setlocal
cd /d "%~dp0"

echo === Rust FPS Optimizer Pro: run source as admin ===
echo Project dir: %CD%
echo.

if not exist "%CD%\RustFPSOptimizer_Pro.py" (
    echo ERROR: RustFPSOptimizer_Pro.py not found in this folder.
    echo Extract the ZIP completely and run this BAT from the rust_optimizer folder.
    pause
    exit /b 1
)

if not exist "%CD%\RustFPSOptimizer.py" (
    echo ERROR: backend file RustFPSOptimizer.py not found.
    echo Pro version needs RustFPSOptimizer.py in the same folder.
    echo Extract the ZIP completely; do not copy only RustFPSOptimizer_Pro.py.
    pause
    exit /b 1
)

where py >nul 2>nul
if not errorlevel 1 (
    echo Checking customtkinter and psutil...
    py -3 -c "import customtkinter, psutil" >nul 2>nul
    if errorlevel 1 py -3 -m pip install --upgrade customtkinter psutil
    echo Starting with py launcher...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'py' -ArgumentList '-3 ""%~dp0RustFPSOptimizer_Pro.py""' -Verb RunAs"
    exit /b 0
)

where python >nul 2>nul
if not errorlevel 1 (
    echo Checking customtkinter and psutil...
    python -c "import customtkinter, psutil" >nul 2>nul
    if errorlevel 1 python -m pip install --upgrade customtkinter psutil
    echo Starting with python...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'python' -ArgumentList '""%~dp0RustFPSOptimizer_Pro.py""' -Verb RunAs"
    exit /b 0
)

where python3 >nul 2>nul
if not errorlevel 1 (
    echo Checking customtkinter and psutil...
    python3 -c "import customtkinter, psutil" >nul 2>nul
    if errorlevel 1 python3 -m pip install --upgrade customtkinter psutil
    echo Starting with python3...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'python3' -ArgumentList '""%~dp0RustFPSOptimizer_Pro.py""' -Verb RunAs"
    exit /b 0
)

echo Python not found. Install Python 3.11+ from python.org and tick "Add Python to PATH".
pause
exit /b 1
