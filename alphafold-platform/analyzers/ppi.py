"""Protein-protein etkileşimi (PPI) analizi."""
from core.models import StructurePrediction, AnalysisResult
import numpy as np
from loguru import logger


class PPIAnalyzer:
    """Protein-protein arayüzünü analiz et."""
    
    def __init__(self, interface_distance: float = 5.0):
        self.interface_distance = interface_distance
    
    def analyze(self, pred1: StructurePrediction, pred2: StructurePrediction) -> AnalysisResult:
        """İki protein arasında etkileşimi analiz et."""
        logger.info(f"PPI analizi: {pred1.metadata.protein_name} + {pred2.metadata.protein_name}")
        
        # Koordinatları çıkar
        coords1 = self._extract_ca_coordinates(pred1.pdb_content)
        coords2 = self._extract_ca_coordinates(pred2.pdb_content)
        
        # Arayüz bul
        interface_atoms = self._find_interface(coords1, coords2)
        
        # Şekil tamamlayıcılığı hesapla
        shape_complementarity = self._calculate_shape_complementarity(coords1, coords2)
        
        result_dict = {
            "interface_atom_count_1": len([x for x in interface_atoms if x[0] < len(coords1)]),
            "interface_atom_count_2": len([x for x in interface_atoms if x[0] >= len(coords1)]),
            "total_interface_atoms": len(interface_atoms),
            "interface_area": len(interface_atoms) * 20.0,  # Tahmini
            "shape_complementarity": shape_complementarity,
            "binding_probability": min(0.95, shape_complementarity)
        }
        
        return AnalysisResult(
            analysis_type="ppi_analysis",
            structure_id=f"{pred1.id}_{pred2.id}",
            result=result_dict
        )
    
    def _extract_ca_coordinates(self, pdb_content: str) -> np.ndarray:
        """CA atom koordinatlarını çıkar."""
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
    
    def _find_interface(self, coords1: np.ndarray, coords2: np.ndarray) -> list[tuple]:
        """Protein arayüzünü bul."""
        interface = []
        for i, c1 in enumerate(coords1):
            for j, c2 in enumerate(coords2):
                dist = np.linalg.norm(c1 - c2)
                if dist < self.interface_distance:
                    interface.append((i, j))
        return interface
    
    def _calculate_shape_complementarity(self, coords1: np.ndarray, coords2: np.ndarray) -> float:
        """Şekil tamamlayıcılığını hesapla (basitleştirilmiş)."""
        if len(coords1) == 0 or len(coords2) == 0:
            return 0.0
        
        # Merkez mesafesi
        center1 = np.mean(coords1, axis=0)
        center2 = np.mean(coords2, axis=0)
        center_dist = np.linalg.norm(center1 - center2)
        
        # Normalize edilmiş skor
        score = 1.0 / (1.0 + center_dist / 10.0)
        return float(score)
