"""FastAPI REST API."""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger
import sys

from core.config import Config
from core.registry import ProviderRegistry
from api.routes import prediction, search, providers, analysis

# Konfigürasyon
config = Config()

# Logger ayarı
logger.remove()
logger.add(sys.stderr, level="INFO")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama yaşam döngüsü."""
    # Başlangıçta
    logger.info("AlphaFold Platform API başlıyor...")
    ProviderRegistry.auto_discover(config.PROVIDERS_DIR)
    available = ProviderRegistry.list_available()
    logger.info(f"Kullanılabilir providers: {available}")
    
    yield
    
    # Kapanışta
    logger.info("API kapanıyor...")

# FastAPI uygulaması
app = FastAPI(
    title=config.APP_NAME,
    version=config.APP_VERSION,
    description="AlphaFold Structure Database Platform",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(prediction.router, prefix="/api/predictions", tags=["Predictions"])
app.include_router(search.router, prefix="/api/search", tags=["Search"])
app.include_router(providers.router, prefix="/api/providers", tags=["Providers"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])

@app.get("/health")
async def health_check():
    """Sağlık kontrolü."""
    return {"status": "healthy", "version": config.APP_VERSION}

@app.get("/")
async def root():
    """API kökü."""
    return {
        "name": config.APP_NAME,
        "version": config.APP_VERSION,
        "endpoints": {
            "predictions": "/api/predictions",
            "search": "/api/search",
            "providers": "/api/providers",
            "analysis": "/api/analysis",
            "health": "/health"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=config.API_HOST,
        port=config.API_PORT,
        log_level="info"
    )
