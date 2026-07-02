"""Search routes."""
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional
from core.registry import ProviderRegistry
from loguru import logger

router = APIRouter()

class SearchResult(BaseModel):
    """Arama sonucu."""
    id: str
    name: str
    organism: Optional[str] = None
    source: str

@router.get("/")
async def search(
    q: str = Query(..., min_length=1, description="Arama sorgusu"),
    provider: str = "alphafold_db",
    limit: int = Query(10, ge=1, le=100)
):
    """Yapı ara."""
    try:
        provider_obj = ProviderRegistry.get(provider)
        results = await provider_obj.search(q, limit)
        
        return {
            "query": q,
            "provider": provider,
            "results": results[:limit],
            "total": len(results)
        }
    except Exception as e:
        logger.error(f"Arama hatası: {e}")
        return {
            "query": q,
            "provider": provider,
            "results": [],
            "total": 0,
            "error": str(e)
        }

@router.get("/providers/{provider}")
async def search_by_provider(provider: str, q: str = Query(...)):
    """Belirli provider'da ara."""
    try:
        provider_obj = ProviderRegistry.get(provider)
        results = await provider_obj.search(q)
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Provider arama hatası: {e}")
        return {"results": [], "count": 0, "error": str(e)}
