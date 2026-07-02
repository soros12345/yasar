"""Model testleri."""
import pytest
from core.models import (
    StructureMetadata,
    StructurePrediction,
    QualityMetrics,
    AnalysisResult,
    VariantEffect,
    ConservationScore
)
from datetime import datetime

def test_structure_metadata():
    """StructureMetadata modeli."""
    metadata = StructureMetadata(
        pdb_id="7KDX",
        protein_name="SARS-CoV-2 Spike",
        organism="SARS-CoV-2",
        source="alphafold_db",
        resolution=2.45
    )
    
    assert metadata.pdb_id == "7KDX"
    assert metadata.protein_name == "SARS-CoV-2 Spike"
    assert metadata.source == "alphafold_db"

def test_structure_prediction():
    """StructurePrediction modeli."""
    metadata = StructureMetadata(
        protein_name="Test Protein",
        source="test"
    )
    
    prediction = StructurePrediction(
        metadata=metadata,
        pdb_content="ATOM      1  N   ALA",
        atoms_count=100,
        residues_count=10,
        chains=["A"],
        plddt_scores=[95.0, 88.5, 92.1]
    )
    
    assert prediction.atoms_count == 100
    assert prediction.residues_count == 10
    assert len(prediction.chains) == 1
    assert len(prediction.plddt_scores) == 3

def test_quality_metrics():
    """QualityMetrics modeli."""
    metrics = QualityMetrics(
        avg_plddt=87.3,
        avg_pae=5.2,
        plddt_distribution={
            "very_high (90-100)": 50,
            "high (70-89)": 30,
            "medium (50-69)": 15,
            "low (0-49)": 5
        },
        quality_assessment="good"
    )
    
    assert metrics.avg_plddt == 87.3
    assert metrics.quality_assessment == "good"

def test_analysis_result():
    """AnalysisResult modeli."""
    result = AnalysisResult(
        analysis_type="quality_assessment",
        structure_id="test_123",
        result={"status": "success"}
    )
    
    assert result.analysis_type == "quality_assessment"
    assert result.structure_id == "test_123"
    assert result.result["status"] == "success"

def test_variant_effect():
    """VariantEffect modeli."""
    variant = VariantEffect(
        position=100,
        original_residue="A",
        variant_residue="V",
        blosum_score=4.0,
        physicochemical_score=-2.5,
        confidence=0.85,
        prediction="benign"
    )
    
    assert variant.position == 100
    assert variant.prediction == "benign"

def test_conservation_score():
    """ConservationScore modeli."""
    score = ConservationScore(
        position=50,
        residue="K",
        jsd_score=0.85,
        plddt_proxy=92.0,
        conservation_level="highly"
    )
    
    assert score.position == 50
    assert score.residue == "K"
    assert score.conservation_level == "highly"
