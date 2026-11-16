#!/usr/bin/env python3
"""يصنع الحالات المحفوظة القديمة لحالات المراجعة الحادية عشرة، بمحرك الالتزام الذي فحصه المراجع.

    sh tests/make_r11_fixtures.sh            (يستخرج الالتزام 2509126 ويشغّل هذا الملف عليه)
    python3 tests/make_r11_fixtures.py <ملف الخريطة> --code=<مجلد كود الالتزام القديم>

لكل حالة في tests/r11_cases.json تُطبَّق أحداث old بالمحرك القديم، ويجب أن يقبلها كلها كما كُتبت، ثم يُحفظ نصه.
no_log: يُحفظ النص بسجل فارغ، كحالة لا يتاح سجل أحداثها.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
code = next(a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--code='))
sys.path.insert(0, os.path.abspath(code))
from transition_engine import Engine, load_network  # noqa: E402

NET = load_network([a for a in sys.argv[1:] if not a.startswith('--')][0])
CASES = json.load(open(os.path.join(HERE, 'r11_cases.json'), encoding='utf-8'))
out = {}
for c in CASES['engine']:
    e = Engine(NET)
    for n, st in enumerate(c['old']):
        r = e.apply(dict(st['ev'], id='o%d' % (n + 1)))
        assert r['ok'], (c['id'], st['ev'], r)
    s = json.loads(e.dump())
    assert all('sessions' not in k for k in s['checks'].values()), 'ليست حالة قديمة'
    if c.get('no_log'):
        s['log'] = []
    out[c['id']] = json.dumps(s, ensure_ascii=False, sort_keys=True)
json.dump(dict(made_by=CASES['old_commit'], states=out), open(os.path.join(HERE, 'r11_fixtures.json'), 'w',
          encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
print('صُنعت %d حالة قديمة بمحرك الالتزام %s' % (len(out), CASES['old_commit']))
