#!/usr/bin/env python3
"""يختبر فحص تتابع البنود (content_sequence.py) والمحتوى بعد إصلاحه.

    python3 tests/test_content_sequence.py <ملف الخريطة>

الحالات، ونتائجها مكتوبة من القاعدة:
1. المحتوى الحالي: لا زوج بنود متتاليين بالحقيقة نفسها في أي فرع تشغيل، ولا قفزة قيمتها صفر في تسلسل حل معروض.
2. الفحص يكشف: يُزرع في نسخة من المحتوى بند دليل فهم بحقيقة البند الذي قبله، فيجده. ويُزرع بديل دليل فهم بحقيقة
   البند الذي يليه في الموضع التالي، فيجده (البديل يُفحص مع ما يليه).
3. الاستثناء محدود: البند الذي يلي بندًا منقطعًا لا يُعدّ مخالفة، والذي يلي بندًا أُجيب عنه يُعدّ.
6. تأخير بند التقييم: البنود الأصلية التي لا موضع لها هي أواخر المراحل وحدها.
7. ما يبقى بلا علاج بعد تأخير وانقطاع: أوله بديل دائمًا، وفي الوحدة 1-4 وحدها.
4. التغطية: كل بندين متتاليين يعرضهما المجدول فعلًا للمهارة نفسها في الجلسة نفسها، في 13 تشغيلًا كاملًا للشريحة
   (منها عشوائية بالبذرتين 79 و16 من المراجعة 22)، لهما صنف صريح: يضمنه المحتوى (من أزواج الفحص)، أو يعالجه التشغيل
   (دخول الافتتاح ودليل الفهم من نشاط آخر: لا حقيقة مكررة)، أو عرض تعليمي (مسموح)، أو يوسَم (دخول نشاط تقييم).
   انتقال بلا صنف، أو لا يحقق شرط صنفه، إخفاق لا سطر مطبوع.
5. محتوى الالتزام 17d7b0b (قبل الإصلاح) يُخفق في الفحص نفسه: للمقارنة، إن وُجد git.
"""
import copy
import json
import os
import random
import subprocess
import sys
from collections import Counter

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


stuck = set()
pairs, by_id, explored = cs.collect(items, types, stuck)
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
DISPLAY, ASSESS, REMEDY = ('lesson', 'practice'), ('gate', 'short', 'check', 'retention'), ('opening', 'evidence')
STATIC = {('opening', 'lesson'), ('lesson', 'evidence')}


def classify(a1, a2):
    """كل انتقال بين بندين متتاليين للمهارة نفسها في الجلسة نفسها له صنف صريح. ما لا صنف له نقص في التغطية."""
    if a1 == a2 or (a1, a2) in STATIC:
        return 'يضمنه المحتوى'            # من أزواج content_sequence، والمحتوى لا يكرر فيها الحقيقة
    if a2 in REMEDY:
        return 'يعالجه التشغيل'           # دخول الافتتاح أو دليل الفهم من نشاط آخر: يُطلب بند آخر أو بديل (R22-01)
    if a2 in DISPLAY:
        return 'عرض تعليمي'               # دخول بنود الدرس أو التدريب: لا تصنع دليلًا ولا قرارًا، والتكرار فيها مسموح
    if a2 in ASSESS:
        return 'يُؤخَّر أو يوسَم'          # دخول نشاط تقييم من نشاط آخر: البند المكرر يُؤخَّر، وإن لم يوجد له موضع وُسم
    return None


def shown_run(name, sessions, events):
    e, sc = g['build'](name)
    st = g['Stepper'](e, sc)
    st.open(sc.g_run(sessions))
    log = []
    while st.pending is not None:
        item, w = st.pending
        log.append((e.s['current'], item['skill'], w['activity'], item['id'], w.get('fact_just_seen')))
        for ev in events(item, w):
            st.event(st.seq, ev)
    return log


def random_kid(seed, p=0.6):
    rng = random.Random(seed)

    def events(item, w):
        if w['activity'] in DISPLAY:
            return [('end',)]
        ans = item['answer'] if rng.random() < p else item['answer'] + 1
        return [('confirm', ans)] + ([] if w['activity'] in ASSESS else [('end',)])
    return events


runs = [(n, g['SCEN'][n]['sessions'], g['Kid'](w, h).events) for n, w, h in (
    ('young', (), ()), ('young', ('1-4-2/evidence/02', '1-4-1/checkA/05'), ('1-4-2/evidence/06',)),
    ('older', (), ()), ('older', ('3-5-2/checkA/03', '3-5-1/evidence/01'), ()), ('retention', (), ()))]
runs += [('young', 20, random_kid(s)) for s in (79, 16, 1, 2, 3, 4)] + [('older', 20, random_kid(s)) for s in (1, 2)]
kinds, classes, problems = Counter(), Counter(), []
for name, sessions, events in runs:
    log = shown_run(name, sessions, events)
    for (s1, k1, a1, i1, _m1), (s2, k2, a2, i2, m2) in zip(log, log[1:]):
        if s1 != s2 or k1 != k2 or i1 == i2:
            continue
        c = classify(a1, a2)
        classes[c] += 1
        if a1 != a2:
            kinds[(a1, a2, c)] += 1
        same = cs.fact(by_id[i1]) == cs.fact(by_id[i2])
        if c is None:
            problems.append(('بلا صنف', a1, a2, i1, i2))
        elif c == 'يضمنه المحتوى' and (i1, i2) not in known:
            problems.append(('ليس مما استكشفه الفحص', a1, a2, i1, i2))
        elif c == 'يعالجه التشغيل' and same:
            problems.append(('الحقيقة نفسها بلا علاج', a1, a2, i1, i2))
        elif c == 'يُؤخَّر أو يوسَم' and same and m2 != i1:
            problems.append(('الحقيقة نفسها بلا وسم', a1, a2, i1, i2))
expect('4. كل انتقال بين بندين متتاليين للمهارة نفسها في الجلسة نفسها، في %d تشغيلًا كاملًا، له صنف صريح ويحقق شرط '
       'صنفه (%s)' % (len(runs), '، '.join('%s: %d' % (k, v) for k, v in sorted(classes.items(), key=str))),
       problems[:5], [])
for (a1, a2, c), n in sorted(kinds.items()):
    print('        %s ثم %s: %d (%s)' % (a1, a2, n, c))

# 6) تأخير بند التقييم: ما لا موضع له، وما يبقى بلا علاج
# القاعدة (item_layer.Activity._defer): لا يُؤخَّر آخر بند في مرحلته (لا موضع بعده)، ولا بديل بند منقطع. فالمتوقع أن
# البنود الأصلية التي لا تُؤخَّر هي أواخر المراحل وحدها: آخر الأصلية في البوابة وإعادتها، وثاني التعويضية لكل نوع،
# وثالث التحقق القصير، والخانة العاشرة في كل محاولة فحص، وخامس كل جولة احتفاظ. يضمن ذلك المولّد (البند الثالث من
# آخر مرحلته لا يحمل حقيقة آخرها)
src6 = cs.ContentSource(items)
want6 = set()
for skill, ts in types.items():
    for grp in ('gate', 'regate'):
        want6.add(src6.by[(skill, grp, 'gate')][-1]['id'])
        want6.update(src6._typed(skill, grp, 'gate.compensation', t)[1]['id'] for t in ts)
    want6.add(src6.by[(skill, 'short', 'short_check')][2]['id'])
    want6.update(i['id'] for a in 'ABC' for i in src6.by[(skill, 'check' + a, 'check')] if i['slot'] == 10)
    for rnd in (1, 2, 3):
        want6.add([i for i in src6.by[(skill, 'deferred', 'deferred_check')] if i['slot'] == rnd][-1]['id'])
got6 = {i for i, _r, _l in stuck if 'alternate' not in by_id[i]['role']}
expect('6. البنود الأصلية التي لا موضع يُؤخَّر إليه بندها هي أواخر المراحل وحدها (%d بندًا)' % len(want6),
       [sorted(got6 - want6), sorted(want6 - got6)], [[], []])
# ما يبقى: بعد تأخير، ينقطع بند ويأتي بديله بحقيقة البند الذي يليه، ولا موضع يُؤخَّر إليه ذاك. المتوقع من القاعدة:
# أول كل زوج باقٍ بديل، وكله في الوحدة 1-4 (خمس حقائق). وعدده مقيس لا مشتق: 16 زوجًا عند كتابة الاختبار.
# وبعد ت2 يزيد صنف: بند موسوم أُجيب عنه صحيحًا (أداء بعد تعرض مباشر) فطُلب بديله، وبديله بحقيقته، فيوسَم البديل أيضًا
# ويُستكمل ببديل تالٍ أو ينتهي النشاط بلا حكم. أول الزوج فيه قد يكون بندًا أصليًا. بمحتوى الحزمة 4 كانت 7 أزواج
# (والمجموع 23). المولّد يأخذ أزواجه من هذا الفحص، فأعاد اختيار أعداد 29 بند بوابة في الحزمة 5 وبقي منها 3: الخانة
# العاشرة في محاولات فحص 1-4-2 الثلاث، وبديلها يعيد الحقيقة نفسها بقرار الأب (3.6). والأولى صارت 14. الأعداد مقيسة
rest = sorted({(a, b) for a, b, _h, _l, _f in cs.marked(pairs, by_id)})
print('        أزواج تبقى بلا علاج بعد تأخير وانقطاع (البند يوسَم): %d' % len(rest))
after_exposed = sorted({(a, b) for a, b, h, _l, _f in cs.marked(pairs, by_id) if h.startswith('exposed')})
only_cut = [p for p in rest if p not in after_exposed]
expect('7. ما يبقى موسومًا: بعد تأخير وانقطاع، أوله بديل دائمًا، 14 زوجًا. وبعد «أداء بعد تعرض مباشر» (ت2)، ثانيه بديل '
       'خانة الفحص دائمًا، 3 أزواج. وكله في الوحدة 1-4 (الأعداد مقيسة)',
       [sorted({by_id[a]['role'] for a, _b in only_cut}), len(only_cut),
        sorted({by_id[b]['role'] for _a, b in after_exposed}), len(after_exposed),
        sorted({a.split('/')[0] for a, _b in rest})],
       [['check.alternate', 'gate.alternate'], 14, ['check.alternate'], 3, ['1-4-1', '1-4-2']])

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
    print('        أزواج مخالفة في محتوى 17d7b0b بالفحص الحالي: %d (عدد مقيس، يزيد كلما استكشف الفحص فروعًا أكثر)' % len(v))
    expect('5. محتوى 17d7b0b يُخفق: فيه أزواج مخالفة، و5 بنود بقفزة صفرية', [len(v) > 0, z],
           [True, ['3-5-2/evidence/19', '3-5-2/gate/14', '3-5-2/lesson/03', '3-5-2/regate/22', '3-5-2/tryfirst/03']])

print('النتيجة: نجح %d من %d' % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
