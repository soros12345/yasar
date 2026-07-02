"""CLI Entry Point."""
import click
import asyncio
from pathlib import Path
from loguru import logger
import sys

from core.config import Config
from core.registry import ProviderRegistry
from providers.alphafold_db.provider import AlphaFoldDBProvider
from analyzers.quality import QualityAnalyzer
from analyzers.conservation import ConservationAnalyzer

# Logger ayarı
logger.remove()
logger.add(sys.stderr, level="INFO")

@click.group()
def cli():
    """AlphaFold Platform CLI."""
    pass

@cli.command()
@click.option('--provider', default='alphafold_db', help='Provider adı')
@click.option('--query', prompt='Arama sorgusu', help='Protein adı, PDB ID vb.')
@click.option('--limit', default=10, help='Sonuç limiti')
def search(provider: str, query: str, limit: int):
    """Protein yapısı ara."""
    click.echo(f"🔍 {provider} içinde ara: {query}")
    
    try:
        provider_obj = ProviderRegistry.get(provider)
        results = asyncio.run(provider_obj.search(query, limit))
        
        if results:
            click.echo(f"✅ {len(results)} sonuç bulundu:\n")
            for i, result in enumerate(results, 1):
                click.echo(f"{i}. {result.get('id', 'N/A')} - {result.get('name', 'Unknown')}")
        else:
            click.echo("❌ Sonuç bulunamadı.")
    
    except Exception as e:
        click.echo(f"❌ Hata: {str(e)}", err=True)

@cli.command()
@click.option('--provider', default='alphafold_db', help='Provider adı')
@click.option('--structure-id', prompt='Yapı ID', help='AlphaFold ID')
@click.option('--output', default=None, help='Çıkış dosyası (.pdb)')
def fetch(provider: str, structure_id: str, output: str):
    """Yapı indir."""
    click.echo(f"📥 {structure_id} indiriliyör ({provider})...")
    
    try:
        provider_obj = ProviderRegistry.get(provider)
        prediction = asyncio.run(provider_obj.fetch(structure_id))
        
        if output:
            output_path = Path(output)
            output_path.write_text(prediction.pdb_content)
            click.echo(f"✅ Yapı kaydedildi: {output_path}")
        else:
            click.echo(f"✅ Yapı indirildi!")
            click.echo(f"  - Protein: {prediction.metadata.protein_name}")
            click.echo(f"  - Atom sayısı: {prediction.atoms_count}")
            click.echo(f"  - Rezidü sayısı: {prediction.residues_count}")
            click.echo(f"  - Chain'ler: {', '.join(prediction.chains)}")
    
    except Exception as e:
        click.echo(f"❌ Hata: {str(e)}", err=True)

@cli.command()
@click.option('--provider', default='alphafold_db', help='Provider adı')
@click.option('--structure-id', prompt='Yapı ID', help='AlphaFold ID')
def analyze_quality(provider: str, structure_id: str):
    """Yapı kalitesini analiz et."""
    click.echo(f"📊 Kalite analizi: {structure_id}")
    
    try:
        provider_obj = ProviderRegistry.get(provider)
        prediction = asyncio.run(provider_obj.fetch(structure_id))
        
        analyzer = QualityAnalyzer()
        result = analyzer.analyze(prediction)
        
        click.echo(f"\n✅ Analiz tamamlandı!")
        click.echo(f"  - Ortalama pLDDT: {result.metrics.avg_plddt:.1f}")
        click.echo(f"  - Ortalama PAE: {result.metrics.avg_pae or 'N/A'}")
        click.echo(f"  - Kalite: {result.metrics.quality_assessment.upper()}")
        click.echo(f"\n📈 pLDDT Dağılımı:")
        for key, value in result.metrics.plddt_distribution.items():
            click.echo(f"  - {key}: {value}")
    
    except Exception as e:
        click.echo(f"❌ Hata: {str(e)}", err=True)

@cli.command()
@click.option('--provider', default='alphafold_db', help='Provider adı')
@click.option('--structure-id', prompt='Yapı ID', help='AlphaFold ID')
def analyze_conservation(provider: str, structure_id: str):
    """Aminoasit korunumunu analiz et."""
    click.echo(f"🔗 Korunum analizi: {structure_id}")
    
    try:
        provider_obj = ProviderRegistry.get(provider)
        prediction = asyncio.run(provider_obj.fetch(structure_id))
        
        analyzer = ConservationAnalyzer()
        result = analyzer.analyze(prediction)
        
        click.echo(f"\n✅ Analiz tamamlandı!")
        click.echo(f"  - Sekans uzunluğu: {result.result['sequence_length']}")
        click.echo(f"  - Ortalama korunum: {result.result['avg_conservation']:.3f}")
        
        if result.result['conservation_scores']:
            click.echo(f"\n🏆 En korunan pozisyonlar (ilk 5):")
            for score in result.result['conservation_scores'][:5]:
                click.echo(f"  - {score['residue']}{score['position']}: "
                          f"JSD={score['jsd_score']:.3f}, "
                          f"Level={score['conservation_level']}")
    
    except Exception as e:
        click.echo(f"❌ Hata: {str(e)}", err=True)

@cli.command()
def list_providers():
    """Kullanılabilir provider'ları listele."""
    click.echo("🔌 Kullanılabilir Provider'lar:\n")
    
    config = Config()
    ProviderRegistry.auto_discover(config.PROVIDERS_DIR)
    
    available = ProviderRegistry.list_available()
    instances = ProviderRegistry.get_all()
    
    for name in available:
        provider = instances.get(name)
        if provider:
            click.echo(f"✅ {name}")
            click.echo(f"   Açıklama: {provider.description}")
            click.echo(f"   Versiyon: {provider.version}\n")

@cli.command()
def list_analyses():
    """Kullanılabilir analizleri listele."""
    click.echo("🔬 Kullanılabilir Analizler:\n")
    
    analyses = [
        ("quality", "Yapı kalitesini pLDDT/PAE skorlarına göre değerlendir"),
        ("conservation", "Aminoasit korunumunu analiz et (JSD + pLDDT proxy)"),
        ("superposition", "İki yapıyı hizala ve RMSD/TM-score hesapla"),
        ("pockets", "Potansiyel ligand binding ceplerini tespit et"),
        ("variants", "Aminoasit varyantlarının etkisini analiz et (BLOSUM62)"),
        ("ppi", "Protein-protein etkileşimini analiz et"),
    ]
    
    for name, description in analyses:
        click.echo(f"📊 {name}")
        click.echo(f"   {description}\n")

if __name__ == '__main__':
    cli()
