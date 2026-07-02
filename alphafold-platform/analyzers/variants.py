"""Varyant etki analizi (BLOSUM62 + fizikokimyasal özellikler)."""
from core.models import StructurePrediction, AnalysisResult, VariantEffect
from loguru import logger


class VariantAnalyzer:
    """Aminoasit varyantlarının etkisini analiz et."""
    
    # BLOSUM62 matrisi (basitleştirilmiş)
    BLOSUM62 = {
        ('A', 'A'): 4, ('A', 'R'): -1, ('A', 'N'): -2,
        ('R', 'R'): 5, ('R', 'N'): 0,
        ('N', 'N'): 6,
    }
    
    # Fizikokimyasal özellikler
    PROPERTIES = {
        'A': {'hydrophobic': 1.8, 'size': 1},
        'R': {'hydrophobic': -4.5, 'size': 3},
        'N': {'hydrophobic': -3.5, 'size': 2},
        'D': {'hydrophobic': -3.5, 'size': 2},
        'C': {'hydrophobic': 2.5, 'size': 1},
        'Q': {'hydrophobic': -3.5, 'size': 3},
        'E': {'hydrophobic': -3.5, 'size': 3},
        'G': {'hydrophobic': -0.4, 'size': 0},
        'H': {'hydrophobic': -3.2, 'size': 2},
        'I': {'hydrophobic': 4.5, 'size': 2},
    }
    
    def analyze(self, prediction: StructurePrediction, position: int,
                original_aa: str, variant_aa: str) -> AnalysisResult:
        """Varyant etkisini analiz et."""
        logger.info(f"Varyant analizi: {original_aa}{position}{variant_aa}")
        
        # BLOSUM skoru
        blosum_score = self._get_blosum_score(original_aa, variant_aa)
        
        # Fizikokimyasal skor
        phys_score = self._calculate_physicochemical_score(original_aa, variant_aa)
        
        # Güven puanı
        confidence = 0.7  # pLDDT veya başka faktörlere göre
        
        # Tahmin
        prediction_type = self._predict_effect(blosum_score, phys_score)
        
        variant = VariantEffect(
            position=position,
            original_residue=original_aa,
            variant_residue=variant_aa,
            blosum_score=float(blosum_score),
            physicochemical_score=float(phys_score),
            confidence=confidence,
            prediction=prediction_type
        )
        
        return AnalysisResult(
            analysis_type="variant_effect",
            structure_id=prediction.id,
            result=variant.dict()
        )
    
    def _get_blosum_score(self, aa1: str, aa2: str) -> int:
        """BLOSUM62 skorunu al."""
        key = tuple(sorted([aa1, aa2]))
        return self.BLOSUM62.get(key, 0)
    
    def _calculate_physicochemical_score(self, aa1: str, aa2: str) -> float:
        """Fizikokimyasal özellik farkı."""
        if aa1 not in self.PROPERTIES or aa2 not in self.PROPERTIES:
            return 0.0
        
        hydro_diff = abs(
            self.PROPERTIES[aa1]['hydrophobic'] -
            self.PROPERTIES[aa2]['hydrophobic']
        )
        size_diff = abs(
            self.PROPERTIES[aa1]['size'] -
            self.PROPERTIES[aa2]['size']
        )
        
        return -(hydro_diff + size_diff)  # Negatif = daha benzer
    
    def _predict_effect(self, blosum: int, phys: float) -> str:
        """Varyant etkisini tahmin et."""
        score = blosum + phys
        if score > 2:
            return "benign"
        elif score < -2:
            return "deleterious"
        else:
            return "unknown"
