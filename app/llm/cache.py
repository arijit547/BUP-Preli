"""In-memory thread-safe LRU + TTL cache for LLM directive interpretations."""

import hashlib
import time
from collections import OrderedDict
from threading import Lock
from typing import Optional
from app.core.constants import PROMPT_VERSION, SCHEMA_VERSION
from app.schemas.directives import DirectiveInterpretation


class InterpretationCache:
    """Thread-safe LRU cache with time-to-live for interpreted directives."""

    def __init__(self, max_size: int = 256, ttl_sec: int = 1800):
        self.max_size = max_size
        self.ttl_sec = ttl_sec
        self._cache: OrderedDict[str, tuple[float, list[DirectiveInterpretation]]] = OrderedDict()
        self._lock = Lock()

    @staticmethod
    def compute_key(
        model: str,
        notes: list[str],
        battery_capacity_kwh: float,
        prompt_version: str = PROMPT_VERSION,
        schema_version: str = SCHEMA_VERSION,
    ) -> str:
        """Construct deterministic cache key from model, prompt, schema, notes, and capacity."""
        normalized_notes = "||".join(note.strip().lower() for note in notes)
        raw_key = (
            f"model:{model}|pv:{prompt_version}|sv:{schema_version}|"
            f"cap:{round(battery_capacity_kwh, 4)}|notes:{normalized_notes}"
        )
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[list[DirectiveInterpretation]]:
        """Retrieve cached interpretation if present and unexpired."""
        with self._lock:
            if key not in self._cache:
                return None
            timestamp, data = self._cache[key]
            if time.time() - timestamp > self.ttl_sec:
                del self._cache[key]
                return None
            # Move to end (MRU)
            self._cache.move_to_end(key)
            return [d.model_copy(deep=True) for d in data]

    def set(self, key: str, data: list[DirectiveInterpretation]) -> None:
        """Store interpretation in LRU cache."""
        with self._lock:
            now = time.time()
            if key in self._cache:
                self._cache[key] = (now, [d.model_copy(deep=True) for d in data])
                self._cache.move_to_end(key)
                return

            if len(self._cache) >= self.max_size:
                # Evict oldest entry (LRU)
                self._cache.popitem(last=False)

            self._cache[key] = (now, [d.model_copy(deep=True) for d in data])

    def clear(self) -> None:
        """Flush the cache."""
        with self._lock:
            self._cache.clear()


# Global cache instance
cache = InterpretationCache()
