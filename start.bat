@echo off
chcp 65001 >nul 2>&1
title Video Automator

echo ============================================
echo   Video Automator - 起動中...
echo ============================================
echo.

cd /d "%~dp0"

REM uv がインストールされているか確認
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo [エラー] uv が見つかりません。
    echo https://docs.astral.sh/uv/getting-started/installation/ からインストールしてください。
    echo.
    pause
    exit /b 1
)

REM 仮想環境が存在しない場合は作成・同期
if not exist ".venv" (
    echo [初回セットアップ] 仮想環境を作成しています...
    uv sync
    if %errorlevel% neq 0 (
        echo [エラー] 仮想環境の作成に失敗しました。
        pause
        exit /b 1
    )
    echo.
)

REM アプリケーション起動
echo アプリケーションを起動しています...
uv run python src/main.py

if %errorlevel% neq 0 (
    echo.
    echo [エラー] アプリケーションの起動に失敗しました。
    pause
    exit /b 1
)
