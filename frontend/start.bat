@echo off
chcp 65001 >nul
title SpendWise AI
cd /d "%~dp0..\backend"

if not exist venv (
  echo [1/2] Създавам виртуална среда и инсталирам библиотеките...
  python -m venv venv
  venv\Scripts\python.exe -m pip install -q fastapi uvicorn python-dotenv google-genai pillow python-multipart
)
if not exist .env (
  echo ВНИМАНИЕ: липсва backend\.env с GEMINI_API_KEY - AI функциите няма да работят.
)

echo [2/2] Стартирам сървъра на http://127.0.0.1:8000 ...
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep 3; Start-Process '%~dp0index.html'"
venv\Scripts\python.exe -m uvicorn main:app --reload
