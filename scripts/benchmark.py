"""Performance benchmark measuring p50, p95, p99, min, and max request latencies."""

import json
import sys
import time
from pathlib import Path
import httpx
import numpy as np


def run_benchmark(base_url: str = "http://localhost:8000", iterations: int = 50) -> None:
    cases_file = Path(__file__).resolve().parent.parent / "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"
    with open(cases_file, "r", encoding="utf-8") as f:
        cases = json.load(f)["cases"]

    client = httpx.Client(base_url=base_url, timeout=30.0)

    # Pre-flight check
    try:
        health = client.get("/health")
        if health.status_code != 200:
            print(f"Error: /health returned {health.status_code}")
            return
    except Exception as e:
        print(f"Could not connect to {base_url}: {e}")
        return

    print(f"\n--- Starting GridWise Performance Benchmark ({iterations} requests) ---")
    latencies: list[float] = []
    failures = 0

    for i in range(iterations):
        case = cases[i % len(cases)]
        t0 = time.perf_counter()
        try:
            res = client.post("/optimize-energy", json=case["input"])
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            if res.status_code == 200:
                latencies.append(elapsed_ms)
            else:
                failures += 1
        except Exception:
            failures += 1

    if not latencies:
        print("All benchmark requests failed.")
        return

    arr = np.array(latencies)
    p50 = np.percentile(arr, 50)
    p90 = np.percentile(arr, 90)
    p95 = np.percentile(arr, 95)
    p99 = np.percentile(arr, 99)
    min_lat = np.min(arr)
    max_lat = np.max(arr)
    avg_lat = np.mean(arr)

    print("\nBenchmark Results:")
    print(f"Total Requests  : {iterations}")
    print(f"Successful      : {len(latencies)}")
    print(f"Failed          : {failures} (failure rate: {(failures/iterations)*100:.1f}%)")
    print(f"Min Latency     : {min_lat:.2f} ms")
    print(f"Mean Latency    : {avg_lat:.2f} ms")
    print(f"p50 Latency     : {p50:.2f} ms")
    print(f"p90 Latency     : {p90:.2f} ms")
    print(f"p95 Latency     : {p95:.2f} ms (Target: <= 5000 ms)")
    print(f"p99 Latency     : {p99:.2f} ms")
    print(f"Max Latency     : {max_lat:.2f} ms")

    if p95 <= 5000.0 and failures == 0:
        print("\nPASSED: p95 latency is well within the 5.0 second competition threshold!")
    else:
        print("\nWARNING: Latency or failure rate did not meet optimal criteria.")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    iters = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    run_benchmark(url, iters)
