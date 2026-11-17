#!/usr/bin/env python3
"""حالات المراجعة الخامسة عشرة بلغة بايثون: الاستعادة المرفوضة لا تغيّر بيانات المستدعي.

    python3 tests/test_r15.py <ملف الخريطة> [--code=مجلد]

النتائج المتوقعة مكتوبة هنا يدويًا. الإعداد نفسه في tests/test_r14.py: 1-4-1 للصغير، والفحص محفوظ بعد S3، وفي
sc.records 13 سجل بند. --code يشغّل الحالات على نسخة أخرى من الكود (مثلًا الالتزام a0c363e).
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


def dump(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False)


def live():
    """حالة الطفل الحالية: المحرك والمجدول وسجلاتهما، ونشاط فحص جارٍ ببند عليه طلب دعم."""
    e, sc = setup()
    sc.begin('follow')
    sc.send(dict(type='check_resumed', skill='1-4-1', check_id='1-4-1/check/1'))
    act = sc.take('check', '1-4-1')
    items = list(sc.carried_items)
    w = act.want()
    it = ContentSource(ITEMS)('1-4-1', w)
    cur = dict(kind='check', skill='1-4-1', act=act.to_dict(), items=items,
               journal=dict(item=it['id'], want=w, answer=it['answer'], assess=True, raw=[['support', 'hint']]))
    return e, sc, cur


def open_into(rec, arr):
    return persist.restore(rec, NET, TYPES, ContentSource(ITEMS), Child(['1-4-1']), item_seconds=secs, records=arr,
                           **NEXT_DAY)


def refused(mutate, label, want_error=persist.Inconsistent):
    """يحضّر سجلًا مرفوضًا، ويستعيده في مصفوفة السجلات الحية نفسها، ثم يقارنها بنسختها قبل الاستعادة."""
    e, sc, cur = live()
    rec = json.loads(json.dumps(persist.snapshot(e, sc, cur)))
    mutate(rec)
    arr = sc.records
    before, rec_before = dump(arr), dump(rec)
    if len(arr) != 13:
        return ['الإعداد: %d سجل بند، والمتوقع 13' % len(arr)]
    bad = []
    try:
        open_into(rec, arr)
        bad.append('%s: قُبل السجل، والمتوقع الرفض' % label)
    except want_error:
        pass
    except Exception as x:                                   # noqa: BLE001
        bad.append('%s: استثناء غير متوقع %r' % (label, x))
    if arr is not sc.records or dump(arr) != before:
        bad.append('%s: سجلات الطفل الحالية صارت %d بعد الرفض، والمتوقع 13 كما كانت حرفًا بحرف' % (label, len(arr)))
    if dump(rec) != rec_before:
        bad.append('%s: تغيّر السجل الممرَّر للاستعادة' % label)
    return bad


def sessions_off(rec):                                      # كما أعاده المراجع: عدد جلسات مخالف وسجلات فارغة
    rec['scheduler']['state']['sessions'] += 1
    rec['records'] = []


def unexplained(rec):                                       # محاولة مختومة بلا حدث يفسّرها
    eng = json.loads(rec['engine'])
    eng['checks']['1-4-1/check/1']['state'] = 'closed'
    rec['engine'] = json.dumps(eng, ensure_ascii=False, sort_keys=True)


def no_records(rec):                                        # سجل بلا records: يُستعمل ما مرّره المستدعي
    rec['records'] = None
    unexplained(rec)


def broken_current(rec):                                    # نشاط جارٍ تالف: استثناء لا Inconsistent
    del rec['current']['act']['check_id']


def case_a():
    return refused(sessions_off, 'عدد الجلسات') + refused(lambda r: (sessions_off(r), r.update(current=None)),
                                                       'عدد الجلسات بلا نشاط جارٍ كما أعاده المراجع')


def case_b():
    return refused(unexplained, 'محاولة غير مفسَّرة') + refused(no_records, 'سجل بلا records')


def case_c():
    return refused(broken_current, 'نشاط جارٍ تالف', want_error=Exception)


def case_d():
    e, sc, cur = live()
    before = copy.deepcopy(sc.records)
    rec = json.loads(json.dumps(persist.snapshot(e, sc, cur)))
    arr = ['قديم']                                           # مصفوفة المستدعي بمحتوى آخر: تُستبدل بعد النجاح
    e2, sc2, notes = open_into(rec, arr)
    bad = []
    if sc2.records is not arr:
        bad.append('مصفوفة المستدعي ليست مصفوفة المجدول المستعاد')
    if len(arr) != 14 or dump(arr[:13]) != dump(before) or not arr[13].get('unsettled'):
        bad.append('بعد الاستعادة: %d سجل، والمتوقع 13 كما حُفظت وسجل البند غير المحسوم' % len(arr))
    arr2 = []
    e3, sc3, notes3 = open_into(json.loads(json.dumps(persist.snapshot(e2, sc2))), arr2)
    if dump(arr2) != dump(arr) or notes3:
        bad.append('الحفظ والاستعادة ثانية: %d سجل، والمتوقع %d بلا فقد ولا تكرار (%r)' % (len(arr2), len(arr), notes3))
    return bad


CASES = [('R15-01-a', True, 'استعادة مرفوضة لاختلاف عدد الجلسات وسجلاتها فارغة: سجلات الطفل الحالية الـ13 تبقى حرفًا '
                            'بحرف، والسجل الممرَّر لا يتغير', case_a),
         ('R15-01-b', False, 'رفض لمحاولة غير مفسَّرة والبند الجاري عليه دعم، بسجلات في اللقطة وبدونها: الضمان نفسه',
          case_b),
         ('R15-01-c', False, 'نشاط جارٍ تالف يرمي استثناءً: الضمان نفسه', case_c),
         ('R15-01-d', False, 'استعادة ناجحة: تُنقل السجلات إلى مصفوفة المستدعي بهويتها ويُضاف البند غير المحسوم مرة '
                             'واحدة، وحفظها واستعادتها لا يفقد ولا يكرر', case_d)]

print('=== حالات المراجعة الخامسة عشرة، بلغة بايثون، على الكود في %s' % os.path.relpath(os.path.abspath(code)))
for cid, rep, title, fn in CASES:
    try:
        bad = fn()
    except Exception as x:                                   # noqa: BLE001
        bad = ['استثناء: %r' % (x,)]
    results.append(not bad)
    print('  %s  %s %s%s' % ('نجح' if not bad else 'أخفق', cid, title, ' [أعاد المراجع إنتاجه]' if rep else ''))
    for b in bad[:4]:
        print('        ' + b)
print('النتيجة: نجح %d من %d' % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
