# AlphaFold Platform

🧬 **Protein yapıları analiz et ve araştır** - Model-agnostik AlphaFold Database Platform

## ✨ Özellikler

### 🔌 Plugin Mimarisi
- **ProviderRegistry**: Otomatik provider keşfi ve kaydı
- **Modüler Design**: Yeni provider'lar kolayca ekleyin
- **Genişletilebilir**: Özel provider'lar oluşturun

### 🔬 İçerisindeki Analizciler
- **Kalite**: pLDDT/PAE skorlarına göre değerlendirme
- **Süperpozisyon**: RMSD ve TM-score hesaplama
- **Cep Tespiti**: Ligand binding ceplerini bulma
- **Varyant Analizi**: BLOSUM62 + fizikokimyasal etki
- **Korunum**: JSD + pLDDT proxy kullanarak hesaplama
- **PPI**: Protein-protein etkileşimi analizi

### 🎨 Arayüzler
- **FastAPI**: RESTful API ile programmatic erişim
- **Streamlit**: Web tabanlı interaktif kullanıcı arayüzü
- **CLI**: Komut satırı araçları

## 🏗️ Mimari

```
αlphafold-platform/
├── core/                    # Model-agnostik çekirdek
│   ├── interfaces/          # Soyut sınıflar (StructureProvider, CacheBackend)
│   ├── registry.py          # Plugin kayıt sistemi
│   ├── models.py            # Pydantic veri modelleri
│   ├── config.py            # Merkezi yapılandırma
│   └── exceptions.py        # Özel istisnalar
│
├── providers/               # 🔌 Provider eklentileri
│   └── alphafold_db/        # AlphaFold Database provider
│       ├── provider.py      # @ProviderRegistry.register("alphafold_db")
│       ├── client.py        # EBI REST API istemcisi
│       └── config.py        # Provider yapılandırması
│
├── analyzers/               # 🔬 Model-agnostik analizciler
│   ├── quality.py           # pLDDT/PAE kalitesi
│   ├── superposition.py     # RMSD + TM-score
│   ├── pockets.py           # Grid tabanlı cep tespiti
│   ├── conservation.py      # JSD + pLDDT proxy
│   ├── variants.py          # BLOSUM62 + fizikokimyasal
│   └── ppi.py               # Interface tespiti + şekil tamamlayıcılığı
│
├── api/                     # FastAPI REST API
│   ├── main.py              # Uygulama ve kurulum
│   └── routes/              # Endpoint grupları
│       ├── prediction.py    # /api/predictions
│       ├── search.py        # /api/search
│       ├── providers.py     # /api/providers
│       └── analysis.py      # /api/analysis
│
├── ui/                      # Streamlit web arayüzü
│   ├── app.py               # Ana uygulama (6 sekme)
│   ├── components/          # Yeniden kullanılabilir bileşenler
│   │   ├── provider_selector.py
│   │   └── structure_viewer.py
│   └── pages/               # Analiz sayfaları
│       ├── quality.py       # 🏆 Kalite
│       ├── superposition.py # 📋 Süperpozisyon
│       ├── pockets.py       # 🧲 Cepller
│       ├── variants.py      # 🧬 Varyantlar
│       ├── conservation.py  # 🔗 Korunum
│       └── metadata.py      # 📊 Metaveri
│
├── cli/                     # Komut satırı arayüzü
│   └── main.py              # CLI komutları
│
├── tests/                   # 18+ pytest testleri
│   ├── test_registry.py     # Registry testleri
│   ├── test_quality.py      # Kalite analiz testleri
│   ├── test_cache.py        # Cache testleri
│   ├── test_models.py       # Model testleri
│   ├── test_variants.py     # Varyant analiz testleri
│   ├── test_superposition.py # Süperpozisyon testleri
│   └── conftest.py          # pytest yapılandırması
│
├── app.py                   # Ana giriş: `python app.py api|ui|cli`
├── requirements.txt         # Python bağımlılıkları
├── Dockerfile              # Docker image
├── docker-compose.yml      # Çok-konteyner orkestrasyon
└── .gitignore              # Git yoksayma dosyası
```

## 🚀 Kurulum

### Gereksinimler
- Python 3.11+
- Docker (opsiyonel)

### Yerel Kurulum

```bash
# Depoyu klonla
git clone https://github.com/soros12345/yasar.git
cd yasar/alphafold-platform

# Virtual environment oluştur
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Bağımlılıkları yükle
pip install -r requirements.txt

# Konfigürasyonu ayarla
cp .env.example .env
```

### Docker ile Kurulum

```bash
cd alphafold-platform
docker-compose up -d
```

## 📖 Kullanım

### API Başlatma

```bash
python app.py api --host 0.0.0.0 --port 8000
```

API Dokümantasyonu: http://localhost:8000/docs

### Web UI Başlatma

```bash
python app.py ui
```

Arayüz: http://localhost:8501

### CLI Kullanımı

```bash
# Protein ara
python app.py cli search --query "insulin" --limit 20

# Kalite analizi
python app.py cli analyze-quality --structure-id "AF-P12345-F1"

# Korunum analizi
python app.py cli analyze-conservation --structure-id "AF-P12345-F1"

# Provider'ları listele
python app.py cli list-providers
```

### API Örnekleri

#### Yapı İndir
```bash
curl -X POST http://localhost:8000/api/predictions/fetch \
  -H "Content-Type: application/json" \
  -d '{"provider": "alphafold_db", "structure_id": "AF-P12345-F1"}'
```

#### Protein Ara
```bash
curl "http://localhost:8000/api/search/?q=insulin&provider=alphafold_db&limit=10"
```

#### Kalite Analizi
```bash
curl -X POST http://localhost:8000/api/analysis/quality \
  -H "Content-Type: application/json" \
  -d '{"provider": "alphafold_db", "structure_id": "AF-P12345-F1"}'
```

#### Varyant Analizi
```bash
curl -X POST http://localhost:8000/api/analysis/variant \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "alphafold_db",
    "structure_id": "AF-P12345-F1",
    "position": 100,
    "original_aa": "A",
    "variant_aa": "V"
  }'
```

## 🧪 Testleme

```bash
# Tüm testleri çalıştır
pytest tests/ -v

# Coverage raporu
pytest tests/ --cov=. --cov-report=html

# Belirli test dosyasını çalıştır
pytest tests/test_quality.py -v
```

## 📦 Yapılandırma

`.env` dosyası oluştur:

```env
# Uygulama
APP_NAME="AlphaFold Platform"
DEBUG=false

# Server
API_HOST=0.0.0.0
API_PORT=8000
UI_HOST=0.0.0.0
UI_PORT=8501

# Cache
CACHE_DIR=./cache
CACHE_TTL=86400

# Provider
ACTIVE_PROVIDERS=alphafold_db

# AlphaFold DB
ALPHAFOLD_DB_API_URL=https://alphafolddb.csb.pitt.edu/api/v1
ALPHAFOLD_DB_TIMEOUT=30
```

## 🔌 Yeni Provider Ekleme

```python
# providers/my_provider/provider.py
from core.interfaces.provider import StructureProvider
from core.registry import ProviderRegistry

@ProviderRegistry.register("my_provider")
class MyProvider(StructureProvider):
    name = "my_provider"
    description = "Benim provider'ım"
    version = "1.0.0"
    
    async def search(self, query, limit=10):
        # İmplement et
        pass
    
    async def fetch(self, structure_id):
        # İmplement et
        pass
    
    async def validate(self):
        # İmplement et
        pass
```

## 🔍 Analizci Örneği

```python
from analyzers.quality import QualityAnalyzer

# Provider'dan yapı al
provider = ProviderRegistry.get("alphafold_db")
prediction = await provider.fetch("AF-P12345-F1")

# Analiz et
analyzer = QualityAnalyzer()
result = analyzer.analyze(prediction)

print(f"Kalite: {result.metrics.quality_assessment}")
print(f"Avg pLDDT: {result.metrics.avg_plddt:.1f}")
```

## 📊 Veri Modelleri

### StructurePrediction
```python
StructurePrediction(
    id="...",
    metadata=StructureMetadata(
        pdb_id="7KDX",
        protein_name="SARS-CoV-2 Spike",
        source="alphafold_db"
    ),
    pdb_content="ATOM ...",
    atoms_count=5425,
    residues_count=1273,
    chains=["A", "B"],
    plddt_scores=[95.2, 88.5, ...],
    pae_scores=[[...]]
)
```

## 📝 Lisans

MIT License - Detaylar için [LICENSE](LICENSE) dosyasına bakın

## 👥 Katkıda Bulun

Pull request'ler memnuniyetle karşılanır!

1. Fork et
2. Feature branch oluştur (`git checkout -b feature/AmazingFeature`)
3. Commit et (`git commit -m 'Add AmazingFeature'`)
4. Push et (`git push origin feature/AmazingFeature`)
5. Pull Request aç

## 📞 İletişim

- Issues: https://github.com/soros12345/yasar/issues
- Discussions: https://github.com/soros12345/yasar/discussions
