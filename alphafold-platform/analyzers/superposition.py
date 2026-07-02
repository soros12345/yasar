"""Süperpozisyon analizi (RMSD, TM-score)."""
from typing import Optional
from core.models import StructurePrediction, AnalysisResult
import numpy as np
from loguru import logger


class SuperpositionAnalyzer:
    """İki yapıyı hizala ve RMSD/TM-score hesapla."""
    
    def __init__(self, rmsd_threshold: float = 2.0):
        self.rmsd_threshold = rmsd_threshold
    
    def analyze(self, pred1: StructurePrediction, pred2: StructurePrediction) -> AnalysisResult:
        """İki yapıyı karşılaştır."""
        logger.info(f"Süperpozisyon: {pred1.metadata.protein_name} vs {pred2.metadata.protein_name}")
        
        # Koordinatları çıkar
        coords1 = self._extract_coordinates(pred1.pdb_content)
        coords2 = self._extract_coordinates(pred2.pdb_content)
        
        if len(coords1) == 0 or len(coords2) == 0:
            raise ValueError("Koordinatlar çıkarılamadı")
        
        # En küçük boyutu kullan
        min_len = min(len(coords1), len(coords2))
        coords1 = coords1[:min_len]
        coords2 = coords2[:min_len]
        
        # RMSD hesapla
        rmsd = self._calculate_rmsd(coords1, coords2)
        
        # TM-score hesapla
        tm_score = self._calculate_tm_score(coords1, coords2)
        
        result_dict = {
            "rmsd": rmsd,
            "tm_score": tm_score,
            "aligned_atoms": min_len,
            "similarity": "high" if rmsd < self.rmsd_threshold else "low"
        }
        
        return AnalysisResult(
            analysis_type="superposition",
            structure_id=f"{pred1.id}_{pred2.id}",
            result=result_dict
        )
    
    def _extract_coordinates(self, pdb_content: str) -> np.ndarray:
        """PDB'den CA atomlarının koordinatlarını çıkar."""
        coords = []
        for line in pdb_content.split("\n"):
            if line.startswith("ATOM") and line[12:16].strip() == "CA":
                try:
                    x = float(line[30:38].strip())
                    y = float(line[38:46].strip())
                    z = float(line[46:54].strip())
                    coords.append([x, y, z])
                except (ValueError, IndexError):
                    pass
        return np.array(coords)
    
    def _calculate_rmsd(self, coords1: np.ndarray, coords2: np.ndarray) -> float:
        """RMSD hesapla (Root Mean Square Deviation)."""
        diff = coords1 - coords2
        rmsd = np.sqrt(np.mean(np.sum(diff**2, axis=1)))
        return float(rmsd)
    
    def _calculate_tm_score(self, coords1: np.ndarray, coords2: np.ndarray) -> float:
        """TM-score hesapla (Basitleştirilmiş)."""
        # Basit TM-score (0-1 arası)
        dmax = 15.0  # Referans mesafe
        diff = coords1 - coords2
        distances = np.sqrt(np.sum(diff**2, axis=1))
        tm = np.mean(1.0 / (1.0 + (distances / dmax)**2))
        return float(tm)
