"""Standalone script to run and evaluate all 10 official public sample cases."""

import json
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx
from app.core.constants import JUDGE_TOLERANCE
from app.validation.replay import replay_and_validate_schedule
from app.directives.compiler import compile_directives
from app.schemas.request import OptimizeEnergyRequest
from app.schemas.response import OptimizeEnergyResponse


def run_cases(base_url: str = "http://localhost:8000") -> bool:
    cases_file = PROJECT_ROOT / "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"
    if not cases_file.exists():
        print(f"Error: {cases_file} not found.")
        return False

    with open(cases_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    cases = data["cases"]
    print(f"\nEvaluating {len(cases)} Public Sample Cases against {base_url}...\n")
    print(f"{'Case ID':<12} | {'Status':<8} | {'Cost (BDT)':<12} | {'Expected (BDT)':<14} | {'Diff':<8} | {'Latency (ms)':<12}")
    print("-" * 78)

    all_passed = True
    total_latency = 0.0

    client = httpx.Client(base_url=base_url, timeout=30.0)

    # First verify /health
    try:
        health_res = client.get("/health")
        if health_res.status_code != 200 or health_res.json().get("status") != "ok":
            print(f"FAILED: /health returned {health_res.status_code}: {health_res.text}")
            return False
    except Exception as e:
        print(f"FAILED to connect to /health: {e}")
        return False

    for case in cases:
        case_id = case["id"]
        inp = case["input"]
        exp = case["expected_output"]
        expected_cost = exp["total_cost_bdt"]

        t0 = time.perf_counter()
        try:
            res = client.post("/optimize-energy", json=inp)
            duration_ms = (time.perf_counter() - t0) * 1000.0
            total_latency += duration_ms

            if res.status_code != 200:
                print(f"{case_id:<12} | FAILED   | HTTP {res.status_code} | {expected_cost:<14.2f} | N/A      | {duration_ms:<12.1f}")
                print(f"   Detail: {res.text}")
                all_passed = False
                continue

            resp_json = res.json()
            resp_obj = OptimizeEnergyResponse.model_validate(resp_json)
            req_obj = OptimizeEnergyRequest.model_validate(inp)

            # Independent Replay Verification
            compiled = compile_directives(req_obj, resp_obj.directive_interpretation)
            replay_and_validate_schedule(req_obj, compiled, resp_obj.hourly_plan)

            actual_cost = resp_obj.total_cost_bdt
            cost_diff = abs(actual_cost - expected_cost)

            # Check directive interpretations
            interp_match = True
            for act_d, exp_d in zip(resp_obj.directive_interpretation, exp["directive_interpretation"]):
                if act_d.directive_type.value != exp_d["directive_type"] or act_d.applies != exp_d["applies"]:
                    interp_match = False
                    break

            is_optimal = cost_diff < max(JUDGE_TOLERANCE, 0.0005 * expected_cost)

            if interp_match and is_optimal:
                status_str = "PASSED"
            else:
                status_str = "MISMATCH"
                all_passed = False

            print(f"{case_id:<12} | {status_str:<8} | {actual_cost:<12.2f} | {expected_cost:<14.2f} | {cost_diff:<8.2f} | {duration_ms:<12.1f}")

        except Exception as e:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            print(f"{case_id:<12} | ERROR    | N/A          | {expected_cost:<14.2f} | N/A      | {duration_ms:<12.1f}")
            print(f"   Exception: {e}")
            all_passed = False

    avg_ms = total_latency / len(cases)
    print("-" * 78)
    print(f"Summary: {'ALL PASSED' if all_passed else 'SOME FAILED'} | Average Latency: {avg_ms:.1f} ms\n")
    return all_passed


if __name__ == "__main__":
    target_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    success = run_cases(target_url)
    sys.exit(0 if success else 1)
