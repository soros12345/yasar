"""Provider registry testleri."""
import pytest
from core.registry import ProviderRegistry
from core.interfaces.provider import StructureProvider
from core.exceptions import ProviderNotFound

class MockProvider(StructureProvider):
    """Mock provider."""
    name = "mock"
    description = "Mock Provider"
    version = "1.0.0"
    
    async def search(self, query, limit=10):
        return [{"id": "TEST-001", "name": "Test Protein"}]
    
    async def fetch(self, structure_id):
        pass
    
    async def validate(self):
        return True

@pytest.fixture(autouse=True)
def clear_registry():
    """Her test öncesinde registry'i temizle."""
    ProviderRegistry._providers.clear()
    ProviderRegistry._instances.clear()
    yield
    ProviderRegistry._providers.clear()
    ProviderRegistry._instances.clear()

def test_register_provider():
    """Provider'ı kaydet."""
    ProviderRegistry.register("mock")(MockProvider)
    assert "mock" in ProviderRegistry.list_available()

def test_get_provider():
    """Provider'ı al."""
    ProviderRegistry.register("mock")(MockProvider)
    provider = ProviderRegistry.get("mock")
    assert provider.name == "mock"

def test_provider_not_found():
    """Provider bulunamadığında hata."""
    with pytest.raises(ProviderNotFound):
        ProviderRegistry.get("nonexistent")

def test_list_providers():
    """Provider'ları listele."""
    ProviderRegistry.register("mock1")(MockProvider)
    ProviderRegistry.register("mock2")(MockProvider)
    
    available = ProviderRegistry.list_available()
    assert len(available) == 2
    assert "mock1" in available
    assert "mock2" in available
