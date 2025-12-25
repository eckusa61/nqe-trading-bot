@echo off
REM NQE Trading Bot - Windows Starter
REM Bu dosyayi cift tiklayarak botu baslatin

title NQE Trading Bot

echo ========================================
echo    NQE TRADING BOT - BASLATILIYOR
echo ========================================
echo.

REM Proje dizinine git
cd /d "%~dp0"
cd ..

REM Sanal ortami kontrol et
if not exist "venv\Scripts\activate.bat" (
    echo [!] Sanal ortam bulunamadi. Olusturuluyor...
    python -m venv venv
    call venv\Scripts\activate
    cd backend
    pip install -r requirements.txt
    cd ..
) else (
    call venv\Scripts\activate
)

REM Backend'i baslat
echo [*] Backend baslatiliyor...
cd backend
start "NQE Backend" python -m uvicorn server:app --host 0.0.0.0 --port 8001 --reload

REM 5 saniye bekle
timeout /t 5 /nobreak > nul

REM Frontend'i baslat (opsiyonel)
echo [*] Frontend baslatiliyor...
cd ..\frontend
if exist "node_modules" (
    start "NQE Frontend" npm start
) else (
    echo [!] Frontend node_modules bulunamadi. Yukleniyor...
    npm install
    start "NQE Frontend" npm start
)

echo.
echo ========================================
echo    BOT CALISIYOR!
echo    Backend: http://localhost:8001
echo    Frontend: http://localhost:3000
echo ========================================
echo.
echo Bu pencereyi kapatmayin.
pause
