#!/usr/bin/env python3
"""يقارن متجهات المطابقة المولَّدة من الكود الحالي بالمولَّدة من التزام آخر.

    python3 tests/compare_vectors.py <التزام>        # مثلًا 5b70237: main قبل المرحلة 0

يولّد متجهات المحرك وطبقة البنود والمجدول من الالتزام المذكور في مجلد مؤقت، ومن الكود الحالي، ثم يقارن الملفات بايتًا
ببايت. وإن اختلف ملف المجدول يذكر المسارات المختلفة، وأول عملية تختلف في كل منها، وما تغيّر في حالة المجدول بعدها.
"""
import json
import os
from collections import Counter
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REV = sys.argv[1]
FILES = ('conformance_vectors.json', 'item_vectors.json', 'scheduler_vectors.json')


def generate(folder):
    maps = sorted((f for f in os.listdir(folder) if f.startswith('mental-math-map-v') and f.endswith('.md')),
                  key=lambda f: [int(x) for x in f.split('-v')[1].split('-')[0].split('.')])
    for script in ('export_conformance.py', 'export_scheduler.py'):
        subprocess.run([sys.executable, script, maps[-1]], cwd=folder, check=True, stdout=subprocess.DEVNULL)


with tempfile.TemporaryDirectory() as tmp:
    old = os.path.join(tmp, 'old')
    os.mkdir(old)
    tar = subprocess.run(['git', '-C', ROOT, 'archive', REV], check=True, stdout=subprocess.PIPE).stdout
    subprocess.run(['tar', '-x', '-C', old], input=tar, check=True)
    generate(old)
    generate(ROOT)
    short = subprocess.run(['git', '-C', ROOT, 'rev-parse', '--short', REV], check=True, stdout=subprocess.PIPE,
                           text=True).stdout.strip()
    print('المتجهات من الكود الحالي مقابل الالتزام %s' % short)
    for f in FILES:
        a = open(os.path.join(ROOT, 'app', f), 'rb').read()
        b = open(os.path.join(old, 'app', f), 'rb').read()
        print('  %s: %s' % (f, 'مطابق بايتًا ببايت' if a == b else 'مختلف'))
        if a == b:
            continue
        new, was = json.loads(a), json.loads(b)
        if f == 'item_vectors.json':
            # ما الذي اختلف: مدخلات (البند المعروض وما أُجيب به) أم نتائج (حالة النشاط وسجلاته وأحداثه)؟
            for k in new:
                if new[k] == was[k]:
                    print('    %s: مطابق' % k)
                elif k != 'drives':
                    x = {json.dumps(v, sort_keys=True, ensure_ascii=False) for v in new[k]}
                    y = {json.dumps(v, sort_keys=True, ensure_ascii=False) for v in was[k]}
                    print('    %s: %d الآن و%d قبل؛ جديد %d وزائل %d' % (k, len(new[k]), len(was[k]), len(x - y), len(y - x)))
            diff = [(x, y) for x, y in zip(new['drives'], was['drives']) if x != y]
            keys, inner, ids = Counter(), Counter(), 0
            for x, y in diff:
                keys.update(k for k in x if x[k] != y.get(k))
                for p, q in zip(x['steps'], y['steps']):
                    inner.update(k for k in set(p) | set(q) if p.get(k) != q.get(k))
                    ids += int(bool(p.get('item')) and bool(q.get('item')) and p['item'].get('id') != q['item'].get('id'))
            print('    drives: %d، والمختلف %d. الحقول المختلفة فيها: %s. داخل الخطوات: %s. بنود اختلف معرّفها: %d' % (
                len(new['drives']), len(diff) + abs(len(new['drives']) - len(was['drives'])),
                dict(keys), dict(inner), ids))
            continue
        if f != 'scheduler_vectors.json':
            continue
        top = [k for k in new if k != 'traces' and new[k] != was[k]]
        parts = Counter(k for x, y in zip(new['traces'], was['traces']) if x != y for k in x if x[k] != y.get(k))
        print('    خارج المسارات، المختلف: %s. وفي المسارات المختلفة، الحقول: %s' % (top or 'لا شيء', dict(parts)))
        print('    (tape و tables مدخلات: البند المعروض وما أُجيب به. ops قرارات المجدول وحالته بعد كل عملية.)')
        diff = [i for i, (x, y) in enumerate(zip(new['traces'], was['traces'])) if x != y]
        print('    المسارات: %d، والمختلف منها %d. ما عدا المسارات مطابق: %s' % (
            len(new['traces']), len(diff) + abs(len(new['traces']) - len(was['traces'])),
            all(new[k] == was[k] for k in new if k != 'traces')))
        for i in diff:
            x, y = new['traces'][i], was['traces'][i]
            for j, (p, q) in enumerate(zip(x['ops'], y['ops'])):
                if p != q:
                    before = [o['args'][0] for o in x['ops'][:j] if o['op'] == 'engine_apply']
                    keys = [k for k in p.get('post', {}) if p['post'][k] != q.get('post', {}).get(k)]
                    print('    المسار %d: أول اختلاف في العملية %d (%s). قرارات خارجية قبلها: %s' % (
                        i, j, p['op'], ['%s %s' % (e['type'], e.get('target', e.get('check_id', ''))) for e in before]))
                    print('      حقول الحالة المختلفة: %s' % '، '.join(keys))
                    print('      آخر سجل المجدول، الآن: %s' % json.dumps(p['post']['log']['last'][-1], ensure_ascii=False))
                    print('      آخر سجل المجدول، قبل: %s' % json.dumps(q['post']['log']['last'][-1], ensure_ascii=False))
                    print('      اقتراحات رفضها المحرك، الآن %d وقبل %d' % (p['post']['refused']['n'], q['post']['refused']['n']))
                    break
