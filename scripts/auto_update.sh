#!/bin/bash
# NQE Trading Bot - Linux/Mac Auto Update Script

echo "========================================"
echo "NQE Trading Bot - Auto Update"
echo "========================================"

# Proje dizinine git
cd ~/nqe-trading-bot || exit 1

# Git pull yap
echo "[1/4] GitHub'dan guncellemeler cekiliyor..."
git pull origin main

if [ $? -ne 0 ]; then
    echo "[HATA] Git pull basarisiz!"
    exit 1
fi

# Sanal ortami aktif et
echo "[2/4] Sanal ortam aktif ediliyor..."
source venv/bin/activate

# Bagimliliklari guncelle
echo "[3/4] Bagimliliklar kontrol ediliyor..."
cd backend
pip install -r requirements.txt --quiet

# Botu yeniden baslat
echo "[4/4] Bot yeniden baslatiliyor..."
pkill -f "uvicorn server:app" 2>/dev/null
nohup python -m uvicorn server:app --host 0.0.0.0 --port 8001 &

echo ""
echo "========================================"
echo "Guncelleme tamamlandi!"
echo "========================================"
