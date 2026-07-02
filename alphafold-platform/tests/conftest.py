"""pytest yapılandırması."""
import pytest
import asyncio
import sys
from pathlib import Path

# Path ayarı
sys.path.insert(0, str(Path(__file__).parent.parent))

@pytest.fixture(scope="session")
def event_loop():
    """Event loop fixture."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# pytest-asyncio için otomatik mode
pytest_plugins = ("pytest_asyncio",)
