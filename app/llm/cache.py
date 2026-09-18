"""In-memory thread-safe LRU + SQLite persistent cache for LLM directive interpretations."""

import hashlib
import json
import sqlite3
import time
from collections import OrderedDict
from pathlib import Path
from threading import Lock
from typing import Optional
from app.core.constants import PROMPT_VERSION, SCHEMA_VERSION
from app.schemas.directives import DirectiveInterpretation, DirectiveInterpretationBatch


class InterpretationCache:
    """Thread-safe LRU cache with time-to-live and SQLite persistence for interpreted directives."""

    def __init__(self, max_size: int = 4096, ttl_sec: int = 86400 * 7, db_path: Optional[str] = None):
        self.max_size = max_size
        self.ttl_sec = ttl_sec
        self._cache: OrderedDict[str, tuple[float, list[DirectiveInterpretation]]] = OrderedDict()
        self._lock = Lock()
        if db_path is None:
            cache_dir = Path(__file__).resolve().parent.parent.parent / ".cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(cache_dir / "llm_interpretations.db")
        else:
            self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        try:
            with self._lock, sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS interpretations (
                        cache_key TEXT PRIMARY KEY,
                        timestamp REAL,
                        data_json TEXT
                    )
                    """
                )
                conn.commit()
        except Exception:
            pass

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
            # 1. Check in-memory LRU
            if key in self._cache:
                timestamp, data = self._cache[key]
                if time.time() - timestamp <= self.ttl_sec:
                    self._cache.move_to_end(key)
                    return [d.model_copy(deep=True) for d in data]
                else:
                    del self._cache[key]

            # 2. Check SQLite persistent cache
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT timestamp, data_json FROM interpretations WHERE cache_key = ?", (key,))
                    row = cursor.fetchone()
                    if row:
                        timestamp, data_json = row
                        if time.time() - timestamp <= self.ttl_sec:
                            raw_list = json.loads(data_json)
                            batch = DirectiveInterpretationBatch.model_validate({"directive_interpretation": raw_list})
                            data = batch.directive_interpretation
                            # Hydrate into in-memory LRU
                            if len(self._cache) >= self.max_size:
                                self._cache.popitem(last=False)
                            self._cache[key] = (timestamp, [d.model_copy(deep=True) for d in data])
                            return [d.model_copy(deep=True) for d in data]
            except Exception:
                pass

            return None

    def set(self, key: str, data: list[DirectiveInterpretation]) -> None:
        """Store interpretation in LRU and persistent SQLite cache."""
        with self._lock:
            now = time.time()
            if key in self._cache:
                self._cache[key] = (now, [d.model_copy(deep=True) for d in data])
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self.max_size:
                    self._cache.popitem(last=False)
                self._cache[key] = (now, [d.model_copy(deep=True) for d in data])

            # Persist to SQLite
            try:
                data_json = json.dumps([d.model_dump(mode="json") for d in data])
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO interpretations (cache_key, timestamp, data_json) VALUES (?, ?, ?)",
                        (key, now, data_json),
                    )
                    conn.commit()
            except Exception:
                pass

    def clear(self) -> None:
        """Flush the cache."""
        with self._lock:
            self._cache.clear()
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("DELETE FROM interpretations")
                    conn.commit()
            except Exception:
                pass


# Global cache instance
cache = InterpretationCache()
