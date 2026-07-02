@echo off
REM AlphaFold Platform - Windows Başlatma Betiği

setlocal enabledelayedexpansion

echo.
echo ==================================================
echo   ^🧬 AlphaFold Platform
echo   Protein Yapi Analiz ve Arastirma Platformu
echo ==================================================
echo.

if "%1"=="--help" goto help
if "%1"=="-h" goto help
if "%1"=="" goto help

goto %1

:api
echo [*] FastAPI API baslatiliyor...
python app.py api --host 0.0.0.0 --port 8000
goto end

:ui
echo [*] Streamlit UI baslatiliyor...
python app.py ui
goto end

:cli
echo [*] CLI baslatiliyor...
python app.py cli list-providers
goto end

:test
echo [*] Testler calistiriliyor...
pytest tests/ -v --cov=. --cov-report=html
goto end

:docker
echo [*] Docker Compose ile baslatiliyor...
docker-compose up -d
echo.
echo [OK] Hizmetler baslatildi:
echo   API: http://localhost:8000 (Docs: http://localhost:8000/docs)
echo   UI:  http://localhost:8501
echo.
goto end

:dev
echo [*] Gelistirme modunda calistiriliyor...
set DEBUG=true
python app.py api
goto end

:help
echo Kullanim:
echo   %0 api        - FastAPI REST API'yi baslat
echo   %0 ui         - Streamlit Web UI'yi baslat
echo   %0 cli        - CLI'yi baslat
echo   %0 test       - Testleri calistir
echo   %0 docker     - Docker Compose ile baslat
echo   %0 dev        - Gelistirme modunda calistir
echo   %0 --help     - Bu yardimi goster
goto end

:end
endlocal
