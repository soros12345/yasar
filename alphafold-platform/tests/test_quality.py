"""Kalite analiz testleri."""
import pytest
import numpy as np
from core.models import StructurePrediction, StructureMetadata
from analyzers.quality import QualityAnalyzer

@pytest.fixture
def sample_prediction():
    """Örnek yapı tahmini."""
    metadata = StructureMetadata(
        protein_name="Test Protein",
        source="test"
    )
    
    # Örnek pLDDT skorları
    plddt_scores = [95.2, 88.5, 92.1, 85.3, 78.9, 95.0, 88.2] * 100
    
    return StructurePrediction(
        metadata=metadata,
        pdb_content="ATOM      1  N   ALA A   1",
        atoms_count=700,
        residues_count=100,
        chains=["A"],
        plddt_scores=plddt_scores
    )

def test_quality_analysis(sample_prediction):
    """Kalite analizini test et."""
    analyzer = QualityAnalyzer()
    result = analyzer.analyze(sample_prediction)
    
    assert result.analysis_type == "quality_assessment"
    assert result.metrics.avg_plddt > 0
    assert result.metrics.quality_assessment in ["excellent", "good", "fair", "poor"]

def test_plddt_distribution(sample_prediction):
    """pLDDT dağılımını test et."""
    analyzer = QualityAnalyzer()
    result = analyzer.analyze(sample_prediction)
    
    dist = result.metrics.plddt_distribution
    assert "very_high (90-100)" in dist
    assert "high (70-89)" in dist
    assert "medium (50-69)" in dist
    assert "low (0-49)" in dist

def test_quality_assessment():
    """Kalite değerlendirmesini test et."""
    analyzer = QualityAnalyzer()
    
    # Mükemmel
    assert analyzer._assess_quality(95.0, None) == "excellent"
    
    # İyi
    assert analyzer._assess_quality(80.0, None) == "good"
    
    # Orta
    assert analyzer._assess_quality(60.0, None) == "fair"
    
    # Kötü
    assert analyzer._assess_quality(30.0, None) == "poor"
