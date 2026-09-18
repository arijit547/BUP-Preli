"""LLM provider abstraction and provider implementations."""

import json
import re
from typing import Protocol, runtime_checkable
import httpx
from app.core.config import settings
from app.core.logging import logger
from app.core.constants import DirectiveType
from app.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from app.schemas.directives import (
    DirectiveInterpretation,
    DirectiveInterpretationBatch,
    SolarReductionAdjustment,
    ReserveAdjustment,
    NoChargeAdjustment,
    NoDischargeAdjustment,
    MaxGridAdjustment,
)


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol defining the interface for operator note interpretation."""

    async def interpret(
        self, notes: list[str], battery_capacity_kwh: float
    ) -> list[DirectiveInterpretation]:
        """Interpret a batch of operator notes into structured directives."""
        ...


class OpenAICompatibleProvider:
    """Async provider for OpenAI, Groq, DeepSeek, Together, vLLM, and compatible APIs."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "gpt-4o-mini",
        base_url: str = "",
        timeout_sec: float = 15.0,
    ):
        self.api_key = api_key or settings.LLM_API_KEY
        self.model = model or settings.LLM_MODEL
        self.base_url = (base_url or settings.LLM_BASE_URL or "https://api.openai.com/v1").rstrip("/")
        self.timeout_sec = timeout_sec or settings.LLM_TIMEOUT_SEC

    async def interpret(
        self, notes: list[str], battery_capacity_kwh: float
    ) -> list[DirectiveInterpretation]:
        if not self.api_key:
            raise ValueError(
                "LLM_API_KEY is not configured for OpenAICompatibleProvider. "
                "Set LLM_API_KEY in environment or .env."
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        user_prompt = build_user_prompt(notes, battery_capacity_kwh)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }

        url = f"{self.base_url}/chat/completions"
        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        raw_json = json.loads(content)

        if "directive_interpretation" in raw_json:
            batch = DirectiveInterpretationBatch.model_validate(raw_json)
        elif isinstance(raw_json, list):
            batch = DirectiveInterpretationBatch.model_validate({"directive_interpretation": raw_json})
        else:
            raise ValueError(f"Unexpected JSON structure from LLM: {list(raw_json.keys())}")

        return batch.directive_interpretation


class GeminiProvider:
    """Async provider for Google Gemini models via Google GenAI REST API."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "gemini-2.0-flash",
        timeout_sec: float = 15.0,
    ):
        self.api_key = api_key or settings.LLM_API_KEY
        self.model = model or settings.LLM_MODEL
        self.timeout_sec = timeout_sec or settings.LLM_TIMEOUT_SEC

    async def interpret(
        self, notes: list[str], battery_capacity_kwh: float
    ) -> list[DirectiveInterpretation]:
        if not self.api_key:
            raise ValueError(
                "LLM_API_KEY is not configured for GeminiProvider. "
                "Set LLM_API_KEY in environment or .env."
            )

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )
        user_prompt = build_user_prompt(notes, battery_capacity_kwh)

        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "response_mime_type": "application/json",
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        text_content = data["candidates"][0]["content"]["parts"][0]["text"]
        raw_json = json.loads(text_content)

        if "directive_interpretation" in raw_json:
            batch = DirectiveInterpretationBatch.model_validate(raw_json)
        elif isinstance(raw_json, list):
            batch = DirectiveInterpretationBatch.model_validate({"directive_interpretation": raw_json})
        else:
            raise ValueError(f"Unexpected Gemini response structure: {list(raw_json.keys())}")

        return batch.directive_interpretation


class OllamaProvider:
    """Async provider for local Ollama instances."""

    def __init__(
        self,
        model: str = "llama3",
        base_url: str = "http://localhost:11434",
        timeout_sec: float = 30.0,
    ):
        self.model = model or settings.LLM_MODEL
        self.base_url = (base_url or settings.LLM_BASE_URL or "http://localhost:11434").rstrip("/")
        self.timeout_sec = timeout_sec or settings.LLM_TIMEOUT_SEC

    async def interpret(
        self, notes: list[str], battery_capacity_kwh: float
    ) -> list[DirectiveInterpretation]:
        url = f"{self.base_url}/api/chat"
        user_prompt = build_user_prompt(notes, battery_capacity_kwh)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0},
        }

        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        content = data["message"]["content"]
        raw_json = json.loads(content)
        if "directive_interpretation" in raw_json:
            batch = DirectiveInterpretationBatch.model_validate(raw_json)
        else:
            batch = DirectiveInterpretationBatch.model_validate({"directive_interpretation": raw_json})
        return batch.directive_interpretation


class MockProvider:
    """TEST-ONLY mock provider used exclusively for offline automated testing.

    WARNING: This provider must NEVER be used for production judging.
    It exists strictly to enable deterministic unit tests and CI runs
    without requiring live LLM network calls or API keys.
    """

    def __init__(self):
        logger.warning("MockProvider initialized. STRICTLY FOR UNIT TESTING ONLY.")

    async def interpret(
        self, notes: list[str], battery_capacity_kwh: float
    ) -> list[DirectiveInterpretation]:
        results: list[DirectiveInterpretation] = []

        for idx, note in enumerate(notes):
            n = note.lower()

            # Anti-prompt-injection check: if attack attempting to manipulate prompt / steal keys
            has_injection = any(
                inj in n
                for inj in [
                    "ignore",
                    "previous instruction",
                    "secret",
                    "api key",
                    "api_key",
                    "system prompt",
                    "bypass",
                    "disable all battery limits",
                ]
            )

            # Check if note contains a legitimate operational energy directive with a time window
            has_time_window = any(
                tw in n
                for tw in [
                    "am",
                    "pm",
                    "noon",
                    "24:",
                    "13:00",
                    "15:00",
                    "ta",
                    "টা",
                    "থেকে",
                    "porjonto",
                    "পর্যন্ত",
                ]
            )

            if has_injection and not (has_time_window and ("charger" in n or "solar" in n or "battery" in n or "grid" in n)):
                results.append(
                    DirectiveInterpretation(
                        note_index=idx,
                        applies=False,
                        directive_type=DirectiveType.NO_OP,
                        structured_adjustment=None,
                        explanation="Adversarial instruction ignored as untrusted data; mapped to no_op.",
                    )
                )
                continue

            # Check for distractor / unrelated note
            if any(
                distractor in n
                for distractor in [
                    "sports office",
                    "registration deadline",
                    "cafeteria",
                    "menu",
                    "book-return",
                    "library",
                    "club notices",
                    "seminar room",
                    "student affairs",
                ]
            ) and not any(k in n for k in ["solar", "battery", "grid", "charger", "reserve"]):
                results.append(
                    DirectiveInterpretation(
                        note_index=idx,
                        applies=False,
                        directive_type=DirectiveType.NO_OP,
                        structured_adjustment=None,
                        explanation="Unrelated operational note that does not affect today's energy schedule.",
                    )
                )
                continue

            # 1. Solar reduction
            if "solar" in n or "panel" in n or "pv" in n:
                hours = [12, 13]
                factor = 0.25
                if "11 am and 2 pm" in n or ("11 am" in n and "2 pm" in n):
                    hours = [11, 12, 13]
                    factor = 0.2
                elif "10 am" in n and "noon" in n:
                    hours = [10, 11]
                    factor = 0.5
                elif "1 pm" in n and "3 pm" in n:
                    hours = [13, 14]
                    factor = 0.2
                elif "13:00" in n and "15:00" in n:
                    hours = [13, 14]
                    factor = 0.2
                elif "noon" in n and "2 pm" in n:
                    hours = [12, 13]
                    factor = 0.25

                results.append(
                    DirectiveInterpretation(
                        note_index=idx,
                        applies=True,
                        directive_type=DirectiveType.SOLAR_REDUCTION,
                        structured_adjustment=SolarReductionAdjustment(hours=hours, factor=factor),
                        explanation="Solar availability reduced during panel maintenance.",
                    )
                )

            # 2. No discharge window (IMPORTANT: check discharge BEFORE charge because 'charge' is a substring of 'discharge'!)
            elif ("discharge" in n or "discharging" in n) and (
                "not" in n
                or "disabled" in n
                or "isolated" in n
                or "relay" in n
                or "protection" in n
                or "bondho" in n
                or "jabe na" in n
                or "বন্ধ" in n
            ):
                hours = [18, 19]
                if "5 pm" in n and "7 pm" in n:
                    hours = [17, 18]
                elif "6 pm" in n and "8 pm" in n:
                    hours = [18, 19]

                results.append(
                    DirectiveInterpretation(
                        note_index=idx,
                        applies=True,
                        directive_type=DirectiveType.NO_DISCHARGE_WINDOW,
                        structured_adjustment=NoDischargeAdjustment(hours=hours),
                        explanation="Battery discharging restricted during protection testing.",
                    )
                )

            # 3. No charge window (now safe: only matches if not discharging)
            elif (
                re.search(r"\bcharge\b|\bcharging\b|\bcharger\b", n)
                or "চার্জ" in n
            ) and (
                "not" in n
                or "isolated" in n
                or "disabled" in n
                or "unavailable" in n
                or "bondho" in n
                or "jabe na" in n
                or "বন্ধ" in n
            ):
                hours = [14, 15]
                if "2 am" in n and "5 am" in n:
                    hours = [2, 3, 4]
                elif "11 am" in n and "1 pm" in n:
                    hours = [11, 12]
                elif (
                    ("2 pm" in n and "4 pm" in n)
                    or "2ta theke 4ta" in n
                    or "২টা থেকে ৪টা" in n
                    or ("2টা" in n and "4টা" in n)
                ):
                    hours = [14, 15]

                results.append(
                    DirectiveInterpretation(
                        note_index=idx,
                        applies=True,
                        directive_type=DirectiveType.NO_CHARGE_WINDOW,
                        structured_adjustment=NoChargeAdjustment(hours=hours),
                        explanation="Battery charging restricted during maintenance window.",
                    )
                )

            # 4. Minimum battery reserve
            elif (
                "reserve" in n
                or "stored" in n
                or "remain in the battery" in n
                or "keep at least" in n
                or "রিসার্ভ" in n
            ):
                hours = [18, 19, 20]
                reserve = 100.0
                if "50%" in n:
                    hours = [18, 19, 20]
                    reserve = battery_capacity_kwh * 0.50
                elif "90 kwh" in n or ("90" in n and "kwh" in n):
                    hours = [18, 19, 20, 21]
                    reserve = 90.0
                elif "80 kwh" in n or ("80" in n and "kwh" in n):
                    hours = [18, 19, 20, 21]
                    reserve = 80.0
                elif "120 kwh" in n or ("120" in n and "kwh" in n):
                    hours = [18, 19, 20]
                    reserve = 120.0

                results.append(
                    DirectiveInterpretation(
                        note_index=idx,
                        applies=True,
                        directive_type=DirectiveType.MINIMUM_BATTERY_RESERVE,
                        structured_adjustment=ReserveAdjustment(hours=hours, minimum_energy_kwh=reserve),
                        explanation="Emergency battery reserve requirement enforced.",
                    )
                )

            # 5. Max grid window
            elif "grid" in n or "feeder" in n or "transformer" in n or "substation" in n:
                hours = [18, 19, 20]
                cap = 155.0
                if "155" in n:
                    hours = [18, 19, 20]
                    cap = 155.0
                elif "180" in n:
                    hours = [19, 20]
                    cap = 180.0
                elif "190" in n:
                    hours = [19, 20, 21]
                    cap = 190.0

                results.append(
                    DirectiveInterpretation(
                        note_index=idx,
                        applies=True,
                        directive_type=DirectiveType.MAX_GRID_WINDOW,
                        structured_adjustment=MaxGridAdjustment(hours=hours, max_grid_kwh=cap),
                        explanation="Grid import capacity capped during peak substation restriction.",
                    )
                )
            else:
                results.append(
                    DirectiveInterpretation(
                        note_index=idx,
                        applies=False,
                        directive_type=DirectiveType.NO_OP,
                        structured_adjustment=None,
                        explanation="Note contains no actionable 24-hour campus energy directive.",
                    )
                )

        return results


def get_llm_provider() -> LLMProvider:
    """Factory function returning the configured LLM provider instance."""
    provider_name = settings.LLM_PROVIDER.lower().strip()
    if provider_name == "openai":
        return OpenAICompatibleProvider()
    elif provider_name == "gemini":
        return GeminiProvider()
    elif provider_name == "ollama":
        return OllamaProvider()
    elif provider_name == "mock":
        return MockProvider()
    else:
        raise ValueError(
            f"Unsupported LLM_PROVIDER '{provider_name}'. "
            f"Allowed values: 'openai', 'gemini', 'ollama', 'mock'."
        )
