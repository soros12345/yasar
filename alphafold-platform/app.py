"""Ana giriş noktası."""
import sys
import click
from pathlib import Path
from loguru import logger

# Path ayarı
sys.path.insert(0, str(Path(__file__).parent))

# Logger ayarı
logger.remove()
logger.add(sys.stderr, level="INFO")

@click.group()
def main():
    """AlphaFold Platform - Ana Komut Arayüzü."""
    pass

@main.command()
@click.option('--host', default='0.0.0.0', help='API host')
@click.option('--port', default=8000, help='API portu')
def api(host: str, port: int):
    """FastAPI REST API'yi başlat."""
    click.echo(f"🚀 FastAPI API başlatılıyor ({host}:{port})...")
    click.echo("📖 API Dokümantasyonu: http://localhost:8000/docs")
    
    try:
        from api.main import app
        import uvicorn
        uvicorn.run(app, host=host, port=port)
    except Exception as e:
        click.echo(f"❌ API başlatma hatası: {str(e)}", err=True)
        sys.exit(1)

@main.command()
@click.option('--host', default='0.0.0.0', help='UI host')
@click.option('--port', default=8501, help='UI portu')
def ui(host: str, port: int):
    """Streamlit UI'yi başlat."""
    click.echo(f"🎨 Streamlit UI başlatılıyor ({host}:{port})...")
    
    try:
        import subprocess
        subprocess.run([
            "streamlit", "run",
            "ui/app.py",
            "--server.address", host,
            "--server.port", str(port)
        ])
    except Exception as e:
        click.echo(f"❌ UI başlatma hatası: {str(e)}", err=True)
        sys.exit(1)

@main.group()
def cli():
    """CLI komutları."""
    pass

@cli.command()
@click.option('--provider', default='alphafold_db', help='Provider adı')
@click.option('--query', prompt='Arama sorgusu', help='Protein adı, PDB ID vb.')
@click.option('--limit', default=10, help='Sonuç limiti')
def search(provider: str, query: str, limit: int):
    """Protein yapısı ara."""
    click.echo(f"🔍 {provider} içinde ara: {query}")
    
    try:
        import asyncio
        from core.registry import ProviderRegistry
        from core.config import Config
        
        config = Config()
        ProviderRegistry.auto_discover(config.PROVIDERS_DIR)
        
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
def analyze_quality(provider: str, structure_id: str):
    """Yapı kalitesini analiz et."""
    click.echo(f"📊 Kalite analizi: {structure_id}")
    
    try:
        import asyncio
        from core.registry import ProviderRegistry
        from core.config import Config
        from analyzers.quality import QualityAnalyzer
        
        config = Config()
        ProviderRegistry.auto_discover(config.PROVIDERS_DIR)
        
        provider_obj = ProviderRegistry.get(provider)
        prediction = asyncio.run(provider_obj.fetch(structure_id))
        
        analyzer = QualityAnalyzer()
        result = analyzer.analyze(prediction)
        
        click.echo(f"\n✅ Analiz tamamlandı!")
        click.echo(f"  - Ortalama pLDDT: {result.metrics.avg_plddt:.1f}")
        click.echo(f"  - Kalite: {result.metrics.quality_assessment.upper()}")
    
    except Exception as e:
        click.echo(f"❌ Hata: {str(e)}", err=True)

@cli.command()
def list_providers():
    """Kullanılabilir provider'ları listele."""
    click.echo("🔌 Kullanılabilir Provider'lar:\n")
    
    try:
        from core.registry import ProviderRegistry
        from core.config import Config
        
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
    
    except Exception as e:
        click.echo(f"❌ Hata: {str(e)}", err=True)

if __name__ == '__main__':
    main()
