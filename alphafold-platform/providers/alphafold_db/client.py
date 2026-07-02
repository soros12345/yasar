"""AlphaFold DB API istemcisi."""
import aiohttp
import asyncio
from typing import Optional, Any
from loguru import logger
from .config import AlphaFoldDBConfig


class AlphaFoldDBClient:
    """AlphaFold DB REST API istemcisi."""
    
    def __init__(self, config: Optional[AlphaFoldDBConfig] = None):
        self.config = config or AlphaFoldDBConfig()
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Protein ara."""
        if not self.session:
            raise RuntimeError("Session açılmadı")
        
        url = f"{self.config.API_URL}/search"
        params = {"q": query, "limit": limit}
        
        async with self.session.get(url, params=params, timeout=self.config.TIMEOUT) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                logger.error(f"API hatası: {resp.status}")
                return []
    
    async def fetch_structure(self, af_id: str) -> Optional[bytes]:
        """Yapı dosyasını indir (PDB format)."""
        if not self.session:
            raise RuntimeError("Session açılmadı")
        
        url = f"{self.config.API_URL}/structures/{af_id}/pdb"
        
        for attempt in range(self.config.MAX_RETRIES):
            try:
                async with self.session.get(url, timeout=self.config.TIMEOUT) as resp:
                    if resp.status == 200:
                        return await resp.read()
                    elif resp.status == 404:
                        logger.warning(f"Yapı bulunamadı: {af_id}")
                        return None
                    else:
                        logger.warning(f"Hata ({attempt+1}/{self.config.MAX_RETRIES}): {resp.status}")
            except asyncio.TimeoutError:
                logger.warning(f"Zaman aşımı ({attempt+1}/{self.config.MAX_RETRIES})")
                if attempt < self.config.MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** attempt)
        
        return None
    
    async def fetch_pae(self, af_id: str) -> Optional[list[list[float]]]:
        """PAE (Predicted Aligned Error) al."""
        if not self.session:
            raise RuntimeError("Session açılmadı")
        
        url = f"{self.config.API_URL}/structures/{af_id}/pae"
        
        async with self.session.get(url, timeout=self.config.TIMEOUT) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("pae_matrix")
            return None
