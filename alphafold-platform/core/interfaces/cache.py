"""Cache arayüzü."""
from abc import ABC, abstractmethod
from typing import Optional, Any
import pickle
from pathlib import Path


class CacheBackend(ABC):
    """Cache arka ucu soyut sınıfı."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Değer al."""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Değer ayarla."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> None:
        """Değer sil."""
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        """Tümünü temizle."""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Anahtar var mı?"""
        pass


class DiskCache(CacheBackend):
    """Disk tabanlı cache."""
    
    def __init__(self, cache_dir: Path = Path("./cache"), ttl: int = 86400):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        self.metadata_file = self.cache_dir / "metadata.pkl"
        self._load_metadata()
    
    def _load_metadata(self) -> None:
        """Metaveri yükle."""
        if self.metadata_file.exists():
            with open(self.metadata_file, "rb") as f:
                self.metadata = pickle.load(f)
        else:
            self.metadata = {}
    
    def _save_metadata(self) -> None:
        """Metaveri kaydet."""
        with open(self.metadata_file, "wb") as f:
            pickle.dump(self.metadata, f)
    
    async def get(self, key: str) -> Optional[Any]:
        cache_file = self.cache_dir / f"{key}.pkl"
        if cache_file.exists():
            with open(cache_file, "rb") as f:
                return pickle.load(f)
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        cache_file = self.cache_dir / f"{key}.pkl"
        with open(cache_file, "wb") as f:
            pickle.dump(value, f)
    
    async def delete(self, key: str) -> None:
        cache_file = self.cache_dir / f"{key}.pkl"
        if cache_file.exists():
            cache_file.unlink()
    
    async def clear(self) -> None:
        for f in self.cache_dir.glob("*.pkl"):
            f.unlink()
    
    async def exists(self, key: str) -> bool:
        cache_file = self.cache_dir / f"{key}.pkl"
        return cache_file.exists()
