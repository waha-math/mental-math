#!/usr/bin/env python3
"""يصنع الحالات المحفوظة القديمة لحالات المراجعة الحادية عشرة، بمحرك الالتزام الذي فحصه المراجع.

    sh tests/make_r11_fixtures.sh            (يستخرج الالتزامين 2509126 و16b124a ويشغّل هذا الملف عليهما)
    python3 tests/make_r11_fixtures.py <ملف الخريطة> --code=<مجلد 2509126> --via=<مجلد 16b124a>

لكل حالة في tests/r11_cases.json تُطبَّق أحداث old بالمحرك القديم، ويجب أن يقبلها كلها كما كُتبت، ثم يُحفظ نصه.
no_log: يُحفظ النص بسجل فارغ، كحالة لا يتاح سجل أحداثها.
via_16b124a (المراجعة 12): النص نفسه بعد أن قرأه محرك الالتزام 16b124a بـ restore ثم حفظه بـ dump، كما يحدث لحالة
فتحها تطبيق بتلك النسخة. ذلك المحرك أضاف قائمة الجلسات المساهمة ولم يطبّق أثر الإبطال.
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
code = next(a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--code='))
via = next(a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--via='))
sys.path.insert(0, os.path.abspath(code))
from transition_engine import Engine, load_network  # noqa: E402

NET_PATH = [a for a in sys.argv[1:] if not a.startswith('--')][0]
NET = load_network(NET_PATH)
CASES = json.load(open(os.path.join(HERE, 'r11_cases.json'), encoding='utf-8'))
spec = importlib.util.spec_from_file_location('engine_via', os.path.join(os.path.abspath(via), 'transition_engine.py'))
VIA = importlib.util.module_from_spec(spec)
spec.loader.exec_module(VIA)
out, out_via = {}, {}
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
    v = json.loads(VIA.Engine.restore(VIA.load_network(NET_PATH), out[c['id']]).dump())
    assert all('sessions' in k for k in v['checks'].values()) and 'migration' not in v, 'ليست حالة 16b124a'
    out_via[c['id']] = json.dumps(v, ensure_ascii=False, sort_keys=True)
json.dump(dict(made_by=CASES['old_commit'], states=out, via_by='16b124a', via_16b124a=out_via), open(os.path.join(HERE, 'r11_fixtures.json'), 'w',
          encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
print('صُنعت %d حالة قديمة بمحرك الالتزام %s، و%d بعد قراءتها وحفظها بمحرك 16b124a'
      % (len(out), CASES['old_commit'], len(out_via)))
