@echo off
chcp 65001 >nul
title 在留カードリーダー

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "READER_PYTHON=.venv\Scripts\python.exe"
) else (
    set "READER_PYTHON=python"
)

"%READER_PYTHON%" --version >nul 2>&1
if errorlevel 1 (
    echo Python が見つかりません。
    echo Python 3.11 以上をインストールしてから、もう一度実行してください。
    echo.
    pause
    exit /b 1
)

"%READER_PYTHON%" launch_reader.py
if errorlevel 1 (
    echo.
    echo 起動に失敗しました。上のメッセージを確認してください。
    pause
    exit /b 1
)
