# Makefile - AlphaFold Platform

.PHONY: help install dev test clean api ui cli docker docker-up docker-down

help:
	@echo "AlphaFold Platform - Komutlar"
	@echo ""
	@echo "  make install    - Ba\u011f\u0131ml\u0131l\u0131klar\u0131 y\u00fckle"
	@echo "  make dev        - Geli\u015ftirme ortam\u0131n\u0131 kur"
	@echo "  make test       - Testleri \u00e7al\u0131\u015ft\u0131r"
	@echo "  make clean      - Ge\u00e7ici dosyalar\u0131 temizle"
	@echo "  make api        - FastAPI ba\u015flat"
	@echo "  make ui         - Streamlit ba\u015flat"
	@echo "  make cli        - CLI \u00e7al\u0131\u015ft\u0131r"
	@echo "  make docker     - Docker image olu\u015ftur"
	@echo "  make docker-up  - Docker Compose ba\u015flat"
	@echo "  make docker-down- Docker Compose durdur"

install:
	pip install -r requirements.txt

dev:
	pip install -r requirements.txt
	pip install pytest pytest-asyncio pytest-cov ipython

test:
	pytest tests/ -v --cov=. --cov-report=html

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -delete
	rm -rf htmlcov/

api:
	python app.py api

ui:
	python app.py ui

cli:
	python app.py cli list-providers

docker:
	docker build -t alphafold-platform .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down
