"""Prediction routes."""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from core.registry import ProviderRegistry
from core.models import StructurePrediction
from core.exceptions import ProviderException
from loguru import logger
import asyncio

router = APIRouter()

class FetchRequest(BaseModel):
    """İstek modeli."""
    provider: str = "alphafold_db"
    structure_id: str

class PredictionResponse(BaseModel):
    """Yanıt modeli."""
    id: str
    protein_name: str
    source: str
    atoms_count: int
    residues_count: int
    chains: list[str]
    avg_plddt: Optional[float] = None

@router.post("/fetch")
async def fetch_prediction(request: FetchRequest):
    """Yapı tahmini indir."""
    try:
        provider = ProviderRegistry.get(request.provider)
        prediction = await provider.fetch(request.structure_id)
        
        import numpy as np
        plddt = np.mean(prediction.plddt_scores) if prediction.plddt_scores else None
        
        return PredictionResponse(
            id=prediction.id,
            protein_name=prediction.metadata.protein_name,
            source=prediction.metadata.source,
            atoms_count=prediction.atoms_count,
            residues_count=prediction.residues_count,
            chains=prediction.chains,
            avg_plddt=float(plddt) if plddt else None
        )
    except Exception as e:
        logger.error(f"Fetch hatası: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/list")
async def list_predictions():
    """Yüklü tahminleri listele."""
    return {"predictions": [], "total": 0}

@router.get("/{prediction_id}")
async def get_prediction(prediction_id: str):
    """Belirli tahminı al."""
    return {"id": prediction_id, "status": "not_found"}
