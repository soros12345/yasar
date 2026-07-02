"""Provider routes."""
from fastapi import APIRouter, HTTPException
from core.registry import ProviderRegistry
from loguru import logger

router = APIRouter()

@router.get("/list")
async def list_providers():
    """Tüm provider'ları listele."""
    available = ProviderRegistry.list_available()
    instances = ProviderRegistry.get_all()
    
    provider_info = []
    for name in available:
        try:
            provider = instances.get(name)
            provider_info.append({
                "name": name,
                "description": provider.description if provider else "N/A",
                "version": provider.version if provider else "N/A"
            })
        except Exception as e:
            logger.error(f"Provider bilgisi hatası ({name}): {e}")
    
    return {"providers": provider_info, "total": len(provider_info)}

@router.get("/{provider_name}")
async def get_provider(provider_name: str):
    """Belirli provider hakkında bilgi al."""
    try:
        provider = ProviderRegistry.get(provider_name)
        is_valid = await provider.validate()
        
        return {
            "name": provider.name,
            "description": provider.description,
            "version": provider.version,
            "available": is_valid
        }
    except Exception as e:
        logger.error(f"Provider bilgisi hatası: {e}")
        raise HTTPException(status_code=404, detail=f"Provider bulunamadı: {provider_name}")

@router.post("/validate")
async def validate_provider(provider_name: str):
    """Provider'ı doğrula."""
    try:
        provider = ProviderRegistry.get(provider_name)
        is_valid = await provider.validate()
        return {"provider": provider_name, "valid": is_valid}
    except Exception as e:
        logger.error(f"Provider doğrulama hatası: {e}")
        return {"provider": provider_name, "valid": False, "error": str(e)}
