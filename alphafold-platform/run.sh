#!/bin/bash
# AlphaFold Platform - Başlatma Betiği

set -e

# Renkler
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logo
echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════╗"
echo "║     🧬 AlphaFold Platform                          ║"
echo "║     Protein Yapı Analiz ve Araştırma Platformu    ║"
echo "╚═══════════════════════════════════════════════════╝"
echo -e "${NC}"

# Yardım
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo -e "${YELLOW}Kullanım:${NC}"
    echo "  $0 api        - FastAPI REST API'yi başlat"
    echo "  $0 ui         - Streamlit Web UI'yi başlat"
    echo "  $0 cli        - CLI'yi başlat"
    echo "  $0 test       - Testleri çalıştır"
    echo "  $0 docker     - Docker Compose ile başlat"
    echo "  $0 dev        - Geliştirme modunda çalıştır"
    exit 0
fi

# Komut seçimi
case "${1:-help}" in
    api)
        echo -e "${GREEN}[*] FastAPI API başlatılıyor...${NC}"
        python app.py api --host 0.0.0.0 --port 8000
        ;;
    ui)
        echo -e "${GREEN}[*] Streamlit UI başlatılıyor...${NC}"
        python app.py ui
        ;;
    cli)
        echo -e "${GREEN}[*] CLI başlatılıyor...${NC}"
        python app.py cli list-providers
        ;;
    test)
        echo -e "${GREEN}[*] Testler çalıştırılıyor...${NC}"
        pytest tests/ -v --cov=. --cov-report=html
        ;;
    docker)
        echo -e "${GREEN}[*] Docker Compose ile başlatılıyor...${NC}"
        docker-compose up -d
        echo -e "${GREEN}[✓] Hizmetler başlatıldı:${NC}"
        echo "  API: http://localhost:8000 (Docs: http://localhost:8000/docs)"
        echo "  UI:  http://localhost:8501"
        ;;
    dev)
        echo -e "${GREEN}[*] Geliştirme modunda çalıştırılıyor...${NC}"
        export DEBUG=true
        python app.py api
        ;;
    *)
        echo -e "${RED}Bilinmeyen komut: $1${NC}"
        echo "Yardım için: $0 --help"
        exit 1
        ;;
esac
