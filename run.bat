@echo off
setlocal
title Web2Apk v1.0 — By Mohsin Khawaja

echo =================================================================
echo   Web2Apk v1.0 — By Mohsin Khawaja
echo   "Get rid of paid web to apk tools"
echo =================================================================
echo.

:: 1. Check for Python installation
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found in your system PATH!
    echo Please download and install Python 3.10+ from:
    echo   https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: 2. Auto-verify and install Python dependencies if needed
python -c "import flask, PIL" >nul 2>&1
if errorlevel 1 (
    echo [*] Checking and installing required Python packages...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies from requirements.txt.
        echo Please ensure you have an active internet connection.
        pause
        exit /b 1
    )
    echo [*] Dependencies installed successfully.
    echo.
)

:: 3. Launch the Web Console
echo [*] Launching Web2Apk Web Console...
python main.py
if errorlevel 1 (
    echo.
    echo [ERROR] Web2Apk exited with an error code.
    pause
)
