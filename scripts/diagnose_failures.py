import json
import httpx
from pathlib import Path

files = [
    'Test cases/gridwise_schema_compliant_full_judge_cases_100.json',
    'Test cases/gridwise_single_note_multiple_directive_cases_100.json',
    'Test cases/gridwise_bangla_banglish_mixed_cases_100.json',
    'Test cases/gridwise_overall_bangla_cases_100.json'
]

client = httpx.Client(base_url='http://127.0.0.1:8000', timeout=30.0)

for fpath in files:
    print('=' * 60)
    print('Testing file:', fpath)
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    cases = data.get('cases', [])
    mismatches = 0
    errors = 0
    for idx, c in enumerate(cases):
        cid = c.get('id', f'CASE-{idx+1}')
        inp = c['input']
        exp_interp = c.get('expected_directive_interpretation')
        try:
            res = client.post('/optimize-energy', json=inp)
        except Exception as ex:
            errors += 1
            if errors <= 3:
                print(f'  [EX] {cid}: {ex}')
            continue

        if res.status_code != 200:
            errors += 1
            if errors <= 3:
                print(f'  [HTTP {res.status_code}] {cid}: {res.text[:120]}')
            continue

        resp_json = res.json()
        act_interp = resp_json.get('directive_interpretation', [])
        if exp_interp is not None:
            mismatch_reasons = []
            if len(act_interp) != len(exp_interp):
                mismatch_reasons.append(f'len mismatch: act {len(act_interp)} vs exp {len(exp_interp)}')
            else:
                for a, e in zip(act_interp, exp_interp):
                    if a.get('directive_type') != e.get('directive_type'):
                        mismatch_reasons.append(f"type: act {a.get('directive_type')} vs exp {e.get('directive_type')}")
                    elif a.get('applies') != e.get('applies'):
                        mismatch_reasons.append(f"applies: act {a.get('applies')} vs exp {e.get('applies')}")
                    else:
                        a_adj = a.get('structured_adjustment') or {}
                        e_adj = e.get('structured_adjustment') or {}
                        if a_adj.get('hours') != e_adj.get('hours'):
                            mismatch_reasons.append(f"hours: act {a_adj.get('hours')} vs exp {e_adj.get('hours')}")
            if mismatch_reasons:
                mismatches += 1
                if mismatches <= 3:
                    print(f'  [MISMATCH] {cid}: {inp["operator_notes"]}')
                    print(f'     Act: {act_interp}')
                    print(f'     Exp: {exp_interp}')
                    print(f'     Reason: {"; ".join(mismatch_reasons)}')
    print(f'Total: {len(cases)}, Mismatches: {mismatches}, Errors: {errors}, Passed: {len(cases) - mismatches - errors}')
