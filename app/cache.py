"""
In-memory LRU cache for comparison results.

Caches results based on SHA256 hash of combined image bytes
to avoid redundant API calls for identical image pairs.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from collections import OrderedDict
from typing import Any, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


class ComparisonCache:
    """Thread-safe LRU cache for comparison results."""

    def __init__(self, max_size: Optional[int] = None):
        settings = get_settings()
        self._max_size = max_size or settings.cache_max_size
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def _hash_images(self, figma: bytes, web: bytes) -> str:
        """Generate a unique cache key from image bytes."""
        hasher = hashlib.sha256()
        hasher.update(figma)
        hasher.update(b"||")
        hasher.update(web)
        return hasher.hexdigest()

    def get(self, figma: bytes, web: bytes) -> Optional[dict[str, Any]]:
        """
        Retrieve cached result for image pair.
        
        Returns None if not cached. Moves accessed item to end (LRU).
        """
        key = self._hash_images(figma, web)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._hits += 1
                logger.info("Cache hit (key=%s..., hits=%d)", key[:8], self._hits)
                return self._cache[key]
            self._misses += 1
            return None

    def set(self, figma: bytes, web: bytes, result: dict[str, Any]) -> None:
        """
        Store result in cache.
        
        Evicts oldest item if cache is full.
        """
        key = self._hash_images(figma, web)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = result
                return
            
            if len(self._cache) >= self._max_size:
                evicted_key, _ = self._cache.popitem(last=False)
                logger.debug("Cache evicted key=%s...", evicted_key[:8])
            
            self._cache[key] = result
            logger.info("Cache stored (key=%s..., size=%d)", key[:8], len(self._cache))

    def clear(self) -> None:
        """Clear all cached items."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            logger.info("Cache cleared")

    def stats(self) -> dict[str, int]:
        """Return cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_percent": round(hit_rate, 1),
            }


_cache_instance: Optional[ComparisonCache] = None


def get_cache() -> ComparisonCache:
    """Get or create the singleton cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = ComparisonCache()
    return _cache_instance
