"""Analysis routes."""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from core.registry import ProviderRegistry
from analyzers.quality import QualityAnalyzer
from analyzers.conservation import ConservationAnalyzer
from analyzers.variants import VariantAnalyzer
from loguru import logger

router = APIRouter()

class QualityAnalysisRequest(BaseModel):
    """Kalite analizi isteği."""
    provider: str = "alphafold_db"
    structure_id: str

class VariantAnalysisRequest(BaseModel):
    """Varyant analizi isteği."""
    provider: str = "alphafold_db"
    structure_id: str
    position: int
    original_aa: str
    variant_aa: str

@router.post("/quality")
async def analyze_quality(request: QualityAnalysisRequest):
    """Yapı kalitesini analiz et."""
    try:
        # Provider'dan yapıyı al
        provider = ProviderRegistry.get(request.provider)
        prediction = await provider.fetch(request.structure_id)
        
        # Analiz yap
        analyzer = QualityAnalyzer()
        result = analyzer.analyze(prediction)
        
        return result.dict()
    except Exception as e:
        logger.error(f"Kalite analizi hatası: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/conservation")
async def analyze_conservation(request: QualityAnalysisRequest):
    """Aminoasit korunum analizi yap."""
    try:
        provider = ProviderRegistry.get(request.provider)
        prediction = await provider.fetch(request.structure_id)
        
        analyzer = ConservationAnalyzer()
        result = analyzer.analyze(prediction)
        
        return result.dict()
    except Exception as e:
        logger.error(f"Korunum analizi hatası: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/variant")
async def analyze_variant(request: VariantAnalysisRequest):
    """Varyant etkisini analiz et."""
    try:
        provider = ProviderRegistry.get(request.provider)
        prediction = await provider.fetch(request.structure_id)
        
        analyzer = VariantAnalyzer()
        result = analyzer.analyze(
            prediction,
            request.position,
            request.original_aa,
            request.variant_aa
        )
        
        return result.dict()
    except Exception as e:
        logger.error(f"Varyant analizi hatası: {e}")
        raise HTTPException(status_code=400, detail=str(e))
