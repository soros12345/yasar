"""AlphaFold DB Provider konfigürasyonu."""
from pydantic import BaseSettings


class AlphaFoldDBConfig(BaseSettings):
    """AlphaFold DB API konfigürasyonu."""
    
    API_URL: str = "https://alphafolddb.csb.pitt.edu/api/v1"
    TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    
    class Config:
        env_prefix = "ALPHAFOLD_DB_"
        env_file = ".env"
