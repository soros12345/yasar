"""Merkezi konfigürasyon yönetimi."""
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
import yaml


class Config(BaseSettings):
    """Uygulama konfigürasyonu."""
    
    # Uygulama
    APP_NAME: str = "AlphaFold Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Server
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    UI_HOST: str = "0.0.0.0"
    UI_PORT: int = 8501
    
    # Cache
    CACHE_DIR: Path = Path("./cache")
    CACHE_TTL: int = 86400  # 24 saat
    
    # Provider Config
    PROVIDERS_DIR: Path = Path("./providers")
    ACTIVE_PROVIDERS: list[str] = ["alphafold_db"]
    
    # External APIs
    EBI_API_URL: str = "https://www.ebi.ac.uk/pdbe/api/pdb/entry/summary"
    UNIPROT_API_URL: str = "https://rest.uniprot.org/uniprotkb"
    
    # Analysis
    RMSD_THRESHOLD: float = 2.0
    PLDDT_THRESHOLD: float = 70.0
    POCKET_GRID_SIZE: float = 1.0
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "Config":
        """YAML dosyasından konfigürasyon yükle."""
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        return cls(**data)
    
    def save_yaml(self, yaml_path: Path) -> None:
        """Konfigürasyonu YAML dosyasına kaydet."""
        with open(yaml_path, "w") as f:
            yaml.dump(self.dict(), f, default_flow_style=False)
