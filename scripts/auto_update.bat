@echo off
REM NQE Trading Bot - Windows Auto Update Script
REM Bu script'i Task Scheduler ile çalıştırın

echo ========================================
echo NQE Trading Bot - Auto Update
echo ========================================
echo.

REM Proje dizinine git
cd /d "C:\nqe-trading-bot"

REM Git pull yap
echo [1/4] GitHub'dan guncellemeler cekiliyor...
git pull origin main

REM Hata kontrolu
if %ERRORLEVEL% NEQ 0 (
    echo [HATA] Git pull basarisiz!
    exit /b 1
)

REM Sanal ortami aktif et
echo [2/4] Sanal ortam aktif ediliyor...
call venv\Scripts\activate

REM Bagimliliklari guncelle
echo [3/4] Bagimliliklar kontrol ediliyor...
cd backend
pip install -r requirements.txt --quiet

REM Botu yeniden baslat
echo [4/4] Bot yeniden baslatiliyor...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq NQE*" 2>nul
start "NQE Trading Bot" python -m uvicorn server:app --host 0.0.0.0 --port 8001

echo.
echo ========================================
echo Guncelleme tamamlandi!
echo ========================================
