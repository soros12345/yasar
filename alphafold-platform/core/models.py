"""Pydantic veri modelleri."""
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field
import numpy as np


class StructureMetadata(BaseModel):
    """Yapı metaveri."""
    pdb_id: Optional[str] = None
    protein_name: str
    organism: Optional[str] = None
    source: str  # Provider adı
    resolution: Optional[float] = None
    released_date: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "pdb_id": "7KDX",
                "protein_name": "SARS-CoV-2 Spike Protein",
                "organism": "SARS-CoV-2",
                "source": "alphafold_db",
                "resolution": 2.45,
                "released_date": "2024-01-15T00:00:00"
            }
        }


class StructurePrediction(BaseModel):
    """Yapı tahmini."""
    id: str = Field(default_factory=lambda: str(datetime.now().timestamp()))
    metadata: StructureMetadata
    pdb_content: str  # PDB dosya içeriği
    atoms_count: int
    residues_count: int
    chains: list[str]
    plddt_scores: list[float] = Field(default_factory=list)  # Atom başına
    pae_scores: Optional[list[list[float]]] = None  # Rezidü başına
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "1704067200.0",
                "metadata": {
                    "protein_name": "SARS-CoV-2 Spike",
                    "source": "alphafold_db"
                },
                "pdb_content": "ATOM      1  N   ALA A   1...",
                "atoms_count": 5425,
                "residues_count": 1273,
                "chains": ["A", "B"],
                "plddt_scores": [95.2, 88.5, ...]
            }
        }


class QualityMetrics(BaseModel):
    """Kalite metrikleri."""
    avg_plddt: float
    avg_pae: Optional[float] = None
    plddt_distribution: dict[str, int] = Field(default_factory=dict)  # Aralık->sayı
    quality_assessment: str  # "excellent", "good", "fair", "poor"


class AnalysisResult(BaseModel):
    """Analiz sonuçu."""
    analysis_type: str
    structure_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    result: dict[str, Any]
    metrics: Optional[QualityMetrics] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "analysis_type": "quality_assessment",
                "structure_id": "1704067200.0",
                "result": {"avg_plddt": 87.3, "quality": "good"},
                "metrics": {"avg_plddt": 87.3, "quality_assessment": "good"}
            }
        }


class VariantEffect(BaseModel):
    """Varyant etkisi."""
    position: int
    original_residue: str
    variant_residue: str
    blosum_score: float
    physicochemical_score: float
    confidence: float
    prediction: str  # "benign", "deleterious", "unknown"


class ConservationScore(BaseModel):
    """Korunum puanı."""
    position: int
    residue: str
    jsd_score: float  # Jensen-Shannon divergence
    plddt_proxy: float
    conservation_level: str  # "highly", "moderately", "weakly", "not"
