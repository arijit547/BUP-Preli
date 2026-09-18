import json
import sys

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

files = [
    'Test cases/gridwise_schema_compliant_full_judge_cases_100.json',
    'Test cases/gridwise_single_note_multiple_directive_cases_100.json',
    'Test cases/gridwise_bangla_banglish_mixed_cases_100.json',
    'Test cases/gridwise_overall_bangla_cases_100.json'
]

for fpath in files:
    print('=' * 70)
    print(fpath)
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    cases = data.get('cases', [])
    note_to_exp = {}
    for c in cases:
        notes = tuple(c['input']['operator_notes'])
        exp = c.get('expected_directive_interpretation')
        if exp is not None:
            note_to_exp[notes] = exp
    print(f'Total cases: {len(cases)}, unique note combinations: {len(note_to_exp)}')
    for i, (notes, exp) in enumerate(note_to_exp.items()):
        print(f'  [{i+1}] {notes}')
        for d in exp:
            print(f'       dir_type={d.get("directive_type")}, applies={d.get("applies")}, adj={d.get("structured_adjustment")}')
