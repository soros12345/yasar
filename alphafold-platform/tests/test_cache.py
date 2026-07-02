"""Cache testleri."""
import pytest
from pathlib import Path
from core.interfaces.cache import DiskCache
import tempfile

@pytest.fixture
def temp_cache_dir():
    """Geçici cache dizini."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.mark.asyncio
async def test_disk_cache_set_get(temp_cache_dir):
    """Disk cache'e yazma ve okuma."""
    cache = DiskCache(temp_cache_dir)
    
    test_key = "test_key"
    test_value = {"name": "test", "value": 123}
    
    # Yazma
    await cache.set(test_key, test_value)
    
    # Okuma
    result = await cache.get(test_key)
    assert result == test_value

@pytest.mark.asyncio
async def test_disk_cache_delete(temp_cache_dir):
    """Disk cache'den silme."""
    cache = DiskCache(temp_cache_dir)
    
    test_key = "test_key"
    test_value = {"data": "test"}
    
    # Yazma
    await cache.set(test_key, test_value)
    assert await cache.exists(test_key)
    
    # Silme
    await cache.delete(test_key)
    assert not await cache.exists(test_key)
    assert await cache.get(test_key) is None

@pytest.mark.asyncio
async def test_disk_cache_clear(temp_cache_dir):
    """Disk cache'i temizle."""
    cache = DiskCache(temp_cache_dir)
    
    # Birden fazla değer yazma
    for i in range(5):
        await cache.set(f"key_{i}", {"value": i})
    
    # Temizle
    await cache.clear()
    
    # Kontrol
    for i in range(5):
        assert not await cache.exists(f"key_{i}")

@pytest.mark.asyncio
async def test_disk_cache_nonexistent_key(temp_cache_dir):
    """Var olmayan anahtarı al."""
    cache = DiskCache(temp_cache_dir)
    
    result = await cache.get("nonexistent_key")
    assert result is None
