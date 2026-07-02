"""Özel istisna sınıfları."""


class AlphaFoldPlatformException(Exception):
    """Temel istisna sınıfı."""
    pass


class ProviderException(AlphaFoldPlatformException):
    """Provider ile ilgili hata."""
    pass


class ProviderNotFound(ProviderException):
    """Provider bulunamadı."""
    pass


class InvalidStructure(AlphaFoldPlatformException):
    """Geçersiz yapı."""
    pass


class AnalysisError(AlphaFoldPlatformException):
    """Analiz sırasında hata."""
    pass


class CacheError(AlphaFoldPlatformException):
    """Cache işlemi sırasında hata."""
    pass


class ConfigError(AlphaFoldPlatformException):
    """Konfigürasyon hatası."""
    pass
