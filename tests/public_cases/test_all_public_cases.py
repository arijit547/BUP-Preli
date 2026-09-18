"""Pytest regression test validating all 10 official public sample cases."""

import pytest
from httpx import AsyncClient
from app.core.constants import JUDGE_TOLERANCE


@pytest.mark.anyio
async def test_all_10_public_sample_cases(async_client: AsyncClient, sample_public_cases: list[dict]):
    """Execute each of the 10 official public sample cases against /optimize-energy."""
    assert len(sample_public_cases) == 10

    for case in sample_public_cases:
        case_id = case["id"]
        label = case["label"]
        inp = case["input"]
        expected_out = case["expected_output"]

        response = await async_client.post("/optimize-energy", json=inp)
        assert response.status_code == 200, f"Case {case_id} ({label}) failed: {response.text}"
        data = response.json()

        # 1. Scenario ID echo
        assert data["scenario_id"] == inp["scenario_id"]

        # 2. Directive interpretation semantic match
        interps = data["directive_interpretation"]
        exp_interps = expected_out["directive_interpretation"]
        assert len(interps) == len(exp_interps), f"Case {case_id} interpretation count mismatch"

        for act, exp in zip(interps, exp_interps):
            assert act["note_index"] == exp["note_index"]
            assert act["applies"] == exp["applies"]
            assert act["directive_type"] == exp["directive_type"]

            if exp["structured_adjustment"] is None:
                assert act["structured_adjustment"] is None
            else:
                assert act["structured_adjustment"] is not None
                assert act["structured_adjustment"]["hours"] == exp["structured_adjustment"]["hours"]

                if "factor" in exp["structured_adjustment"]:
                    assert abs(act["structured_adjustment"]["factor"] - exp["structured_adjustment"]["factor"]) < JUDGE_TOLERANCE
                if "minimum_energy_kwh" in exp["structured_adjustment"]:
                    assert abs(act["structured_adjustment"]["minimum_energy_kwh"] - exp["structured_adjustment"]["minimum_energy_kwh"]) < JUDGE_TOLERANCE
                if "max_grid_kwh" in exp["structured_adjustment"]:
                    assert abs(act["structured_adjustment"]["max_grid_kwh"] - exp["structured_adjustment"]["max_grid_kwh"]) < JUDGE_TOLERANCE

        # 3. Hourly plan completeness
        assert len(data["hourly_plan"]) == 24

        # 4. Optimal cost verification
        expected_cost = expected_out["total_cost_bdt"]
        actual_cost = data["total_cost_bdt"]
        cost_diff = abs(actual_cost - expected_cost)

        # Tolerance: within 0.01 BDT or relative error < 0.05%
        assert cost_diff < max(JUDGE_TOLERANCE, 0.0005 * expected_cost), (
            f"Case {case_id} ({label}) cost mismatch: got {actual_cost}, expected {expected_cost} (diff {cost_diff:.4f})"
        )
