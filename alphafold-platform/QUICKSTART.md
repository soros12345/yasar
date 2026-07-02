# AlphaFold Platform - Hızlı Başlangıç Rehberi

## 📋 Gereksinimler

- Python 3.11+
- pip
- (İsteğe bağlı) Docker & Docker Compose

## 🚀 Hızlı Başlama (5 dakika)

### 1️⃣ Repository'yi klonla

```bash
git clone https://github.com/soros12345/yasar.git
cd yasar/alphafold-platform
```

### 2️⃣ Virtual Environment oluştur

```bash
# Linux / macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3️⃣ Bağımlılıkları yükle

```bash
pip install -r requirements.txt
```

### 4️⃣ Uygulamayı başlat

**Seçenek A: Web UI (Tarayıcıda Çalıştır) 🎨**
```bash
python app.py ui
```
- Tarayıcı otomatik açılacak: http://localhost:8501
- 6 sekme ile protein analizi yapabilirsiniz

**Seçenek B: REST API (Programcılar için) 📡**
```bash
python app.py api
```
- API Docs: http://localhost:8000/docs
- Swagger UI ile interaktif API testi

**Seçenek C: Komut Satırı (CLI) 💻**
```bash
python app.py cli list-providers
python app.py cli search --query "insulin"
python app.py cli analyze-quality --structure-id "AF-P12345-F1"
```

---

## 🐳 Docker ile (1 komut)

```bash
docker-compose up -d
```

**Erişim:**
- 🎨 Web UI: http://localhost:8501
- 📡 API: http://localhost:8000
- 📚 API Docs: http://localhost:8000/docs

---

## 🎯 Temel Kullanım

### 🎨 Web UI'da

1. **Ana Sayfada** → Provider Seç (varsayılan: alphafold_db)
2. **Sekmelerde Seç:**
   - 🏆 **Kalite**: Yapı kalitesini pLDDT skorları ile analiz et
   - 📖 **Süperpozisyon**: İki yapıyı karşılaştır (RMSD/TM-score)
   - 🧲 **Cepler**: Potansiyel ilaç bağlanma alanlarını tespit et
   - 🧬 **Varyantlar**: Aminoasit mutasyonlarının etkisini analiz et
   - 🔗 **Korunum**: Evolutif korunum skorlarını hesapla
   - 📋 **Metaveri**: Yapı detaylarını ve istatistikleri görüntüle

### 📡 API ile

```python
import requests
import json

# Yapı indirme
response = requests.post(
    "http://localhost:8000/api/predictions/fetch",
    json={
        "provider": "alphafold_db",
        "structure_id": "AF-P12345-F1"
    }
)
print(json.dumps(response.json(), indent=2))

# Kalite analizi
response = requests.post(
    "http://localhost:8000/api/analysis/quality",
    json={
        "provider": "alphafold_db",
        "structure_id": "AF-P12345-F1"
    }
)
print(f"Kalite: {response.json()['result']['quality']}")
print(f"Avg pLDDT: {response.json()['result']['avg_plddt']:.1f}")
```

### 💻 CLI ile

```bash
# Protein ara
python app.py cli search --query "spike protein" --limit 10

# Yapı kalitesini analiz et
python app.py cli analyze-quality --structure-id "AF-P12345-F1"

# Korunum analizi
python app.py cli analyze-conservation --structure-id "AF-P12345-F1"
```

---

## 🧪 Testler

```bash
# Tüm testleri çalıştır
pytest tests/ -v

# Coverage raporu
pytest tests/ --cov=. --cov-report=html
open htmlcov/index.html  # Raporu aç

# Belirli testleri çalıştır
pytest tests/test_quality.py -v
```

---

## 📚 Örnek Workflow

### Senaryo: SARS-CoV-2 Spike Proteinini Analiz Et

```bash
# 1. Protein ara
python app.py cli search --query "SARS-CoV-2 spike" --limit 5
# Çıkı: AF-P0DTC2-F1, AF-P0DTC2-F2, ...

# 2. Yapıyı indir ve kalite kontrol et
python app.py cli analyze-quality --structure-id "AF-P0DTC2-F1"
# Sonuç:
#   - Ortalama pLDDT: 94.2
#   - Kalite: EXCELLENT
#   - pLDDT Dağılımı: Çok Yüksek (90-100): 1200, ...

# 3. Korunum analizi
python app.py cli analyze-conservation --structure-id "AF-P0DTC2-F1"
# En korunan pozisyonlar gösterilecek
```

---

## ⚙️ Yapılandırma

`.env` dosyasını düzenle:

```env
# Debug
DEBUG=false

# Server
API_PORT=8000
UI_PORT=8501

# Cache
CACHE_TTL=86400  # 24 saat

# Analiz parametreleri
RMSD_THRESHOLD=2.0
PLDDT_THRESHOLD=70.0
```

---

## 🆘 Sorun Giderme

### "ModuleNotFoundError: No module named 'core'"
```bash
# Python path'i ayarla
export PYTHONPATH=$PYTHONPATH:$(pwd)
python app.py api
```

### "Connection refused" (API)
```bash
# API'nin çalıştığını kontrol et
python app.py api  # Ayrı terminal'de

# Başka bir terminal'de test et
curl http://localhost:8000/health
```

### Docker hataları
```bash
# Cache'i temizle ve yeniden başla
docker-compose down
docker-compose up --build
```

---

## 📖 Daha Fazla Bilgi

- **README.md**: Detaylı dokumentasyon
- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **İssues**: https://github.com/soros12345/yasar/issues

---

## 🎓 Öğrenme Kaynakları

- AlphaFold: https://www.deepmind.com/research/align-fold
- AlphaFold DB: https://alphafolddb.csb.pitt.edu/
- FastAPI: https://fastapi.tiangolo.com/
- Streamlit: https://streamlit.io/

---

**Mutlu araştırmaları!** 🧬🔬
