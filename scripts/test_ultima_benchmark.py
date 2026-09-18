"""Runner to evaluate the new 50 hardest adversarial test cases (gridwise_ultima_50_hardest.json) against Render."""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx
from app.core.constants import JUDGE_TOLERANCE
from app.schemas.response import OptimizeEnergyResponse

TARGET_URL = os.environ.get("TARGET_URL", "https://bup-preli-6ag0.onrender.com")
CONCURRENCY = 10
TIMEOUT = 90.0


def compare_directives(actual: list, expected: list) -> tuple[bool, str]:
    if len(actual) != len(expected):
        return False, f"Count mismatch: got {len(actual)}, expected {len(expected)}"

    for i, (act, exp) in enumerate(zip(actual, expected)):
        act_d = act.directive_type.value if hasattr(act.directive_type, "value") else str(act.directive_type)
        exp_d = exp.get("directive_type")
        if act_d != exp_d:
            return False, f"Index {i} directive_type mismatch: got '{act_d}', expected '{exp_d}'"

        if act.applies != exp.get("applies"):
            return False, f"Index {i} applies mismatch: got {act.applies}, expected {exp.get('applies')}"

        exp_adj = exp.get("structured_adjustment")
        act_adj = act.structured_adjustment

        if exp_adj is not None:
            if act_adj is None or act_adj.__class__.__name__ == "EmptyAdjustment":
                return False, f"Index {i} structured_adjustment missing: expected {exp_adj}"

            act_adj_dict = act_adj.model_dump() if hasattr(act_adj, "model_dump") else act_adj

            # Compare hours
            if "hours" in exp_adj:
                exp_hours = sorted(exp_adj["hours"])
                act_hours = sorted(act_adj_dict.get("hours", []))
                if act_hours != exp_hours:
                    return False, f"Index {i} hours mismatch: got {act_hours}, expected {exp_hours}"

            # Compare factor
            if "factor" in exp_adj:
                exp_f = exp_adj["factor"]
                act_f = act_adj_dict.get("factor")
                if act_f is None or abs(act_f - exp_f) > JUDGE_TOLERANCE:
                    return False, f"Index {i} factor mismatch: got {act_f}, expected {exp_f}"

            # Compare minimum_energy_kwh
            if "minimum_energy_kwh" in exp_adj:
                exp_e = exp_adj["minimum_energy_kwh"]
                act_e = act_adj_dict.get("minimum_energy_kwh")
                if act_e is None or abs(act_e - exp_e) > JUDGE_TOLERANCE:
                    return False, f"Index {i} minimum_energy_kwh mismatch: got {act_e}, expected {exp_e}"

            # Compare max_grid_kwh
            if "max_grid_kwh" in exp_adj:
                exp_g = exp_adj["max_grid_kwh"]
                act_g = act_adj_dict.get("max_grid_kwh")
                if act_g is None or abs(act_g - exp_g) > JUDGE_TOLERANCE:
                    return False, f"Index {i} max_grid_kwh mismatch: got {act_g}, expected {exp_g}"

    return True, "OK"


async def main():
    print("=" * 110)
    print("EVALUATING GRIDWISE ULTIMA-50 (50 HARDEST ADVERSARIAL CASES)")
    print(f"Target: {TARGET_URL}")
    print(f"Tolerance: {JUDGE_TOLERANCE}")
    print("=" * 110)

    # Load baseline hours
    with open(PROJECT_ROOT / "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json", "r") as f:
        sample_data = json.load(f)
    baseline_hours = sample_data["cases"][0]["input"]["hours"]

    # Load ULTIMA-50
    with open(PROJECT_ROOT / "gridwise_ultima_50_hardest.json", "r", encoding="utf-8") as f:
        ultima_data = json.load(f)

    cases = ultima_data.get("test_cases", [])
    battery = ultima_data["metadata"]["default_battery"]

    semaphore = asyncio.Semaphore(CONCURRENCY)

    async with httpx.AsyncClient(base_url=TARGET_URL, timeout=TIMEOUT) as client:
        # Check health
        h = await client.get("/health")
        assert h.status_code == 200, "Health check failed"
        print("GET /health: 200 OK\n")

        async def eval_case(c):
            cid = c["id"]
            title = c.get("title", "")
            cat = c.get("category", "")
            notes = c["operator_notes"]
            exp_dirs = c["expected_directives"]

            payload = {
                "scenario_id": cid,
                "battery": battery,
                "operator_notes": notes,
                "hours": baseline_hours,
            }

            async with semaphore:
                t0 = time.perf_counter()
                try:
                    res = await client.post("/optimize-energy", json=payload)
                    lat_ms = (time.perf_counter() - t0) * 1000.0

                    if res.status_code != 200:
                        return {
                            "id": cid,
                            "category": cat,
                            "title": title,
                            "passed": False,
                            "latency_ms": lat_ms,
                            "status": f"HTTP_{res.status_code}",
                            "error": res.text[:120],
                            "act_dirs": [],
                            "exp_dirs": exp_dirs,
                        }

                    data = res.json()
                    resp_obj = OptimizeEnergyResponse.model_validate(data)
                    act_dirs = resp_obj.directive_interpretation

                    ok, reason = compare_directives(act_dirs, exp_dirs)
                    return {
                        "id": cid,
                        "category": cat,
                        "title": title,
                        "passed": ok,
                        "latency_ms": lat_ms,
                        "status": "PASSED" if ok else "MISMATCH",
                        "error": reason if not ok else "",
                        "act_dirs": [d.model_dump() for d in act_dirs],
                        "exp_dirs": exp_dirs,
                    }

                except Exception as e:
                    lat_ms = (time.perf_counter() - t0) * 1000.0
                    return {
                        "id": cid,
                        "category": cat,
                        "title": title,
                        "passed": False,
                        "latency_ms": lat_ms,
                        "status": "ERROR",
                        "error": f"{type(e).__name__}: {e}",
                        "act_dirs": [],
                        "exp_dirs": exp_dirs,
                    }

        print("Executing 50 adversarial cases against Render...")
        t_start = time.perf_counter()
        results = await asyncio.gather(*[eval_case(c) for c in cases])
        wall_time = time.perf_counter() - t_start

    passed_count = sum(1 for r in results if r["passed"])
    print(f"\nCompleted in {wall_time:.2f}s! Passed: {passed_count}/{len(cases)} ({(passed_count/len(cases))*100:.1f}%)\n")

    print(f"{'ID':<8} | {'Category':<20} | {'Status':<8} | {'Latency':<9} | {'Result / Error':<45}")
    print("-" * 100)
    for r in results:
        status_str = r["status"]
        lat_str = f"{r['latency_ms']:.1f} ms"
        err_str = "OK" if r["passed"] else r["error"][:45]
        print(f"{r['id']:<8} | {r['category']:<20} | {status_str:<8} | {lat_str:<9} | {err_str:<45}")
    print("-" * 100)

    # Category breakdown
    from collections import defaultdict
    cat_stats = defaultdict(lambda: {"total": 0, "passed": 0})
    for r in results:
        cat_stats[r["category"]]["total"] += 1
        if r["passed"]:
            cat_stats[r["category"]]["passed"] += 1

    print("\nCATEGORY BREAKDOWN:")
    print(f"{'Category':<25} | {'Score':<10} | {'Percentage'}")
    print("-" * 50)
    for cat, st in sorted(cat_stats.items()):
        pct = (st["passed"] / st["total"]) * 100
        print(f"{cat:<25} | {st['passed']}/{st['total']:<8} | {pct:.1f}%")

    with open(PROJECT_ROOT / "ultima_50_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "total": len(cases),
            "passed": passed_count,
            "wall_time": wall_time,
            "results": results,
        }, f, indent=2, ensure_ascii=False)
    print(f"\nFull detailed results saved to: ultima_50_results.json")


if __name__ == "__main__":
    asyncio.run(main())
