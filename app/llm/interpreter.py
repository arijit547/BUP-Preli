"""LLM Interpreter service coordinating provider execution, caching, and retries."""

import time
from typing import Optional
from app.core.config import settings
from app.core.logging import logger
from app.llm.cache import cache
from app.llm.provider import LLMProvider, get_llm_provider
from app.schemas.directives import DirectiveInterpretation


class LLMInterpreter:
    """Interprets 1-3 operator notes using the configured generative model."""

    def __init__(self, provider: Optional[LLMProvider] = None):
        self.provider = provider or get_llm_provider()

    async def interpret_notes(
        self, notes: list[str], battery_capacity_kwh: float
    ) -> tuple[list[DirectiveInterpretation], float]:
        """Interpret operator notes into structured directives.

        Returns:
            tuple of (list of DirectiveInterpretation, latency_ms)
        """
        start_time = time.perf_counter()

        # Check cache first
        cache_key = cache.compute_key(
            model=getattr(self.provider, "model", settings.LLM_MODEL),
            notes=notes,
            battery_capacity_kwh=battery_capacity_kwh,
        )
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            logger.info("Cache hit for operator notes interpretation", extra={"cache_key": cache_key, "latency_ms": elapsed_ms})
            return cached_result, elapsed_ms

        # Execute provider call with bounded retry
        last_err: Optional[Exception] = None
        for attempt in range(1, settings.LLM_MAX_RETRIES + 1):
            try:
                directives = await self.provider.interpret(notes, battery_capacity_kwh)
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0

                # Cache successful response
                cache.set(cache_key, directives)

                logger.info(
                    "LLM note interpretation completed",
                    extra={"attempt": attempt, "latency_ms": elapsed_ms, "directive_count": len(directives)},
                )
                return directives, elapsed_ms
            except Exception as e:
                last_err = e
                logger.warning(
                    f"LLM note interpretation attempt {attempt} failed: {type(e).__name__}: {str(e)}",
                    extra={"attempt": attempt},
                )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        logger.error(
            "All LLM note interpretation attempts exhausted",
            extra={"latency_ms": elapsed_ms, "last_error": str(last_err)},
        )
        raise RuntimeError(f"LLM interpretation failed: {str(last_err)}") from last_err
