#!/usr/bin/env python3
"""يقارن قرارات المجدول ومدخلاته بين ملفي متجهات، مسارًا بمسار، بعد حلّ فهارس جدول البنود إلى البنود نفسها.

    python3 tests/compare_decisions.py <scheduler_vectors.json القديم> [<الجديد>]

tests/compare_vectors.py تقارن حالة المحرك كلها، فإضافة حقل إلى حالته تجعل كل مسار «مختلفًا» ولا يظهر أين تغيّر قرار.
هذه تقارن ثلاثة أشياء وحدها: سجل قرارات المجدول (بصمته وعدده بعد آخر عملية)، وعدد الجلسات، والشريط (ما عُرض وما أُجيب
به) بعد حلّ الفهارس وإسقاط بصمة البند v. أداة عرض، ورمز خروجها ليس حكمًا.
"""
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
old = json.load(open(sys.argv[1], encoding='utf-8'))
new = json.load(open(sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'app', 'scheduler_vectors.json'),
                     encoding='utf-8'))


def item(v, k):
    it = v['tables']['items'][k] if isinstance(k, int) else k
    return {f: it[f] for f in it if f != 'v'} if isinstance(it, dict) else it


def tape(v, t):
    out = []
    for x in t['tape']:
        if x[0] == 'src':
            out.append(['src', x[1], x[2], item(v, x[3])])
        elif x[0] == 'ans':
            out.append(['ans', item(v, x[1])] + x[2:])
        else:
            out.append(x)
    return out


def ident(x):
    it = x[3] if x[0] == 'src' else x[1] if x[0] == 'ans' else None
    return it.get('id') if isinstance(it, dict) else None


N, O = new['traces'], old['traces']
print('المسارات: %d الآن و%d قبل' % (len(N), len(O)))
logs, inputs, what = [], [], Counter()
for i, (a, b) in enumerate(zip(N, O)):
    pa, pb = a['ops'][-1]['post'], b['ops'][-1]['post']
    if pa['log'] != pb['log'] or pa['sessions'] != pb['sessions'] or len(a['ops']) != len(b['ops']):
        logs.append(i)
    ta, tb = tape(new, a), tape(old, b)
    if ta != tb:
        inputs.append(i)
        if len(ta) != len(tb):
            what['طول الشريط'] += 1
        else:
            for x, y in zip(ta, tb):
                if x != y:
                    what[ident(x) or ident(y) or x[0]] += 1
print('قرارات المجدول (سجله وعدد جلساته وعملياته) تختلف في %d مسارًا: %s' % (len(logs), logs))
print('المدخلات (ما عُرض وما أُجيب به) تختلف في %d مسارًا: %s' % (len(inputs), inputs))
print('  ما اختلف في المسارات المتساوية الطول، بمعرّف البند: %s' % dict(what))
for i in logs:
    ta, tb = tape(new, N[i]), tape(old, O[i])
    j = next((k for k, (x, y) in enumerate(zip(ta, tb)) if x != y), min(len(ta), len(tb)))

    def show(t):
        return ['%s %s' % (x[2].get('activity'), ident(x)) if x[0] == 'src'
                else 'جواب %s' % json.dumps(x[3][0] if isinstance(x[3], list) else x[3], ensure_ascii=False)
                for x in t[max(0, j - 2):j + 6] if x[0] in ('src', 'ans')]
    print('  المسار %d (%s): أول اختلاف في الشريط عند %d. سجل المجدول %d مدخلًا الآن و%d قبل' % (
        i, ' '.join(N[i]['opts'].get('scope') or []), j, N[i]['ops'][-1]['post']['log']['n'],
        O[i]['ops'][-1]['post']['log']['n']))
    print('    الآن: %s' % '، '.join(show(ta)))
    print('    قبل: %s' % '، '.join(show(tb)))
