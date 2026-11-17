#!/usr/bin/env python3
"""يختبر فحص تتابع البنود (content_sequence.py) والمحتوى بعد إصلاحه.

    python3 tests/test_content_sequence.py <ملف الخريطة>

الحالات، ونتائجها مكتوبة من القاعدة:
1. المحتوى الحالي: لا زوج بنود متتاليين بالحقيقة نفسها في أي فرع تشغيل، ولا قفزة قيمتها صفر في تسلسل حل معروض.
2. الفحص يكشف: يُزرع في نسخة من المحتوى بند دليل فهم بحقيقة البند الذي قبله، فيجده. ويُزرع بديل دليل فهم بحقيقة
   البند الذي يليه في الموضع التالي، فيجده (البديل يُفحص مع ما يليه).
3. الاستثناء محدود: البند الذي يلي بندًا منقطعًا لا يُعدّ مخالفة، والذي يلي بندًا أُجيب عنه يُعدّ.
4. التغطية: أزواج البنود التي يعرضها المجدول فعلًا في تشغيل كامل للشريحة (الصغير، والكبيران، بأخطاء وطلبات دعم)
   داخل النشاط الواحد، وبين الافتتاح والدرس ودليل الفهم، كلها من الأزواج التي استكشفها الفحص. لو فات الفحصَ فرعٌ
   يسلكه المجدول لظهر هنا.
5. محتوى الالتزام 17d7b0b (قبل الإصلاح) يُخفق في الفحص نفسه: للمقارنة، إن وُجد git.
"""
import copy
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import content_sequence as cs  # noqa: E402
from slice_content import zero_step, SLOTS  # noqa: E402

MAP = sys.argv[1]
items = json.load(open(os.path.join(ROOT, 'slice-content.json'), encoding='utf-8'))['items']
types = cs.load_types(items)
results = []


def expect(title, got, want):
    ok = got == want
    results.append(ok)
    print('  %s  %s' % ('نجح' if ok else 'أخفق', title))
    if not ok:
        print('        %r، والمتوقع %r' % (got, want))


pairs, by_id, explored = cs.collect(items, types)
bad = cs.violations(pairs, by_id)
zeros = [i['id'] for i in items if i['skill'] in SLOTS and zero_step(i)]
expect('1. المحتوى الحالي: لا مخالفة تتابع ولا قفزة صفرية (%d نشاطًا، %d زوجًا)' % (explored, len(pairs)),
       [len(bad), zeros], [0, []])


def planted(change):
    its = copy.deepcopy(items)
    change({i['id']: i for i in its})
    p, b, _n = cs.collect(its, types)
    return {(x, y) for x, y, _h, _l, _f in cs.violations(p, b)}


def same_as(target, source):
    def change(d):
        d[target]['numbers']['n'] = 10 - d[source]['numbers']['n']
    return change


# 1-4-2، ف2، الجولة 1: 01 ثم 02 أساسيان، 03 و04 احتياطيان، 25 بديل. ثم ف3: 05 و06
got = planted(same_as('1-4-2/evidence/02', '1-4-2/evidence/01'))
expect('2أ. بند دليل فهم زُرع بحقيقة سابقه: يُكشف', ('1-4-2/evidence/01', '1-4-2/evidence/02') in got, True)
got = planted(same_as('1-4-2/evidence/25', '1-4-2/evidence/02'))
expect('2ب. بديل زُرع بحقيقة البند الذي يليه حين يحل محل 01: يُكشف', ('1-4-2/evidence/25', '1-4-2/evidence/02') in got, True)

# فحص الاستقلال في 1-4-2، المحاولة A: بديل الخانة 1 (02) يعيد حقيقة بندها (01) بعد انقطاعه، بقرار الأب
a, b = by_id['1-4-2/checkA/01'], by_id['1-4-2/checkA/02']
how = sorted(h for x, y, h, _l in pairs if (x, y) == (a['id'], b['id']))
expect('3أ. بديل الخانة بعد بندها المنقطع: الحقيقة نفسها، وليس مخالفة',
       [cs.fact(a) == cs.fact(b), how, any((x, y) == (a['id'], b['id']) for x, y, _h, _l, _f in bad)],
       [True, ['interrupted'], False])
got = planted(same_as('1-4-2/checkA/03', '1-4-2/checkA/01'))
expect('3ب. بند الخانة 2 زُرع بحقيقة الخانة 1: مخالفة بعد بند الخانة 1 المجاب وبعد بديلها المجاب',
       [('1-4-2/checkA/01', '1-4-2/checkA/03') in got, ('1-4-2/checkA/02', '1-4-2/checkA/03') in got], [True, True])

# 4) التغطية: ما يعرضه المجدول فعلًا
src = open(os.path.join(HERE, 'test_phase0.py'), encoding='utf-8').read()
g = {'__file__': os.path.join(HERE, 'test_phase0.py'), '__name__': 'phase0_helpers'}
sys.argv = [g['__file__'], MAP]
exec(compile(src[:src.index("\nprint('=== ")], 'test_phase0.py', 'exec'), g)
known = {(x, y) for x, y, _h, _l in pairs}
JUNCTIONS = {('opening', 'lesson'), ('lesson', 'evidence')}
seen = dict(inside=0, junction=0, other=0)
missing, others = [], []
for name, wrong, helped in (('young', (), ()), ('young', ('1-4-2/evidence/02', '1-4-1/checkA/05'), ('1-4-2/evidence/06',)),
                            ('older', (), ()), ('older', ('3-5-2/checkA/03', '3-5-1/evidence/01'), ()),
                            ('retention', (), ())):
    e, sc = g['build'](name)
    log, inner = [], sc.source

    def source(skill, w, inner=inner, log=log, sc=sc):
        it = inner(skill, w)
        if it is not None:
            log.append((sc.sessions, skill, w['activity'], it['id']))
        return it
    sc.source = source
    st = g['Stepper'](e, sc)
    st.open(sc.g_run(g['SCEN'][name]['sessions']))
    g['play'](st, g['Kid'](wrong, helped))
    for (s1, k1, a1, i1), (s2, k2, a2, i2) in zip(log, log[1:]):
        if s1 != s2 or k1 != k2 or i1 == i2:
            continue
        kind = 'inside' if a1 == a2 else 'junction' if (a1, a2) in JUNCTIONS else 'other'
        seen[kind] += 1
        if kind != 'other' and (i1, i2) not in known:
            missing.append((i1, i2, a1, a2))
        if kind == 'other':
            others.append((a1, a2, i1, i2, cs.fact(by_id[i1]) == cs.fact(by_id[i2])))
expect('4. أزواج عرضها المجدول فعلًا داخل النشاط وبين الافتتاح والدرس ودليل الفهم: كلها مما استكشفه الفحص '
       '(%d داخل النشاط، %d بين الأنشطة المغطاة)' % (seen['inside'], seen['junction']), missing[:5], [])
print('        أزواج بين أنشطة لا يغطيها الفحص، في الجلسة نفسها والمهارة نفسها: %d، منها بالحقيقة نفسها: %d'
      % (len(others), sum(1 for o in others if o[4])))
for o in sorted(set(o[:2] for o in others)):
    print('          %s ثم %s' % o)

# 5) المحتوى قبل الإصلاح
try:
    old = json.loads(subprocess.run(['git', '-C', ROOT, 'show', '17d7b0b:slice-content.json'], check=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout)['items']
except Exception:                                            # noqa: BLE001
    old = None
if old is None:
    print('  تُرك  5. محتوى 17d7b0b غير متاح (لا git): المقارنة لم تُشغَّل')
else:
    p, b, _n = cs.collect(old, cs.load_types(old))
    v = {(x, y) for x, y, _h, _l, _f in cs.violations(p, b)}
    z = sorted(i['id'] for i in old if i['skill'] in SLOTS and zero_step(i))
    expect('5. محتوى 17d7b0b: 65 زوجًا مخالفًا (عدد مقيس لا متوقع)، و5 بنود بقفزة صفرية', [len(v), z],
           [65, ['3-5-2/evidence/19', '3-5-2/gate/14', '3-5-2/lesson/03', '3-5-2/regate/22', '3-5-2/tryfirst/03']])

print('النتيجة: نجح %d من %d' % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
