@echo off
chcp 65001 >nul
title Vegetable Project - Dev Mode
color 0A

echo ============================================
echo    Vegetable Project - Development Mode
echo ============================================
echo.

REM ไปที่โฟลเดอร์โปรเจค
cd /d "D:\pang\project\backend_fastapi"

REM เปิดใช้งาน virtual environment
call .venv\Scripts\activate.bat

echo [1/3] กำลังรัน Backend Server...
start "Backend Server" cmd /k "cd /d D:\pang\project\backend_fastapi && call .venv\Scripts\activate.bat && uvicorn main:app --host 0.0.0.0 --port 8888 --reload"

echo [2/3] กำลังรัน ngrok...
timeout /t 4 /nobreak >nul

REM หยุด ngrok เก่าถ้ามี
taskkill /F /IM ngrok.exe >nul 2>&1

REM รัน ngrok native exe (background, minimized)
start /min "" "%LOCALAPPDATA%\ngrok\ngrok.exe" http 8888 --domain=unvengeful-leeanne-interpressure.ngrok-free.dev

echo [3/3] รอ ngrok เริ่มต้น...
timeout /t 6 /nobreak >nul

echo ตั้งค่า Telegram Webhook...
python setup_ngrok_telegram.py

echo.
echo ============================================
echo  ระบบพร้อมใช้งาน!
echo.
echo  Backend:        http://localhost:8888
echo  ngrok:          https://unvengeful-leeanne-interpressure.ngrok-free.dev
echo  ngrok Dashboard: http://localhost:4040
echo  API Docs:       http://localhost:8888/docs
echo ============================================
echo.
echo กด Enter เพื่อปิดหน้าต่างนี้...
pause >nul
