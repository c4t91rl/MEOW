import time
import hashlib
from typing import Any, Optional
from config import get_settings


class SimpleCache:
    """
    In-memory TTL cache.
    Na hackathon wystarczy. Na prod użyjcie Redis.
    """

    def __init__(self):
        self._store: dict[str, tuple[float, Any]] = {}

    def _make_key(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()

    def get(self, url: str) -> Optional[Any]:
        key = self._make_key(url)
        if key not in self._store:
            return None
        timestamp, data = self._store[key]
        ttl = get_settings().cache_ttl_seconds
        if time.time() - timestamp > ttl:
            del self._store[key]
            return None
        return data

    def set(self, url: str, data: Any):
        key = self._make_key(url)
        self._store[key] = (time.time(), data)

    def clear(self):
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)


cache = SimpleCache()