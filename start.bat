@echo off
title Video Automator

echo ============================================
echo   Video Automator - Starting...
echo ============================================
echo.

cd /d "%~dp0"

where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] uv is not installed.
    echo Please install from: https://docs.astral.sh/uv/getting-started/installation/
    echo.
    pause
    exit /b 1
)

if not exist ".venv" (
    echo [SETUP] Creating virtual environment...
    uv sync
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo.
)

echo Starting application...
uv run python src/main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application failed to start.
    pause
    exit /b 1
)
