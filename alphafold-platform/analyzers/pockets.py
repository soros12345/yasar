"""Cebi tespiti (ligand binding pockets)."""
from core.models import StructurePrediction, AnalysisResult
import numpy as np
from loguru import logger


class PocketAnalyzer:
    """Potansiyel ligand binding ceplerini tespit et."""
    
    def __init__(self, grid_size: float = 1.0, min_volume: int = 50):
        self.grid_size = grid_size
        self.min_volume = min_volume
    
    def analyze(self, prediction: StructurePrediction) -> AnalysisResult:
        """Cepleri tespit et."""
        logger.info(f"Cep tespiti: {prediction.metadata.protein_name}")
        
        # Koordinatları çıkar
        coords = self._extract_all_coordinates(prediction.pdb_content)
        
        if len(coords) == 0:
            pockets = []
        else:
            # Grid oluştur
            pockets = self._find_pockets(coords)
        
        result_dict = {
            "pocket_count": len(pockets),
            "pockets": [
                {
                    "id": i,
                    "center": p["center"].tolist(),
                    "volume": p["volume"],
                    "atoms_nearby": p["atom_count"]
                }
                for i, p in enumerate(pockets)
            ]
        }
        
        return AnalysisResult(
            analysis_type="pocket_detection",
            structure_id=prediction.id,
            result=result_dict
        )
    
    def _extract_all_coordinates(self, pdb_content: str) -> np.ndarray:
        """Tüm atom koordinatlarını çıkar."""
        coords = []
        for line in pdb_content.split("\n"):
            if line.startswith("ATOM"):
                try:
                    x = float(line[30:38].strip())
                    y = float(line[38:46].strip())
                    z = float(line[46:54].strip())
                    coords.append([x, y, z])
                except (ValueError, IndexError):
                    pass
        return np.array(coords)
    
    def _find_pockets(self, coords: np.ndarray) -> list[dict]:
        """Grid tabanlı cep tespiti."""
        # Sınırları hesapla
        min_coords = np.min(coords, axis=0)
        max_coords = np.max(coords, axis=0)
        
        # Grid oluştur
        pockets = []
        grid_step = self.grid_size
        
        x = min_coords[0]
        while x < max_coords[0]:
            y = min_coords[1]
            while y < max_coords[1]:
                z = min_coords[2]
                while z < max_coords[2]:
                    # Bu grid hücresi etrafında atom say
                    cell_center = np.array([x, y, z])
                    distances = np.linalg.norm(coords - cell_center, axis=1)
                    nearby_atoms = np.sum(distances < 10.0)  # 10Å içinde
                    
                    if nearby_atoms > 0:
                        pockets.append({
                            "center": cell_center,
                            "volume": grid_step**3,
                            "atom_count": int(nearby_atoms)
                        })
                    
                    z += grid_step
                y += grid_step
            x += grid_step
        
        # Çakışan cepleri birleştir (basitleştirilmiş)
        return pockets[:10]  # İlk 10 cep
