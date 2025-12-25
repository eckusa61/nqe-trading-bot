# NQE Trading Bot - PC Kurulum Rehberi

## 🚀 Hızlı Kurulum (Windows)

### Gereksinimler
- Python 3.11+
- Git
- TWS veya IB Gateway (IBKR için)

### Adım 1: Repo'yu İndirin
```bash
git clone https://github.com/eckusa61/nqe-trading-bot.git
cd nqe-trading-bot
```

### Adım 2: Sanal Ortam Oluşturun
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# veya
source venv/bin/activate  # Linux/Mac
```

### Adım 3: Bağımlılıkları Yükleyin
```bash
cd backend
pip install -r requirements.txt
```

### Adım 4: Ortam Değişkenlerini Ayarlayın
`.env` dosyasını düzenleyin:
```
# backend/.env dosyasına ekleyin:
OPENAI_API_KEY=sk-proj-...
CLAUDE_API_KEY=sk-ant-...

# Telegram
TELEGRAM_HABER_TOKEN=...
TELEGRAM_HABER_CHAT_ID=...
TELEGRAM_SINYAL_TOKEN=...
TELEGRAM_SINYAL_CHAT_ID=...
TELEGRAM_ANALIZ_TOKEN=...
TELEGRAM_ANALIZ_CHAT_ID=...
TELEGRAM_OPTIMIZASYON_TOKEN=...
TELEGRAM_OPTIMIZASYON_CHAT_ID=...
```

### Adım 5: TWS/IB Gateway Ayarları
1. TWS veya IB Gateway açın
2. Global Configuration → API → Settings
3. ✅ Enable ActiveX and Socket Clients
4. ❌ Read-Only API (işaretsiz olmalı)
5. Socket Port: 7497

### Adım 6: Botu Başlatın
```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### Adım 7: Frontend (Opsiyonel)
```bash
cd ../frontend
npm install
npm start
```

---

## 🔄 Otomatik Güncelleme

Botu GitHub'dan otomatik güncellemek için:

### Windows (Task Scheduler ile)
1. `scripts/auto_update.bat` dosyasını çalıştırın
2. Veya Task Scheduler ile her 5 dakikada çalışacak şekilde ayarlayın

### Manuel Güncelleme
```bash
git pull origin main
pip install -r requirements.txt
```

---

## 📱 Telegram Bildirimleri

Bot çalışırken şu kanallara mesaj gönderir:
- **Haber**: Piyasa haberleri
- **Sinyal**: BUY/SELL sinyalleri  
- **Analiz**: Günlük raporlar
- **Optimizasyon**: Bot durumu, AI kararları

---

## 🛠️ Sorun Giderme

### "Connection refused" hatası
- TWS/IB Gateway açık mı?
- API ayarları doğru mu?
- Port 7497 doğru mu?

### "Module not found" hatası
```bash
pip install -r requirements.txt
```

### Bot yanıt vermiyor
```bash
# Logları kontrol edin
tail -f logs/trading_bot.log
```

---

## 📞 Destek

Sorunlar için GitHub Issues kullanın veya Telegram üzerinden iletişime geçin.
