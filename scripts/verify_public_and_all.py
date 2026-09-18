import httpx
import json
import sys

client = httpx.Client(base_url='http://127.0.0.1:8000', timeout=30.0)

with open('BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

passed = 0
print("=" * 60)
print("VERIFYING 10 OFFICIAL PUBLIC SAMPLE CASES")
print("=" * 60)
for c in data['cases']:
    cid = c['id']
    exp_cost = c['expected_output']['total_cost_bdt']
    res = client.post('/optimize-energy', json=c['input'])
    if res.status_code != 200:
        print(f"  {cid}: FAILED with status {res.status_code}")
        continue
    act_cost = res.json()['total_cost_bdt']
    diff = abs(act_cost - exp_cost)
    status = "OK" if diff < 0.01 else "FAIL"
    print(f"  {cid}: Act={act_cost:.2f}, Exp={exp_cost:.2f}, Diff={diff:.2f} -> {status}")
    if diff < 0.01:
        passed += 1

print(f"Public sample cases: {passed}/{len(data['cases'])} PASSED")
print("=" * 60)
