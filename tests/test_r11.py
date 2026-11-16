#!/usr/bin/env python3
"""حالات المراجعة الحادية عشرة بلغة بايثون: ترحيل الحالة القديمة في المحرك، وبقاء الفحص المحفوظ في المجدول.

    python3 tests/test_r11.py <ملف الخريطة> [--code=مجلد]

حالات المحرك ونتائجها المتوقعة في tests/r11_cases.json، والحالات المحفوظة القديمة في tests/r11_fixtures.json (صنعها
محرك الالتزام 2509126، ومعها النص نفسه بعد قراءته وحفظه بمحرك 16b124a). كل حالة تُفحص بثلاثة طرق: الاستعادة المباشرة،
والاستعادة بعد المرور بـ 16b124a، وإعادة تشغيل السجل. والحكم واحد فيها، والحالة المصححة ثابتة إذا حُفظت واستُعيدت.
حالتا المجدول هنا، ونتائجهما المتوقعة مكتوبة صراحة، على المجدول المرجعي. ومجدول التطبيق يطابقه فيهما في متجهات
المجدول (app/test_scheduler_conformance.mjs). --code يشغّل الحالات على نسخة أخرى من الكود.
"""
import copy
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
args = [a for a in sys.argv[1:] if not a.startswith('--code')]
code = next((a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--code=')), os.path.dirname(HERE))
sys.path.insert(0, os.path.abspath(code))
from transition_engine import Engine, load_network, ROW  # noqa: E402
from scheduler import Scheduler, Capped  # noqa: E402
from content_source import ContentSource, load_items  # noqa: E402

MAP = args[0]
NET = load_network(MAP)
CASES = json.load(open(os.path.join(HERE, 'r11_cases.json'), encoding='utf-8'))
FIX = json.load(open(os.path.join(HERE, 'r11_fixtures.json'), encoding='utf-8'))
OLD, VIA = FIX['states'], FIX['via_16b124a']
results = []


def query(e, key):
    kind, arg = key.split(':', 1)
    if kind == 'state':
        return e.derive()[arg]
    if kind == 'check':
        return e.s['checks'][arg]['state']
    if kind == 'restart_reason':
        return e.s['checks'][arg].get('restart_reason')
    if kind == 'check_invalid':
        return bool(e.s['checks'][arg].get('invalid'))
    if kind == 'valid_independent':
        return len(e.valid_evidence(arg, 'independent'))
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


def run_steps(e, steps, tag):
    for n, st in enumerate(steps):
        ev = dict(st['ev'], id='%s%d' % (tag, n + 1))
        res = e.apply(ev)
        if 'ok' in st and not res['ok']:
            return ['%s رُفض (%s)، والمتوقع قبوله' % (ev['type'], res.get('code'))]
        if 'code' in st and (res['ok'] or res.get('code') != st['code']):
            return ['%s: %s، والمتوقع الرفض بـ %s' % (ev['type'], 'قُبل' if res['ok'] else res.get('code'), st['code'])]
        if st.get('refused') and res['ok']:
            return ['%s قُبل، والمتوقع رفضه' % ev['type']]
    return []


def verdict(e):
    """الحكم الذي يُقارن بين طريقي الاسترجاع: حالات المهارات كلها، والأدلة الصالحة، وحالات المحاولات."""
    return (e.derive(), sorted((x['skill'], x['kind'], x['session']) for x in e.s['evidence'] if x['valid']),
            {k: c['state'] for k, c in e.s['checks'].items()})


def stable(e, label):
    """ثبات الترحيل (المراجعة 12): الحالة المصححة تُحفظ وتُستعاد مرتين، فلا يتغير نصها ولا حكمها ولا يُضاف حدث."""
    t1 = e.dump()
    t2 = Engine.restore(NET, t1).dump()
    t3 = Engine.restore(NET, t2).dump()
    return [] if t1 == t2 == t3 else [label + ': الحفظ ثم الاستعادة غيّر الحالة المصححة']


def engine_case(c):
    text = OLD[c['id']]
    paths = [('بعد الاستعادة', Engine.restore(NET, text)),
             ('بعد قراءتها وحفظها بمحرك 16b124a ثم الاستعادة', Engine.restore(NET, VIA[c['id']]))]
    if not c.get('no_log'):
        paths.append(('بعد إعادة تشغيل السجل', Engine.replay(NET, json.loads(text)['log'])))
    bad = []
    for label, e in paths:
        bad += compare(e, c['expect'], label)
    for label, e in paths[1:]:
        if verdict(e) != verdict(paths[0][1]):
            bad.append('الحكم %s يخالف حكم الاستعادة المباشرة' % label)
    for label, e in paths[:2]:
        bad += stable(e, label)
    if bad or 'then' not in c:
        return bad
    for label, e in paths:
        b = run_steps(e, c['then'], 't')
        bad += [label + '، المتابعة: ' + x for x in b] or compare(e, c['expect_then'], label + ' ثم المتابعة')
    for label, e in paths[1:]:
        if not bad and verdict(e) != verdict(paths[0][1]):
            bad.append('بعد المتابعة: الحكم %s يخالف حكم الاستعادة المباشرة' % label)
    return bad


# ---------------------------------------------------------------- المجدول مع المحرك
TYPES = {}
for sid, _t, _m, _r, ev, _a in ROW.findall(open(MAP, encoding='utf-8').read()):
    if sid in NET[1] and sid not in TYPES:
        TYPES[sid] = re.findall(r'ف\d', ev)
ITEMS = load_items()


class Child:
    """يجيب صحيحًا عن مهارة رأى درسها، وخطأً قبل ذلك."""
    def __init__(self):
        self.known = set()

    def __call__(self, item, want):
        a = want['activity']
        if a in ('lesson', 'practice'):
            if a == 'lesson':
                self.known.add(item['skill'])
            return 'correct'
        assess = a in ('gate', 'short', 'check', 'retention')
        ans = item['answer'] if item['skill'] in self.known else item['answer'] + 1
        return [('confirm', ans)] + ([] if assess else [('end',)]), item['answer'], assess


def cut_check():
    """1-4-1 للصغير، والسقف يسع 5 بنود فحص: الفهم يثبت في S3 (اليوم 2)، والفحص يبدأ في S4 (اليوم 3) ويُقطع بعد
    خانته الخامسة، فيُحفظ في المجدول."""
    e = Engine(NET, group='young')
    e.apply(dict(id='d0', type='teacher_open', skill='1-4-1', bypass=['1-3-3'], reason='قرار الشريحة في 10.2'))
    src = ContentSource(ITEMS)
    sc = Scheduler(e, TYPES, src, Child(), group='young', scope={'1-4-1'}, learning=True, cap=300,
                   item_seconds=lambda w: 60 if w['activity'] in ('check', 'lesson') else 0)
    sc.run(max_sessions=4)
    return e, sc, src


def saved(sc, s):
    c = sc.carry if sc.carry and sc.carry['skill'] == s else getattr(sc, 'parked', {}).get(s)
    return copy.deepcopy(c)


def session_at(sc, day):
    sc.sessions += 1
    sc.cur, sc.elapsed = 'S%d' % sc.sessions, 0
    sc.send(dict(type='session_start', session=sc.cur, kind='follow', day=day))


def teach_session(sc):
    """جلسة متابعة فيها الحصة التعليمية وحدها. السقف إن بلغه نشاط يختم الجلسة كما في المجدول."""
    sc.begin('follow')
    cur = sc.cur
    try:
        sc.teach()
    except Capped:
        pass
    sc.end()
    return cur


def sched_a():
    e, sc, src = cut_check()
    k, bad = '1-4-1/check/1', []
    before = saved(sc, '1-4-1')
    if not (before and before['kind'] == 'check' and len(before['items']) == 5 and e.s['checks'][k]['state'] == 'pending'
            and [e.s['sessions'][x]['day'] for x in e.s['order']] == [0, 1, 2, 3]):
        return ['الإعداد: لم يُقطع الفحص بعد خانته الخامسة في اليوم 3 كما يُفترض']
    first5 = list(before['items'])
    session_at(sc, 2)                                       # يوم الفهم نفسه: التاريخ يُعلَّم ثم يؤكده الوالد
    sc.send(dict(type='date_confirmed', target=sc.cur))
    sc.teach()
    if saved(sc, '1-4-1') != before:
        bad.append('رفض check_same_day غيّر النشاط المحفوظ أو حذفه')
    if e.s['checks'][k]['state'] != 'pending' or e.s['sessions'][sc.cur]['teach'] != 0:
        bad.append('المحرك قبِل شيئًا في الجلسة ذات التاريخ غير المتسق')
    sc.end()
    cur = teach_session(sc)                                 # اليوم 4
    ind = [x for x in e.s['evidence'] if x['kind'] == 'independent' and x['valid']]
    flow = [(x['type'], x['session']) for x in e.s['log'] if x['type'] in ('check_resumed', 'independence_result')]
    served_checks = [i for i in src.served if '/check' in i]
    if flow != [('check_resumed', cur), ('independence_result', cur)]:
        bad.append('الجلسة الصالحة التالية: أحداث الفحص %r، والمتوقع استئنافه ونتيجته فيها' % flow)
    if not ind or ind[0]['items'][:5] != first5 or len(ind[0]['items']) != 10 or len(set(ind[0]['items'])) != 10:
        bad.append('دليل الاستقلال لا يبدأ بالخانات الخمس المحفوظة، أو ليس فيه عشر خانات مختلفة')
    if len(served_checks) != 10 or len(src.served) != len(set(src.served)):
        bad.append('عُرض بند فحص مرتين أو نقص منه: %d بند فحص' % len(served_checks))
    if e.derive()['1-4-1'] != 'met' or sc.carry is not None or getattr(sc, 'parked', {}) or sc.refused:
        bad.append('الحالة بعد الاستكمال: %s، وما زال نشاط محفوظ أو اقتراح مرفوض' % e.derive()['1-4-1'])
    return bad


def sched_b():
    e, sc, src = cut_check()
    k = '1-4-1/check/1'
    e.apply(dict(id='t1', type='check_abandoned', check_id=k, reason='قرار المعلم'))
    teach_session(sc)                                       # اليوم 4: المحاولة تُركت، فالرفض نهائي
    bad = []
    if ('carry_dropped:check_state' not in [x[1] for x in sc.log]):
        bad.append('لم يُسجَّل إسقاط النشاط بسبب check_state')
    teach_session(sc)                                       # المحاولة الجديدة قطعها السقف أيضًا: تكتمل في التالية
    if saved(sc, '1-4-1') is not None:
        bad.append('بقي نشاط محاولة تُركت محفوظًا')
    if e.s['checks'].get('1-4-1/check/2', {}).get('state') != 'closed' or e.derive()['1-4-1'] != 'met' or sc.refused:
        bad.append('لم تُبدأ محاولة جديدة وتُجتز')
    return bad


SCHED = [
    dict(id='R11-01-a', reproduced_by_reviewer=True, run=sched_a,
         title='فحص قطعه السقف بعد خمس خانات، ثم جلسة بتاريخ أسبق من يوم الفهم أكّده الوالد: يُرفض الاستئناف '
               '(check_same_day) ولا يتغير النشاط المحفوظ. وفي الجلسة الصالحة التالية يُستكمل من الخانة السادسة، '
               'ويُجتاز بعشر خانات مختلفة، بلا تعليق دائم'),
    dict(id='R11-01-b', reproduced_by_reviewer=False, run=sched_b,
         title='رفض نهائي: المعلم ترك المحاولة المحفوظة. يُسقط المجدول نشاطها (check_state)، ويبدأ محاولة جديدة '
               'في الجلسة نفسها، تكتمل في التالية'),
]


def report(c, bad):
    results.append(not bad)
    print('  %s  %s %s%s' % ('نجح' if not bad else 'أخفق', c['id'], c['title'],
                             ' [أعاد المراجع إنتاجه]' if c.get('reproduced_by_reviewer') else ''))
    for b in bad[:3]:
        print('        ' + b)


print('=== حالات المراجعة الحادية عشرة، بلغة بايثون، على الكود في %s' % os.path.relpath(os.path.abspath(code)))
print('المجدول مع المحرك:')
for c in SCHED:
    try:
        bad = c['run']()
    except Exception as x:                                   # noqa: BLE001
        bad = ['استثناء: %r' % (x,)]
    report(c, bad)
print('ترحيل الحالة القديمة في المحرك:')
for c in CASES['engine']:
    try:
        bad = engine_case(c)
    except Exception as x:                                   # noqa: BLE001
        bad = ['استثناء: %r' % (x,)]
    report(c, bad)
print('النتيجة: نجح %d من %d' % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
