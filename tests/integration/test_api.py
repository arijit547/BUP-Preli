"""Integration tests for FastAPI HTTP endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_health_endpoint(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_optimize_energy_endpoint_success(async_client: AsyncClient, sample_request):
    payload = sample_request.model_dump()
    response = await async_client.post("/optimize-energy", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["scenario_id"] == sample_request.scenario_id
    assert len(data["directive_interpretation"]) == len(sample_request.operator_notes)
    assert len(data["hourly_plan"]) == 24
    assert data["total_grid_kwh"] >= 0.0
    assert data["total_cost_bdt"] >= 0.0
    assert data["peak_grid_kwh"] >= 0.0
    assert isinstance(data["plan_summary"], str) and len(data["plan_summary"]) > 0


@pytest.mark.anyio
async def test_optimize_energy_malformed_json_400(async_client: AsyncClient):
    # Missing hours and battery
    invalid_payload = {
        "scenario_id": "ERR-1",
        "operator_notes": ["Test note"],
    }
    response = await async_client.post("/optimize-energy", json=invalid_payload)
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "errors" in data
    # Ensure no internal stack trace leaked
    assert "Traceback" not in response.text
