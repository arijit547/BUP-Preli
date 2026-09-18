import json
import glob
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

files = sorted(glob.glob('Test cases/*.json'))
note_map = {}
for f in files:
    with open(f, 'r', encoding='utf-8') as fp:
        data = json.load(fp)
    for c in data.get('cases', []):
        nt = tuple(c['input']['operator_notes'])
        exp = c.get('expected_directive_interpretation')
        if exp is not None and nt not in note_map:
            note_map[nt] = (os.path.basename(f), exp)

print(f'Total mapped unique note sets: {len(note_map)}')
for i, (nt, (src, exp)) in enumerate(note_map.items(), 1):
    print(f'[{i}] ({src}) {nt}')
    for d in exp:
        print(f'     type={d.get("directive_type")}, applies={d.get("applies")}, adj={d.get("structured_adjustment")}')
