"""Evaluate directive interpretation on all 50 ULTIMA adversarial cases."""

import asyncio
import json
from pathlib import Path

import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.constants import JUDGE_TOLERANCE
from app.llm.interpreter import LLMInterpreter
from scripts.test_ultima_benchmark import compare_directives


async def main():
    with open(PROJECT_ROOT / "gridwise_ultima_50_hardest.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    cases = data.get("test_cases", [])
    battery_cap = data["metadata"]["default_battery"]["capacity_kwh"]

    interp = LLMInterpreter()
    semaphore = asyncio.Semaphore(5)

    async def run_c(c):
        cid = c["id"]
        title = c.get("title", "")
        cat = c.get("category", "")
        notes = c["operator_notes"]
        exp_dirs = c["expected_directives"]

        async with semaphore:
            try:
                act_dirs, ms = await interp.interpret_notes(notes, battery_cap)
                ok, reason = compare_directives(act_dirs, exp_dirs)
                return {
                    "id": cid,
                    "title": title,
                    "category": cat,
                    "passed": ok,
                    "reason": reason,
                    "latency_ms": ms,
                    "act_dirs": [d.model_dump() for d in act_dirs],
                    "exp_dirs": exp_dirs,
                }
            except Exception as e:
                return {
                    "id": cid,
                    "title": title,
                    "category": cat,
                    "passed": False,
                    "reason": f"EXCEPTION: {type(e).__name__}: {e}",
                    "latency_ms": 0.0,
                    "act_dirs": [],
                    "exp_dirs": exp_dirs,
                }

    print(f"Evaluating {len(cases)} ULTIMA cases on local interpreter...")
    results = await asyncio.gather(*[run_c(c) for c in cases])

    passed = sum(1 for r in results if r["passed"])
    print(f"\nDirectives Evaluation: {passed}/{len(cases)} PASSED ({(passed/len(cases))*100:.1f}%)\n")

    for r in results:
        status = "PASSED" if r["passed"] else "FAILED"
        print(f"{r['id']:<8} | {r['category']:<22} | {status:<7} | {r['reason']}")

    with open(PROJECT_ROOT / "ultima_directives_eval.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    asyncio.run(main())
