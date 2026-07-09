@echo off
setlocal
cd /d "%~dp0"

echo === Rust FPS Optimizer Pro: build EXE ===
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

set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3"

if not defined PYTHON_CMD (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    where python3 >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python3"
)

if not defined PYTHON_CMD (
    echo Python not found. Install Python 3.11+ from python.org and tick "Add Python to PATH".
    pause
    exit /b 1
)

echo Using Python command: %PYTHON_CMD%
%PYTHON_CMD% --version
if errorlevel 1 (
    echo Python command exists but failed to run.
    pause
    exit /b 1
)

echo.
echo Installing dependencies...
%PYTHON_CMD% -m pip install --upgrade pip
if errorlevel 1 goto :fail
%PYTHON_CMD% -m pip install --upgrade customtkinter psutil pyinstaller
if errorlevel 1 goto :fail

set "ICON_ARGS="
if exist "%CD%\app.ico" set "ICON_ARGS=--icon app.ico --add-data app.ico;."

echo.
echo Building Pro EXE...
%PYTHON_CMD% -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin %ICON_ARGS% --collect-data customtkinter --hidden-import RustFPSOptimizer --hidden-import psutil --name RustFPSOptimizerPro RustFPSOptimizer_Pro.py
if errorlevel 1 goto :fail

echo.
echo Done: %CD%\dist\RustFPSOptimizerPro.exe
echo Tip: run it as administrator for all tweaks.
pause
exit /b 0

:fail
echo.
echo Build failed.
pause
exit /b 1
