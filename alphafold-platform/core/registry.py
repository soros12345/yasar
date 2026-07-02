"""Plugin kayıt sistemi."""
import importlib
from pathlib import Path
from typing import Dict, Type, Optional
from .interfaces.provider import StructureProvider
from .exceptions import ProviderNotFound
import logging

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Provider registry - otomatik keşif ve kayıt."""
    
    _providers: Dict[str, Type[StructureProvider]] = {}
    _instances: Dict[str, StructureProvider] = {}
    
    @classmethod
    def register(cls, name: str):
        """Dekoratör: Provider'ı kaydet.
        
        Usage:
            @ProviderRegistry.register("my_provider")
            class MyProvider(StructureProvider):
                ...
        """
        def decorator(provider_class: Type[StructureProvider]):
            cls._providers[name] = provider_class
            logger.info(f"Provider kayıt edildi: {name}")
            return provider_class
        return decorator
    
    @classmethod
    def get(cls, name: str) -> StructureProvider:
        """Provider'ı al (instance)."""
        if name not in cls._providers:
            raise ProviderNotFound(f"Provider bulunamadı: {name}")
        
        if name not in cls._instances:
            cls._instances[name] = cls._providers[name]()
        
        return cls._instances[name]
    
    @classmethod
    def get_all(cls) -> Dict[str, StructureProvider]:
        """Tüm provider'ları al."""
        for name, provider_class in cls._providers.items():
            if name not in cls._instances:
                cls._instances[name] = provider_class()
        return cls._instances
    
    @classmethod
    def list_available(cls) -> list[str]:
        """Kullanılabilir provider'ları listele."""
        return list(cls._providers.keys())
    
    @classmethod
    def auto_discover(cls, providers_dir: Path = Path("./providers")) -> None:
        """Provider'ları otomatik keşfet.
        
        Klasör yapısı:
        providers/
          provider_name/
            __init__.py
            provider.py  (ProviderRegistry.register dekoratörü içerir)
        """
        if not providers_dir.exists():
            logger.warning(f"Provider dizini bulunamadı: {providers_dir}")
            return
        
        for provider_path in providers_dir.iterdir():
            if provider_path.is_dir() and not provider_path.name.startswith("_"):
                try:
                    module_name = f"providers.{provider_path.name}.provider"
                    module = importlib.import_module(module_name)
                    logger.info(f"Provider keşfedildi: {provider_path.name}")
                except Exception as e:
                    logger.error(f"Provider keşif hatası ({provider_path.name}): {e}")
