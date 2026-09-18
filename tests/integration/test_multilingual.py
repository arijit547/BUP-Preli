"""Integration tests for multilingual and paraphrase robustness."""

import pytest
from httpx import AsyncClient
from app.core.constants import DirectiveType


@pytest.mark.anyio
async def test_multilingual_bangla_banglish_notes(async_client: AsyncClient, sample_request):
    # Test Bangla and Banglish notes
    notes = [
        "Battery charging বন্ধ থাকবে 2টা থেকে 4টা পর্যন্ত.",
        "The sports office moved next month's registration deadline."
    ]
    payload = sample_request.model_dump()
    payload["operator_notes"] = notes

    response = await async_client.post("/optimize-energy", json=payload)
    assert response.status_code == 200
    data = response.json()

    interps = data["directive_interpretation"]
    assert len(interps) == 2

    # First note: no_charge_window for [14, 15]
    assert interps[0]["directive_type"] == DirectiveType.NO_CHARGE_WINDOW.value
    assert interps[0]["applies"] is True
    assert interps[0]["structured_adjustment"]["hours"] == [14, 15]

    # Second note: distractor -> no_op
    assert interps[1]["directive_type"] == DirectiveType.NO_OP.value
    assert interps[1]["applies"] is False
    assert interps[1]["structured_adjustment"] is None
