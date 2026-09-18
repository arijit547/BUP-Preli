"""Detailed verification script for Render deployed endpoint."""

import json
import os
import sys
import time
from pathlib import Path
import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.constants import JUDGE_TOLERANCE
from app.directives.compiler import compile_directives
from app.schemas.request import OptimizeEnergyRequest
from app.schemas.response import OptimizeEnergyResponse
from app.validation.replay import replay_and_validate_schedule

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "https://bup-preli-6ag0.onrender.com"
client = httpx.Client(base_url=BASE_URL, timeout=60.0)

print(f"Connecting to Render endpoint: {BASE_URL}...")
h_start = time.perf_counter()
h_res = client.get("/health")
h_ms = (time.perf_counter() - h_start) * 1000.0
assert h_res.status_code == 200, f"Health check failed: {h_res.text}"
print(f"GET /health: {h_res.status_code} OK ({h_res.json()}) in {h_ms:.1f} ms\n")

# 1. Run 10 Official Public Cases
pub_file = PROJECT_ROOT / "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"
with open(pub_file, "r", encoding="utf-8") as f:
    pub_data = json.load(f)

public_results = []
for case in pub_data["cases"]:
    cid = case["id"]
    inp = case["input"]
    exp = case["expected_output"]
    exp_cost = exp["total_cost_bdt"]

    t0 = time.perf_counter()
    res = client.post("/optimize-energy", json=inp)
    lat_ms = (time.perf_counter() - t0) * 1000.0

    if res.status_code != 200:
        public_results.append({
            "id": cid,
            "status": f"HTTP {res.status_code}",
            "act_cost": None,
            "exp_cost": exp_cost,
            "diff": None,
            "lat_ms": lat_ms,
            "replay": False,
        })
        continue

    data = res.json()
    resp_obj = OptimizeEnergyResponse.model_validate(data)
    req_obj = OptimizeEnergyRequest.model_validate(inp)

    # Replay verification
    compiled = compile_directives(req_obj, resp_obj.directive_interpretation)
    replay_passed = True
    try:
        replay_and_validate_schedule(req_obj, compiled, resp_obj.hourly_plan)
    except Exception:
        replay_passed = False

    act_cost = resp_obj.total_cost_bdt
    diff = abs(act_cost - exp_cost)
    is_ok = diff <= JUDGE_TOLERANCE and replay_passed

    public_results.append({
        "id": cid,
        "status": "PASSED" if is_ok else "MISMATCH",
        "act_cost": act_cost,
        "exp_cost": exp_cost,
        "diff": diff,
        "lat_ms": lat_ms,
        "replay": replay_passed,
        "directives": [d.directive_type.value for d in resp_obj.directive_interpretation],
    })

print("=" * 95)
print("OFFICIAL PUBLIC SAMPLE CASES EVALUATION (TOLERANCE = 0.01 BDT)")
print("=" * 95)
print(f"{'Case ID':<12} | {'Status':<8} | {'Output (BDT)':<14} | {'Expected (BDT)':<14} | {'Diff':<8} | {'Latency':<10} | {'Replay'}")
print("-" * 95)
for r in public_results:
    act_str = f"{r['act_cost']:.2f}" if r['act_cost'] is not None else "N/A"
    diff_str = f"{r['diff']:.2f}" if r['diff'] is not None else "N/A"
    replay_str = "VERIFIED" if r['replay'] else "FAILED"
    print(f"{r['id']:<12} | {r['status']:<8} | {act_str:<14} | {r['exp_cost']:<14.2f} | {diff_str:<8} | {r['lat_ms']:<7.1f} ms | {replay_str}")
print("-" * 95)
all_ok = all(r["status"] == "PASSED" for r in public_results)
avg_lat = sum(r["lat_ms"] for r in public_results) / len(public_results)
print(f"Result: {'10/10 ALL PASSED' if all_ok else 'SOME FAILED'} | Average Latency: {avg_lat:.1f} ms")
print("=" * 95)
