"""Aminoasit korunum analizi (JSD + pLDDT proxy)."""
from core.models import StructurePrediction, AnalysisResult, ConservationScore
import numpy as np
from scipy.spatial.distance import jensenshannon
from loguru import logger


class ConservationAnalyzer:
    """Korunum skorlarını hesapla (JSD + pLDDT proxy)."""
    
    # Amino asit frekansları (basit model)
    BACKGROUND_FREQ = {
        'A': 0.082, 'C': 0.015, 'D': 0.054, 'E': 0.061, 'F': 0.040,
        'G': 0.074, 'H': 0.023, 'I': 0.059, 'K': 0.064, 'L': 0.099,
        'M': 0.023, 'N': 0.043, 'P': 0.052, 'Q': 0.041, 'R': 0.052,
        'S': 0.072, 'T': 0.062, 'V': 0.073, 'W': 0.013, 'Y': 0.033
    }
    
    def analyze(self, prediction: StructurePrediction) -> AnalysisResult:
        """Korunum analizi yap."""
        logger.info(f"Korunum analizi: {prediction.metadata.protein_name}")
        
        # Sekans çıkar
        sequence = self._extract_sequence(prediction.pdb_content)
        plddt_scores = prediction.plddt_scores
        
        conservation_scores = []
        
        for pos, aa in enumerate(sequence):
            if aa not in self.BACKGROUND_FREQ:
                continue
            
            # JSD hesapla (basitleştirilmiş)
            jsd = self._calculate_jsd(aa)
            
            # pLDDT proxy
            if pos < len(plddt_scores):
                plddt_proxy = plddt_scores[pos]
            else:
                plddt_proxy = 0.0
            
            # Korunum seviyesi
            conservation_level = self._assess_conservation(jsd)
            
            conservation_scores.append(ConservationScore(
                position=pos,
                residue=aa,
                jsd_score=jsd,
                plddt_proxy=plddt_proxy,
                conservation_level=conservation_level
            ))
        
        return AnalysisResult(
            analysis_type="conservation_analysis",
            structure_id=prediction.id,
            result={
                "sequence_length": len(sequence),
                "conservation_scores": [
                    s.dict() for s in conservation_scores[:20]  # İlk 20
                ],
                "avg_conservation": np.mean([s.jsd_score for s in conservation_scores])
            }
        )
    
    def _extract_sequence(self, pdb_content: str) -> str:
        """PDB'den protein sekvansını çıkar."""
        # 3-harf kodunu 1-harf koduna çevir
        three_to_one = {
            'ALA': 'A', 'ARG': 'R', 'ASN': 'N', 'ASP': 'D', 'CYS': 'C',
            'GLN': 'Q', 'GLU': 'E', 'GLY': 'G', 'HIS': 'H', 'ILE': 'I',
            'LEU': 'L', 'LYS': 'K', 'MET': 'M', 'PHE': 'F', 'PRO': 'P',
            'SER': 'S', 'THR': 'T', 'TRP': 'W', 'TYR': 'Y', 'VAL': 'V'
        }
        
        sequence = []
        prev_res_num = None
        
        for line in pdb_content.split("\n"):
            if line.startswith("ATOM") and line[12:16].strip() == "CA":
                res_name = line[17:20].strip()
                res_num = line[22:26].strip()
                
                if res_num != prev_res_num:
                    aa = three_to_one.get(res_name, 'X')
                    sequence.append(aa)
                    prev_res_num = res_num
        
        return ''.join(sequence)
    
    def _calculate_jsd(self, aa: str) -> float:
        """Jensen-Shannon divergence hesapla."""
        # Background frekansları
        p = np.array([self.BACKGROUND_FREQ.get(a, 0.05) for a in self.BACKGROUND_FREQ.keys()])
        p = p / np.sum(p)
        
        # Gözlenen frekans (tek amino asit)
        q = np.zeros_like(p)
        aa_list = list(self.BACKGROUND_FREQ.keys())
        if aa in aa_list:
            q[aa_list.index(aa)] = 1.0
        
        jsd = jensenshannon(p, q)
        return float(jsd)
    
    def _assess_conservation(self, jsd: float) -> str:
        """Korunum seviyesi değerlendir."""
        if jsd > 0.7:
            return "highly"
        elif jsd > 0.4:
            return "moderately"
        elif jsd > 0.2:
            return "weakly"
        else:
            return "not"
