"""Kalite analizi."""
from typing import Optional
from core.models import StructurePrediction, QualityMetrics, AnalysisResult
from datetime import datetime
import numpy as np
from loguru import logger


class QualityAnalyzer:
    """Yapı kalitesini analiz et (pLDDT/PAE)."""
    
    def __init__(self, plddt_threshold: float = 70.0, pae_threshold: float = 5.0):
        self.plddt_threshold = plddt_threshold
        self.pae_threshold = pae_threshold
    
    def analyze(self, prediction: StructurePrediction) -> AnalysisResult:
        """Kalite analizi yap."""
        logger.info(f"Kalite analizi: {prediction.metadata.protein_name}")
        
        # pLDDT istatistikleri
        plddt_array = np.array(prediction.plddt_scores)
        avg_plddt = float(np.mean(plddt_array)) if len(plddt_array) > 0 else 0.0
        
        # pLDDT dağılımı
        plddt_dist = self._calculate_plddt_distribution(plddt_array)
        
        # PAE istatistikleri
        avg_pae = None
        if prediction.pae_scores:
            pae_array = np.array(prediction.pae_scores)
            avg_pae = float(np.mean(pae_array))
        
        # Kalite değerlendirmesi
        quality = self._assess_quality(avg_plddt, avg_pae)
        
        metrics = QualityMetrics(
            avg_plddt=avg_plddt,
            avg_pae=avg_pae,
            plddt_distribution=plddt_dist,
            quality_assessment=quality
        )
        
        return AnalysisResult(
            analysis_type="quality_assessment",
            structure_id=prediction.id,
            result={
                "avg_plddt": avg_plddt,
                "avg_pae": avg_pae,
                "plddt_distribution": plddt_dist,
                "quality": quality
            },
            metrics=metrics
        )
    
    def _calculate_plddt_distribution(self, scores: np.ndarray) -> dict[str, int]:
        """pLDDT dağılımını hesapla."""
        if len(scores) == 0:
            return {}
        
        return {
            "very_high (90-100)": int(np.sum(scores >= 90)),
            "high (70-89)": int(np.sum((scores >= 70) & (scores < 90))),
            "medium (50-69)": int(np.sum((scores >= 50) & (scores < 70))),
            "low (0-49)": int(np.sum(scores < 50)),
        }
    
    def _assess_quality(self, avg_plddt: float, avg_pae: Optional[float]) -> str:
        """Kalite değerlendirmesi yap."""
        if avg_plddt >= 90:
            return "excellent"
        elif avg_plddt >= 70:
            return "good"
        elif avg_plddt >= 50:
            return "fair"
        else:
            return "poor"
