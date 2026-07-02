"""Superposition analiz testleri."""
import pytest
import numpy as np
from analyzers.superposition import SuperpositionAnalyzer
from core.models import StructurePrediction, StructureMetadata

@pytest.fixture
def sample_predictions():
    """Örnek yapı tahminleri."""
    metadata = StructureMetadata(
        protein_name="Test Protein",
        source="test"
    )
    
    # PDB içeriği (basit CA atomları)
    pdb_content = """ATOM      1  CA  ALA A   1      10.000  10.000  10.000  1.00  0.00           C
ATOM      2  CA  ALA A   2      11.000  11.000  11.000  1.00  0.00           C
ATOM      3  CA  ALA A   3      12.000  12.000  12.000  1.00  0.00           C"""
    
    pred1 = StructurePrediction(
        metadata=metadata,
        pdb_content=pdb_content,
        atoms_count=3,
        residues_count=3,
        chains=["A"],
        plddt_scores=[90.0, 88.0, 92.0]
    )
    
    # İkinci yapı (biraz kaydırılmış)
    pdb_content2 = """ATOM      1  CA  ALA B   1      10.100  10.100  10.100  1.00  0.00           C
ATOM      2  CA  ALA B   2      11.100  11.100  11.100  1.00  0.00           C
ATOM      3  CA  ALA B   3      12.100  12.100  12.100  1.00  0.00           C"""
    
    pred2 = StructurePrediction(
        metadata=metadata,
        pdb_content=pdb_content2,
        atoms_count=3,
        residues_count=3,
        chains=["B"],
        plddt_scores=[91.0, 89.0, 93.0]
    )
    
    return pred1, pred2

def test_extract_coordinates(sample_predictions):
    """Koordinat çıkarmayı test et."""
    analyzer = SuperpositionAnalyzer()
    pred1, _ = sample_predictions
    
    coords = analyzer._extract_coordinates(pred1.pdb_content)
    
    assert len(coords) == 3
    assert coords.shape == (3, 3)

def test_rmsd_calculation():
    """RMSD hesaplamayı test et."""
    analyzer = SuperpositionAnalyzer()
    
    # Aynı koordinatlar
    coords1 = np.array([[1, 1, 1], [2, 2, 2], [3, 3, 3]], dtype=float)
    coords2 = np.array([[1, 1, 1], [2, 2, 2], [3, 3, 3]], dtype=float)
    
    rmsd = analyzer._calculate_rmsd(coords1, coords2)
    assert rmsd < 0.001  # ~0
    
    # Farklı koordinatlar
    coords3 = np.array([[1.5, 1.5, 1.5], [2.5, 2.5, 2.5], [3.5, 3.5, 3.5]], dtype=float)
    rmsd = analyzer._calculate_rmsd(coords1, coords3)
    assert rmsd > 0.5

def test_tm_score_calculation():
    """TM-score hesaplamayı test et."""
    analyzer = SuperpositionAnalyzer()
    
    # Aynı koordinatlar
    coords = np.array([[1, 1, 1], [2, 2, 2], [3, 3, 3]], dtype=float)
    tm = analyzer._calculate_tm_score(coords, coords)
    assert tm > 0.99  # ~1
