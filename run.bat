@echo off
title Ren'Py Save Graph
echo ===================================================
echo   Ren'Py Save Graph — Interactive Flowchart App
echo ===================================================
echo.

where py >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ from https://www.python.org/
    echo Make sure to check "Add python.exe to PATH" during installation.
    echo.
    pause
    exit /b 1
)

where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js / npm is not installed or not in PATH!
    echo Please install Node.js 18+ from https://nodejs.org/
    echo.
    pause
    exit /b 1
)

echo Installing / Updating renpy-save-graph...
py -m pip install --quiet --upgrade .

echo Installing / building the web UI...
call npm install --silent
call npm run build --silent

echo.
echo Starting web server on http://localhost:5555/
echo Press Ctrl+C in this window to stop.
echo.
py -m renpy_save_graph.server
pause
