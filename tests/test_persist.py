#!/usr/bin/env python3
"""سياسة الحفظ والاستعادة (persist.py) بلغة بايثون، بنتائج متوقعة مكتوبة هنا يدويًا.

    python3 tests/test_persist.py <ملف الخريطة>

المسار: 1-4-1 للصغير بمحتوى الشريحة، وسقف 240 ثانية و60 لبند الفحص. ثبت الفهم في S2، وبدأ الفحص في S3 وقُطع
بعد أربع خانات. في S4 يُستأنف الفحص خطوةً خطوة كما ستفعل الواجهة: الخانة الخامسة صحيحة، ثم تُعرض السادسة، ثم
يُغلق التطبيق. البنود المتوقعة من المحتوى بقاعدتها: خانات المحاولة A بترتيب الخانة، وبديل الخانة السادسة.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from transition_engine import Engine, load_network, ROW  # noqa: E402
from scheduler import Scheduler  # noqa: E402
from content_source import ContentSource, load_items  # noqa: E402
from item_layer import EvidenceRun, fold_item, classify  # noqa: E402
import persist  # noqa: E402

MAP = sys.argv[1]
NET = load_network(MAP)
TYPES = {}
for sid, _t, _m, _r, ev, _a in ROW.findall(open(MAP, encoding='utf-8').read()):
    if sid in NET[1] and sid not in TYPES:
        TYPES[sid] = re.findall(r'ف\d', ev)
ITEMS = load_items(os.path.join(os.path.dirname(HERE), 'slice-content.json'))
SLOT = {i['slot']: i['id'] for i in ITEMS if i['skill'] == '1-4-1' and i['group'] == 'checkA' and i['role'] == 'check'}
ALT6 = [i['id'] for i in ITEMS if i['skill'] == '1-4-1' and i['group'] == 'checkA' and i['role'] == 'check.alternate'
        and i['slot'] == 6][0]
results = []


def check(name, cond, detail=''):
    results.append(bool(cond))
    print('  %s  %d. %s' % ('نجح' if cond else 'أخفق', len(results), name))
    if not cond and detail:
        print('        ' + str(detail)[:400])


class Child:
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


def secs(w):
    return 60 if w['activity'] == 'check' else 0


def setup():
    """حتى نهاية S3: الفحص محفوظ بأربع خانات."""
    e = Engine(NET, group='young')
    e.apply(dict(id='d0', type='teacher_open', skill='1-4-1', bypass=['1-3-3'], reason='قرار الشريحة'))
    src, child = ContentSource(ITEMS), Child()
    sc = Scheduler(e, TYPES, src, child, group='young', scope={'1-4-1'}, learning=True, cap=240, item_seconds=secs,
                   records=[])
    sc.search()
    sc.start_session()
    sc.follow_learning()
    return e, sc, src, child


def mid_check(journal_raw):
    """S4 كما ستفعله الواجهة: استئناف الفحص، الخانة الخامسة صحيحة، ثم عرض السادسة وأحداثها الخام حتى الآن."""
    e, sc, src, child = setup()
    sc.begin('follow')
    sc.send(dict(type='check_resumed', skill='1-4-1', check_id='1-4-1/check/1'))
    act = sc.take('check', '1-4-1')
    items = list(sc.carried_items)
    w = act.want()
    it = src('1-4-1', w)
    raw, ans, assess = child(it, w)
    act.feed(classify(fold_item(raw, ans, assess)))
    items.append(it['id'])
    w = act.want()
    it = src('1-4-1', w)
    cur = dict(kind='check', skill='1-4-1', act=act.to_dict(), items=items,
               journal=dict(item=it['id'], want=w, answer=it['answer'], assess=True, raw=journal_raw))
    return e, sc, src, cur


# الاستعادة في يوم أسرة جديد تختم الجلسة المفتوحة (المرحلة 0ج). هذه الحالات كُتبت للجلسة التالية بعد الاستعادة،
# فتمرّ بهذا المسار. والكود السابق للمرحلة 0 لا يعرف today، فلا يُمرَّر له
NEXT_DAY = dict(today=10 ** 6) if 'today' in __import__('inspect').signature(persist.restore).parameters else {}

def reopen(rec):
    child = Child()
    child.known.add('1-4-1')                                # الطفل نفسه: تعلّم المهارة في S2
    src = ContentSource(ITEMS)
    src.served = []
    e, sc, notes = persist.restore(rec, NET, TYPES, src, child, item_seconds=secs, records=[], **NEXT_DAY)
    return e, sc, src, notes


print('=== سياسة الحفظ والاستعادة (persist.py)')

# 1. الإغلاق بعد طلب دعم في الخانة السادسة
e, sc, src, cur = mid_check([['support', 'hint']])
rec = persist.snapshot(e, sc, cur)
e2, sc2, src2, notes = reopen(json.loads(json.dumps(rec)))
entry = sc2.entry('check', '1-4-1')
check('أُغلق التطبيق بعد طلب دعم في الخانة السادسة: يُختم البند بانقطاع «غير محسوم» ومعه الدعم، فيُعامل طلب دعم '
      'بقاعدة 3.1، وتنتهي المحاولة «بطلب دعم». النشاط محفوظ ببنوده الستة، وجلسة S4 مختومة، ولا جلسة جارية',
      notes == [('unsettled_item', '1-4-1', SLOT[6], 'help'), ('current_saved', 'check', '1-4-1'),
                ('session_closed', 'S4')]
      and entry['items'] == [SLOT[k] for k in range(1, 7)] and entry['act']['result'] == 'help'
      and e2.s['current'] is None and sc2.cur is None
      and sc2.records[-1]['unsettled'] and sc2.records[-1]['support_before'] == ['hint'], (notes, entry))
sc2.follow_learning()
res = [x for x in e2.s['log'] if x['type'] == 'independence_result']
check('في الجلسة التالية يُستأنف الفحص ويصدر حدثه: «انتهت بطلب دعم» بالخانات الست، في المحاولة الأصلية',
      [(x['session'], x['check_id'], x['result'], x['items']) for x in res]
      == [('S5', '1-4-1/check/1', 'help', [SLOT[k] for k in range(1, 7)])], res)

# 2. الإغلاق والخانة السادسة معروضة بلا حدث
e, sc, src, cur = mid_check([])
rec = persist.snapshot(e, sc, cur)
e2, sc2, src2, notes = reopen(json.loads(json.dumps(rec)))
entry = sc2.entry('check', '1-4-1')
check('أُغلق التطبيق والخانة السادسة معروضة بلا إجابة: تُختم منقطعة، فيُطلب لها بديل، والمحاولة غير منتهية',
      notes[0] == ('unsettled_item', '1-4-1', SLOT[6], 'interrupted') and entry['act']['done'] is False
      and entry['act']['alt'] == {'6': 1} and entry['act']['correct'] == 5, (notes, entry))
for _ in range(3):
    if not sc2.saved and sc2.satisfied():
        break
    sc2.follow_learning()
ind = [x for x in e2.s['evidence'] if x['kind'] == 'independent' and x['valid']]
want_items = [SLOT[k] for k in range(1, 7)] + [ALT6] + [SLOT[k] for k in range(7, 11)]
check('ثم تكمل الخانات في جلستين تاليتين: بديل السادسة ثم 7 إلى 10، ويُجتاز الفحص بعشر صحيحة. الدليل يحمل البنود '
      'الإحدى عشرة كلها، والسادسة الأصلية معها، ولم يُعرض بند مرتين بعد الاستعادة',
      e2.derive()['1-4-1'] == 'met' and len(ind) == 1 and ind[0]['items'] == want_items
      and len(src2.served) == len(set(src2.served)) and SLOT[6] not in src2.served, (ind, src2.served))

# 3. إجابة مؤكدة خاطئة في بند غير تقييمي، ثم إغلاق
e, sc, src, child = setup()
act = EvidenceRun('1-4-1', TYPES['1-4-1'], round=9)
w = act.want()
cur = dict(kind='evidence', skill='1-4-1', act=act.to_dict(), items=[],
           journal=dict(item='x', want=w, answer=7, assess=False, raw=[['confirm', 6]]))
rec = persist.snapshot(e, sc, cur)
e2, sc2, src2, notes = reopen(json.loads(json.dumps(rec)))
check('إجابة مؤكدة خاطئة في بند دليل فهم، ثم إغلاق قبل نهاية البند: تبقى الإجابة، فيُعدّ البند خطأً لا انقطاعًا',
      notes[0] == ('unsettled_item', '1-4-1', 'x', 'wrong') and sc2.records[-1]['first'] is False
      and sc2.records[-1]['final'] == 'incomplete', notes)

# 4. حدث ينهي البند لا يُحفظ في journal
refused = []
for raw, assess in (([['confirm', 7], ['end']], False), ([['confirm', 7]], True), ([['interrupt']], False)):
    try:
        persist.snapshot(e, sc, dict(cur, journal=dict(cur['journal'], raw=raw, assess=assess)))
        refused.append(False)
    except ValueError:
        refused.append(True)
check('حدث ينهي البند (نهاية، أو تأكيد في بند تقييم، أو انقطاع) لا يُحفظ في journal: يُطوى البند ويُعطى للنشاط في '
      'الحفظ نفسه. والسجل الذي يحمله يُرفض عند صنعه', refused == [True] * 3, refused)

# 5. الحفظ والاستعادة عند حد جلسة، ثم المتابعة: النتيجة نفسها كما لو لم يُغلق التطبيق
def run_through(stop_after):
    e, sc, src, child = setup()
    for k in range(8):
        if k == stop_after:                                 # إغلاق وإعادة فتح عند حد الجلسة
            rec = json.loads(json.dumps(persist.snapshot(e, sc)))
            e, sc, src, notes = reopen(rec)
            again = persist.snapshot(e, sc)
            assert notes == [] and again == rec, 'السجل تغيّر بالاستعادة وحدها'
        if not sc.saved and sc.satisfied():
            break
        sc.follow_learning()
    return persist.snapshot(e, sc)


base = run_through(None)
same = all(run_through(k)['engine'] == base['engine'] for k in (0, 1, 2))
check('سجل حُفظ عند حد جلسة يُستعاد كما هو حرفًا بحرف، وحفظه مرة ثانية يعطي السجل نفسه. والمتابعة بعده تنتهي إلى '
      'حالة المحرك نفسها التي ينتهي إليها التشغيل بلا إغلاق', same)

# 6. سجل يخالف فيه المجدولُ المحرك
e, sc, src, child = setup()
rec = json.loads(json.dumps(persist.snapshot(e, sc)))
bad = []
r1 = json.loads(json.dumps(rec))
r1['scheduler']['state']['saved'][0]['act']['check_id'] = '1-4-1/check/9'
r2 = json.loads(json.dumps(rec))
r2['scheduler']['state']['sessions'] += 1
r3 = json.loads(json.dumps(rec))
r3['scheduler']['state']['saved'].append(r3['scheduler']['state']['saved'][0])
r4 = dict(rec, schema=99)
for r in (r1, r2, r3, r4):
    try:
        reopen(r)
        bad.append(False)
    except persist.Inconsistent:
        bad.append(True)
check('يُرفض السجل الذي يخالف فيه المجدول المحرك: فحص محفوظ لا محاولة له، أو عدد جلسات مختلف، أو مفتاح محفوظ '
      'مرتين، أو نسخة سجل مجهولة', bad == [True] * 4, bad)

print('نجحت الاختبارات كلها: %d' % len(results) if all(results) else 'أخفق اختبار')
sys.exit(0 if all(results) else 1)
