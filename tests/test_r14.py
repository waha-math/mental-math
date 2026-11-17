#!/usr/bin/env python3
"""حالات المراجعة الرابعة عشرة بلغة بايثون: سجل محاولات البنود في اللقطة، وتسوية قرار المعلم عند الاستعادة.

    python3 tests/test_r14.py <ملف الخريطة> [--code=مجلد]

النتائج المتوقعة مكتوبة هنا يدويًا. المسار نفسه في tests/test_persist.py: 1-4-1 للصغير بمحتوى الشريحة، وسقف 240
ثانية و60 لبند الفحص، والفحص محفوظ بأربع خانات بعد S3. الملاحظة الثالثة (Saver) في اختبار المتصفح.
--code يشغّل الحالات على نسخة أخرى من الكود (مثلًا الالتزام 11419f8).
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
from scheduler import Scheduler  # noqa: E402
from content_source import ContentSource  # noqa: E402
from item_layer import fold_item, indicators, RetentionRun  # noqa: E402
import persist  # noqa: E402

# الاستعادة في يوم أسرة جديد تختم الجلسة المفتوحة (المرحلة 0ج). هذه الحالات كُتبت للجلسة التالية بعد الاستعادة،
# فتمرّ بهذا المسار. والكود السابق للمرحلة 0 لا يعرف today، فلا يُمرَّر له
NEXT_DAY = dict(today=10 ** 6) if 'today' in __import__('inspect').signature(persist.restore).parameters else {}

MAP = args[0]
NET = load_network(MAP)
TYPES = {'1-4-1': ['ف1', 'ف3']}                             # من صف المهارة في الخريطة
ITEMS = json.load(open(os.path.join(HERE, '..', 'slice-content.json'), encoding='utf-8'))['items']
results = []


class Child:
    def __init__(self, known=()):
        self.known = set(known)

    def __call__(self, item, want):
        a = want['activity']
        if a in ('lesson', 'practice'):
            if a == 'lesson':
                self.known.add(item['skill'])
            return 'correct'
        assess = a in ('gate', 'short', 'check', 'retention')
        ans = item['answer'] if item['skill'] in self.known else item['answer'] + 1
        return [('confirm', ans)] + ([] if assess else [('end',)]), item['answer'], assess


def secs(w):
    return 60 if w['activity'] == 'check' else 0


def setup():
    e = Engine(NET, group='young')
    e.apply(dict(id='d0', type='teacher_open', skill='1-4-1', bypass=['1-3-3'], reason='قرار الشريحة'))
    src = ContentSource(ITEMS)
    sc = Scheduler(e, TYPES, src, Child(), group='young', scope={'1-4-1'}, learning=True, cap=240, item_seconds=secs,
                   records=[])
    sc.search()
    sc.start_session()
    sc.follow_learning()
    return e, sc


def reopen(rec):
    src = ContentSource(ITEMS)
    return persist.restore(json.loads(json.dumps(rec)), NET, TYPES, src, Child(['1-4-1']), item_seconds=secs, records=[],
                           **NEXT_DAY)


def crafted():
    """أربعة سجلات بنود بطي أحداث خام كما تطويها الواجهة: إجابة خاطئة، ونجاح بمساعدة بعد خطأ، وانقطاع بعد طلب دعم،
    ونجاح بمساعدة من أول إجابة."""
    out = []
    for raw, ans, assess in (([('confirm', 6)], 7, True),
                             ([('confirm', 6), ('support', 'hint'), ('confirm', 7), ('end',)], 7, False),
                             ([('support', 'extra_model'), ('interrupt',)], 7, False),
                             ([('support', 'someone'), ('confirm', 7), ('end',)], 7, False)):
        out.append(dict(fold_item(raw, ans, assess), skill='1-4-1', activity='evidence', role='evidence', item='x'))
    return out


def same(a, b):
    return json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False)


def case_01a():
    e, sc = setup()
    sc.records.extend(crafted())
    before = copy.deepcopy(sc.records)
    e2, sc2, _ = reopen(persist.snapshot(e, sc))
    e3, sc3, _ = reopen(persist.snapshot(e2, sc2))
    bad = []
    kinds = dict(wrong=sum(1 for r in before if r['first'] is False),
                 supported_ok=sum(1 for r in before if r['support_before'] and r['final'] == 'correct'),
                 cut_after_support=sum(1 for r in before if r['status'] == 'interrupted' and r['support_before']))
    if not (kinds['wrong'] >= 1 and kinds['supported_ok'] >= 1 and kinds['cut_after_support'] >= 1):
        bad.append('الإعداد لا يحمل الأنواع المطلوبة: %r' % kinds)
    for label, recs in (('بعد الاستعادة', sc2.records), ('بعد الحفظ والاستعادة مرة ثانية', sc3.records)):
        if not same(recs, before):
            bad.append('%s: %d سجل بند، والمتوقع %d كما قبل الحفظ' % (label, len(recs or []), len(before)))
        elif not same(indicators(recs), indicators(before)):
            bad.append('%s: المؤشرات تغيّرت' % label)
    return bad


def case_01b():
    e, sc = setup()
    sc.begin('follow')
    sc.send(dict(type='check_resumed', skill='1-4-1', check_id='1-4-1/check/1'))
    act = sc.take('check', '1-4-1')
    items = list(sc.carried_items)
    src = ContentSource(ITEMS)
    w = act.want()
    it = src('1-4-1', w)
    before = copy.deepcopy(sc.records)
    cur = dict(kind='check', skill='1-4-1', act=act.to_dict(), items=items,
               journal=dict(item=it['id'], want=w, answer=it['answer'], assess=True, raw=[['support', 'hint']]))
    e2, sc2, notes = reopen(persist.snapshot(e, sc, cur))
    first = copy.deepcopy(sc2.records)
    e3, sc3, notes3 = reopen(persist.snapshot(e2, sc2))
    bad = []
    if len(first) != len(before) + 1 or not same(first[:-1], before):
        bad.append('الاستعادة الأولى: %d سجل، والمتوقع ما قبل الإغلاق (%d) وسجل البند الجاري' % (len(first), len(before)))
    else:
        u = first[-1]
        if not (u.get('unsettled') and u['status'] == 'interrupted' and u['support_before'] == ['hint']
                and u['item'] == it['id']):
            bad.append('سجل البند غير المحسوم ليس كما يُتوقع: %r' % u)
    if not same(sc3.records, first):
        bad.append('الاستعادة الثانية: %d سجل، والمتوقع %d بلا فقد ولا تكرار للبند غير المحسوم' % (
            len(sc3.records or []), len(first)))
    if notes3:
        bad.append('الاستعادة الثانية أعادت معالجة: %r' % notes3)
    return bad


def check_state(e, cid):
    return e.s['checks'][cid]['state']


def case_02a(extra=False):
    e, sc = setup()
    cid = '1-4-1/check/1'
    other = None
    if extra:                                               # نشاط آخر محفوظ لا علاقة له بالقرار
        ret = RetentionRun('1-4-1', 1)
        ret.shown['retention'] = 1
        other = dict(kind='retention', skill='1-4-1', act=ret.to_dict(), items=['1-4-1/deferred/01'])
        sc.saved.append(other)
    r = e.apply(dict(id='t1', type='check_abandoned', check_id=cid, reason='قرار المعلم'))
    if not r['ok']:
        return ['الإعداد: رُفض ترك المحاولة (%s)' % r.get('code')]
    try:
        e2, sc2, notes = reopen(persist.snapshot(e, sc))
    except persist.Inconsistent as x:
        return ['رُفض السجل: %s' % x]
    bad = []
    want_saved = [other] if extra else []
    if not same(sc2.saved, want_saved):
        bad.append('المخزن بعد الاستعادة: %r، والمتوقع %r' % ([(c['kind'], c['skill']) for c in sc2.saved],
                                                           [(c['kind'], c['skill']) for c in want_saved]))
    if sc2.log[-1] != [3, 'carry_dropped:check_abandoned', '1-4-1'] or ['reconciled', cid, 'check_abandoned'] not in [
            list(n) for n in notes]:
        bad.append('لم تُكتب التسوية في سجل المجدول والملاحظات: %r %r' % (sc2.log[-1], notes))
    if check_state(e2, cid) != 'abandoned':
        bad.append('المحاولة في المحرك ليست متروكة')
    if not extra:
        sc2.follow_learning()
        started = [x['check_id'] for x in e2.s['log'] if x['type'] == 'check_started']
        if started != [cid, '1-4-1/check/2']:
            bad.append('الجلسة التالية: محاولات %r، والمتوقع بدء المحاولة الثانية' % started)
    return bad


def case_02b():
    e, sc = setup()
    cid = '1-4-1/check/1'
    r = e.apply(dict(id='t1', type='invalidate_session', target='S3'))
    if not r['ok'] or check_state(e, cid) != 'needs_restart':
        return ['الإعداد: إبطال S3 لم يجعل المحاولة تحتاج إعادة بدء']
    try:
        e2, sc2, notes = reopen(persist.snapshot(e, sc))
    except persist.Inconsistent as x:
        return ['رُفض السجل: %s' % x]
    sc2.follow_learning()
    bad = []
    if [x[1] for x in sc2.log if x[1].startswith('carry_dropped')] != ['carry_dropped:check_state']:
        bad.append('النشاط المحفوظ لم يُسقط عند استئنافه: %r' % sc2.log[-3:])
    if check_state(e2, cid) != 'needs_restart' or sc2.saved:
        bad.append('المحاولة أو المخزن بعد الجلسة التالية ليسا كما يُتوقع')
    if [x for x in e2.s['log'] if x['type'] == 'check_started' and x['check_id'] != cid]:
        bad.append('بدأت محاولة جديدة قبل أن يترك المعلم المحاولة التي تحتاج إعادة بدء')
    return bad


def case_02e():
    """النشاط الجاري نفسه (لا المحفوظ) هو المحاولة التي تركها المعلم قبل الحفظ."""
    e, sc = setup()
    cid = '1-4-1/check/1'
    sc.begin('follow')
    sc.send(dict(type='check_resumed', skill='1-4-1', check_id=cid))
    act = sc.take('check', '1-4-1')
    items = list(sc.carried_items)
    w = act.want()
    it = ContentSource(ITEMS)('1-4-1', w)
    cur = dict(kind='check', skill='1-4-1', act=act.to_dict(), items=items,
               journal=dict(item=it['id'], want=w, answer=it['answer'], assess=True, raw=[]))
    e.apply(dict(id='t1', type='check_abandoned', check_id=cid, reason='قرار المعلم'))
    try:
        e2, sc2, notes = reopen(persist.snapshot(e, sc, cur))
        e3, sc3, notes3 = reopen(persist.snapshot(e2, sc2))
    except persist.Inconsistent as x:
        return ['رُفض السجل: %s' % x]
    bad = []
    if [n[0] for n in notes] != ['unsettled_item', 'current_saved', 'reconciled', 'session_closed'] or sc2.saved:
        bad.append('الاستعادة الأولى: %r، والمخزن %r' % (notes, sc2.saved))
    if notes3 or persist.snapshot(e3, sc3) != persist.snapshot(e2, sc2):
        bad.append('الاستعادة الثانية غيّرت اللقطة: %r' % notes3)
    return bad


def case_02d():
    e, sc = setup()
    cid = '1-4-1/check/1'
    rec = json.loads(json.dumps(persist.snapshot(e, sc)))
    out = []
    for state in ('abandoned', 'closed'):                   # حالة لا يفسّرها حدث في سجل المحرك
        r = copy.deepcopy(rec)
        eng = json.loads(r['engine'])
        eng['checks'][cid]['state'] = state
        r['engine'] = json.dumps(eng, ensure_ascii=False, sort_keys=True)
        try:
            reopen(r)
            out.append('سجل فيه محاولة %s بلا حدث يفسّرها قُبل' % state)
        except persist.Inconsistent:
            pass
    return out


CASES = [('R14-01-a', True, 'سجل محاولات البنود في اللقطة: إجابة خاطئة، ونجاح بمساعدة، وانقطاع بعد طلب دعم. السجلات '
                            'والمؤشرات بعد الاستعادة، وبعد حفظ المستعادة واستعادتها، هي نفسها قبل الحفظ', case_01a),
         ('R14-01-b', True, 'بند «غير محسوم» بعد طلب دعم: يُنشأ سجله في الاستعادة الأولى، ويبقى في الثانية مرة واحدة، '
                            'ولا تُعاد معالجته', case_01b),
         ('R14-02-a', True, 'المعلم ترك المحاولة المحفوظة ثم حُفظ فورًا: الاستعادة تُسقط النشاط المتروك وتكتب إسقاطه، '
                            'والمحاولة متروكة في المحرك، والجلسة التالية تبدأ المحاولة الثانية', case_02a),
         ('R14-02-b', False, 'إبطال جلسة أسهمت في المحاولة المحفوظة ثم الحفظ: يُستعاد السجل، ويُسقط النشاط عند استئنافه، '
                             'ولا تبدأ محاولة جديدة قبل ترك المعلم', case_02b),
         ('R14-02-c', False, 'الترك لا يمسّ نشاطًا محفوظًا آخر: فحص احتفاظ محفوظ يبقى كما هو', lambda: case_02a(True)),
         ('R14-02-e', False, 'النشاط الجاري نفسه هو المحاولة التي تركها المعلم قبل الحفظ: يُضم إلى المخزن ثم يُسوّى في '
                             'الاستعادة الأولى، والاستعادة الثانية لا تغيّر اللقطة', case_02e),
         ('R14-02-d', False, 'سجل فيه محاولة متروكة أو مختومة لا يفسّرها حدث في سجل المحرك يبقى مرفوضًا', case_02d)]

print('=== حالات المراجعة الرابعة عشرة، بلغة بايثون، على الكود في %s' % os.path.relpath(os.path.abspath(code)))
for cid, rep, title, fn in CASES:
    try:
        bad = fn()
    except Exception as x:                                   # noqa: BLE001
        bad = ['استثناء: %r' % (x,)]
    results.append(not bad)
    print('  %s  %s %s%s' % ('نجح' if not bad else 'أخفق', cid, title, ' [أعاد المراجع إنتاجه]' if rep else ''))
    for b in bad[:3]:
        print('        ' + b)
print('النتيجة: نجح %d من %d' % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
