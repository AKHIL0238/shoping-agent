"""
Simple in-process TTL cache for search results.
Avoids repeated SerpAPI calls for the same query within a session.
"""

from __future__ import annotations
import time
import hashlib
import json
from typing import Any, Callable, Optional


class TTLCache:
    def __init__(self, ttl_seconds: int = 300):
        self._store: dict[str, tuple[float, Any]] = {}
        self._ttl = ttl_seconds

    def _key(self, *args, **kwargs) -> str:
        raw = json.dumps({"a": args, "k": kwargs}, sort_keys=True, default=str)
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        if key in self._store:
            ts, val = self._store[key]
            if time.time() - ts < self._ttl:
                return val
            del self._store[key]
        return None

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time(), value)

    def clear(self) -> None:
        self._store.clear()


_search_cache = TTLCache(ttl_seconds=300)


def cached_search(fn: Callable) -> Callable:
    """Decorator — caches the result of a search function for 5 min."""
    def wrapper(*args, **kwargs):
        key = _search_cache._key(*args, **kwargs)
        cached = _search_cache.get(key)
        if cached is not None:
            return cached
        result = fn(*args, **kwargs)
        _search_cache.set(key, result)
        return result
    return wrapper
