"""Pytest test fixtures and configuration."""

import json
import os
import pytest
from httpx import ASGITransport, AsyncClient
from app.core.config import settings
from app.main import app
from app.schemas.request import BatteryConfig, HourEntry, OptimizeEnergyRequest


@pytest.fixture(autouse=True)
def set_test_mode(monkeypatch):
    """Ensure LLM_PROVIDER is set to 'mock' during test execution."""
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mock")


@pytest.fixture
def sample_public_cases() -> list[dict]:
    """Load the 10 official public sample cases."""
    path = os.path.join(os.path.dirname(__file__), "..", "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]


@pytest.fixture
def sample_request() -> OptimizeEnergyRequest:
    """Provide a valid 24-hour test request."""
    hours = [
        HourEntry(hour=h, demand_kwh=100.0, solar_kwh=20.0 if 8 <= h <= 16 else 0.0, tariff_bdt_per_kwh=10.0 if 17 <= h <= 22 else 5.0)
        for h in range(24)
    ]
    battery = BatteryConfig(
        capacity_kwh=200.0,
        initial_energy_kwh=100.0,
        minimum_energy_kwh=40.0,
        max_charge_kwh_per_hour=50.0,
        max_discharge_kwh_per_hour=50.0,
    )
    return OptimizeEnergyRequest(
        scenario_id="TEST-SCENARIO-01",
        operator_notes=["Do not charge the battery between 2 PM and 4 PM."],
        hours=hours,
        battery=battery,
    )


@pytest.fixture
async def async_client():
    """Async HTTP test client bound to FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
