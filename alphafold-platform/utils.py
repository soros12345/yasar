"""Utility fonksiyonları."""
import asyncio
from typing import Any, Callable, TypeVar, Coroutine
from functools import wraps
from loguru import logger
import time

T = TypeVar('T')

def async_timer(func: Callable) -> Callable:
    """Async fonksiyonun çalışma süresini ölç."""
    @wraps(func)
    async def wrapper(*args, **kwargs) -> T:
        start = time.time()
        logger.info(f"[başladı] {func.__name__}")
        try:
            result = await func(*args, **kwargs)
            elapsed = time.time() - start
            logger.info(f"[tamamlandı] {func.__name__} ({elapsed:.2f}s)")
            return result
        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"[hata] {func.__name__} ({elapsed:.2f}s): {e}")
            raise
    return wrapper

def sync_timer(func: Callable) -> Callable:
    """Sync fonksiyonun çalışma süresini ölç."""
    @wraps(func)
    def wrapper(*args, **kwargs) -> T:
        start = time.time()
        logger.info(f"[başladı] {func.__name__}")
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            logger.info(f"[tamamlandı] {func.__name__} ({elapsed:.2f}s)")
            return result
        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"[hata] {func.__name__} ({elapsed:.2f}s): {e}")
            raise
    return wrapper

def retry(max_attempts: int = 3, delay: float = 1.0):
    """Fonksiyonu yeniden dene (exponential backoff)."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts:
                        logger.error(f"[başarısız] {func.__name__} ({attempt}/{max_attempts} deneme)")
                        raise
                    
                    wait_time = delay * (2 ** (attempt - 1))
                    logger.warning(f"[yeniden dene] {func.__name__} ({attempt}/{max_attempts}) - {wait_time:.1f}s bekleniyor")
                    await asyncio.sleep(wait_time)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts:
                        logger.error(f"[başarısız] {func.__name__} ({attempt}/{max_attempts} deneme)")
                        raise
                    
                    wait_time = delay * (2 ** (attempt - 1))
                    logger.warning(f"[yeniden dene] {func.__name__} ({attempt}/{max_attempts}) - {wait_time:.1f}s bekleniyor")
                    time.sleep(wait_time)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
