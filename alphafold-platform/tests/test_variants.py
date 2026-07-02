"""Varyant analizi testleri."""
import pytest
from analyzers.variants import VariantAnalyzer
from core.models import StructurePrediction, StructureMetadata

@pytest.fixture
def sample_prediction():
    """Örnek yapı tahmini."""
    metadata = StructureMetadata(
        protein_name="Test Protein",
        source="test"
    )
    
    return StructurePrediction(
        metadata=metadata,
        pdb_content="ATOM      1  N   ALA",
        atoms_count=100,
        residues_count=10,
        chains=["A"],
        plddt_scores=[90.0] * 100
    )

def test_variant_analysis(sample_prediction):
    """Varyant analizini test et."""
    analyzer = VariantAnalyzer()
    result = analyzer.analyze(
        sample_prediction,
        position=50,
        original_aa="A",
        variant_aa="V"
    )
    
    assert result.analysis_type == "variant_effect"
    assert "prediction" in result.result

def test_blosum_score():
    """BLOSUM skoru testi."""
    analyzer = VariantAnalyzer()
    
    # Aynı amino asit
    score = analyzer._get_blosum_score("A", "A")
    assert score == 4  # Beklenen BLOSUM62 skoru
    
    # Farklı amino asitler
    score = analyzer._get_blosum_score("A", "R")
    assert isinstance(score, int)

def test_physicochemical_score():
    """Fizikokimyasal skor testi."""
    analyzer = VariantAnalyzer()
    
    # Hidrofobik ve polar
    score = analyzer._calculate_physicochemical_score("L", "K")
    assert isinstance(score, float)
    assert score < 0  # Negatif = farklı
    
    # Benzer
    score = analyzer._calculate_physicochemical_score("L", "I")
    assert isinstance(score, float)

def test_variant_prediction():
    """Varyant tahmini testi."""
    analyzer = VariantAnalyzer()
    
    # Benign
    pred = analyzer._predict_effect(5, -1)
    assert pred == "benign"
    
    # Zararlı
    pred = analyzer._predict_effect(-5, -2)
    assert pred == "deleterious"
