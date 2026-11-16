#!/usr/bin/env python3
"""حالات المراجعة العاشرة على المحرك المرجعي وطبقة البنود بلغة بايثون.

    python3 tests/test_r10.py <ملف الخريطة> [--code مجلد]

النتائج المتوقعة في tests/r10_cases.json، مكتوبة يدويًا من نص القاعدة. --code يشغّل الحالات على نسخة أخرى من
الكود (مثلًا الالتزام السابق للإصلاح)، ليُرى أنها تفشل بسبب العيب المقصود.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
args = [a for a in sys.argv[1:] if not a.startswith('--code')]
code = next((a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--code=')), os.path.dirname(HERE))
sys.path.insert(0, os.path.abspath(code))
from transition_engine import Engine, load_network  # noqa: E402
from item_layer import fold_item, indicators  # noqa: E402

MAP = args[0]
NET = load_network(MAP)
CASES = json.load(open(os.path.join(HERE, 'r10_cases.json'), encoding='utf-8'))


def query(e, key):
    kind, arg = key.split(':', 1)
    if kind == 'state':
        return e.derive()[arg]
    if kind == 'check':
        return e.s['checks'][arg]['state']
    if kind == 'teach':
        return e.s['sessions'][arg]['teach']
    if kind == 'clock':
        return e.s['sessions'][arg]['clock']
    if kind == 'valid_independent':
        return len(e.valid_evidence(arg, 'independent'))
    if kind == 'independent_items':
        return [i for x in e.s['evidence'] if x['skill'] == arg and x['kind'] == 'independent' for i in x.get('items', [])]
    if kind == 'retention_due_day':
        nxt = e.retention_next(arg)
        return None if nxt is None else nxt[1]
    raise KeyError(key)


def compare(e, expect, where):
    out = []
    for k, want in expect.items():
        try:
            got = query(e, k)
        except Exception as x:                               # noqa: BLE001
            got = 'خطأ: %s' % type(x).__name__
        if got != want:
            out.append('%s: %s = %r، والمتوقع %r' % (where, k, got, want))
    return out


def run_steps(e, steps, n):
    bad = []
    for st in steps:
        if 'do' in st:
            if st['do'] == 'restore':
                e = Engine.restore(NET, e.dump())
            else:
                e = Engine.replay(NET, e.s['log'])
            continue
        n[0] += 1
        ev = dict(st['ev'], id='r%d' % n[0])
        res = e.apply(ev)
        if 'ok' in st and not res['ok']:
            bad.append('%s رُفض (%s)، والمتوقع قبوله' % (ev['type'], res.get('code')))
        elif 'code' in st and (res['ok'] or res.get('code') != st['code']):
            bad.append('%s: %s، والمتوقع الرفض بـ %s' % (ev['type'], 'قُبل' if res['ok'] else res.get('code'), st['code']))
        elif st.get('refused') and res['ok']:
            bad.append('%s قُبل، والمتوقع رفضه' % ev['type'])
        if bad:
            break
    return e, bad


def check_all(e, expect, label):
    bad = compare(e, expect, label)
    bad += compare(Engine.restore(NET, e.dump()), expect, label + ' بعد الحفظ والاستعادة')
    bad += compare(Engine.replay(NET, e.s['log']), expect, label + ' بعد إعادة تشغيل السجل')
    return bad


def engine_case(c):
    e, n = Engine(NET), [0]
    e, bad = run_steps(e, CASES['bases'].get(c.get('base'), []), n)
    if bad:
        return ['الأساس: ' + b for b in bad]
    e, bad = run_steps(e, c['steps'], n)
    if not bad:
        bad = check_all(e, c['expect'], 'آخر الخطوات')
    if not bad and 'then' in c:
        e, bad = run_steps(e, c['then'], n)
        if not bad:
            bad = check_all(e, c['expect_then'], 'بعد المتابعة')
    return bad


def dig(d, path):
    for k in path.split('.'):
        d = d[k]
    return d


def fold_case(c):
    raw = [tuple(x) for x in c['raw']]
    if 'split' in c:                                        # الأحداث الخام تُحفظ نصًّا في منتصف البند ثم تُكمَل
        raw = [tuple(x) for x in json.loads(json.dumps(c['raw'][:c['split']]))] + raw[c['split']:]
    return fold_item(raw, c['answer'], c['assess'])


def item_case(c, recs):
    rec = fold_case(c)
    recs[c['id']] = rec
    bad = ['الحقل %s = %r، والمتوقع %r' % (k, rec.get(k, '«غير موجود»'), v)
           for k, v in c.get('record', {}).items() if rec.get(k, '«غير موجود»') != v]
    ind = indicators([rec])
    bad += ['المؤشر %s = %r، والمتوقع %r' % (k, dig(ind, k), v) for k, v in c['indicators'].items() if dig(ind, k) != v]
    return bad


results = []


def report(c, bad):
    results.append(not bad)
    print('  %s  %s %s%s' % ('نجح' if not bad else 'أخفق', c['id'], c['title'],
                             '' if c.get('reproduced_by_reviewer') is False else ' [أعاد المراجع إنتاجه]'))
    for b in bad[:3]:
        print('        ' + b)


print('=== حالات المراجعة العاشرة، بلغة بايثون، على الكود في %s' % os.path.relpath(os.path.abspath(code)))
for c in CASES['engine']:
    try:
        bad = engine_case(c)
    except Exception as x:                                   # noqa: BLE001
        bad = ['استثناء: %r' % (x,)]
    report(c, bad)
recs = {}
for c in CASES['items']:
    try:
        bad = item_case(c, recs)
    except Exception as x:                                   # noqa: BLE001
        bad = ['استثناء: %r' % (x,)]
    report(c, bad)
for c in CASES['item_sets']:
    ind = indicators([recs[k] for k in c['of']])
    report(c, ['المؤشر %s = %r، والمتوقع %r' % (k, dig(ind, k), v) for k, v in c['indicators'].items()
               if dig(ind, k) != v])
print('النتيجة: نجح %d من %d' % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
