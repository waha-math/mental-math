#!/usr/bin/env python3
"""بطاقة «كيف حسبتها؟» في فحص 3-5-3 (الخريطة 13.27 و10.2): بعد الخانة 8، ثلاث بطاقات، يُسجَّل الاختيار بلا تصحيح.

    python3 tests/test_how.py <ملف الخريطة> [--write]

القاعدة، مكتوبة قبل التشغيل:
- الحدث ('how', back أو up أو other) مقبول لبند يحمل how وحده، مرة واحدة، قبل التأكيد. وغير ذلك مرفوض ولا يتغير شيء.
- الاختيار يُحفظ في سجل البند (evidence.how) ولا أثر له في غيره: الحقول المطوية والنتيجة كما بلا بطاقة.
- مسار كامل لطفل يمضي يومًا بعد يوم حتى يُجتاز فحص 3-5-3: مع البطاقة وبلاها، المحرك وحالة المجدول واحدان، والسجلات
  واحدة إلا الحقل how في سجل بند الخانة 8 وحده.

--write يكتب tests/how_tape.json: الحالة الدائمة للمسار مع البطاقة. test_how.mjs يعيد المسار ويطابقها.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WRITE = '--write' in sys.argv
MAP = [a for a in sys.argv[1:] if not a.startswith('--')][0]
src = open(os.path.join(HERE, 'test_phase0.py'), encoding='utf-8').read()
g = {'__file__': os.path.join(HERE, 'test_phase0.py'), '__name__': 'phase0_helpers'}
sys.argv = [g['__file__'], MAP]
exec(compile(src[:src.index("\nprint('=== ")], 'test_phase0.py', 'exec'), g)
from stepper import Stepper  # noqa: E402
from item_layer import fold_item, classify, evidence  # noqa: E402

Engine, Scheduler, ContentSource, NET, TYPES, ITEMS, Kid, persist, final, dump = (g[k] for k in (
    'Engine', 'Scheduler', 'ContentSource', 'NET', 'TYPES', 'ITEMS', 'Kid', 'persist', 'final', 'dump'))
results = []


def check(title, got, want):
    ok = dump(got) == dump(want)
    results.append(ok)
    print('  %s  %d. %s' % ('نجح' if ok else 'أخفق', len(results), title))
    if not ok:
        print('        المتوقع %s\n        الناتج  %s' % (dump(want)[:500], dump(got)[:500]))


print('=== بطاقة «كيف حسبتها؟»، المرجع')
HOW_ITEMS = sorted(i['id'] for i in ITEMS if i.get('how'))
check('المحتوى: البطاقة على بند الخانة 8 وبديله في محاولات فحص 3-5-3 الثلاث، ولا غيرها',
      [HOW_ITEMS, sorted({(i['skill'], i['slot'], i['role']) for i in ITEMS if i.get('how')})],
      [['3-5-3/checkA/15', '3-5-3/checkA/16', '3-5-3/checkB/15', '3-5-3/checkB/16', '3-5-3/checkC/15', '3-5-3/checkC/16'],
       [('3-5-3', 8, 'check'), ('3-5-3', 8, 'check.alternate')]])

# ---------------------------------------------------------------- 1) عقد الحدث
BY = {i['id']: i for i in ITEMS}
st = Stepper(None, None)
W = dict(activity='check', role='check', slot=8, alternate=0, attempt='A')


def allowed(item, ev, raw=(), w=W):
    st.pending, st.raw = (BY[item], w), list(raw)
    return st.allowed(ev)


plain8 = next(i['id'] for i in ITEMS if i['skill'] == '3-5-3' and i['role'] == 'check' and i['slot'] == 7)
check('عقد الحدث: مقبول لبند يحمل البطاقة بإحدى البطاقات الثلاث، ومرفوض لغيره أو ببطاقة غريبة أو مرة ثانية أو في بند عرض',
      [allowed('3-5-3/checkA/15', ('how', 'back')), allowed('3-5-3/checkA/15', ('how', 'up')),
       allowed('3-5-3/checkA/15', ('how', 'other')), allowed(plain8, ('how', 'up')),
       allowed('3-5-3/checkA/15', ('how', 'sideways')), allowed('3-5-3/checkA/15', ('how',)),
       allowed('3-5-3/checkA/15', ('how', 'up'), [('how', 'back')]),
       allowed('3-5-3/checkA/15', ('how', 'up'), w=dict(activity='practice', pos=0))],
      [None, None, None, 'بطاقة «كيف حسبتها؟» ليست لهذا البند', 'بطاقة غير معروفة', 'بطاقة غير معروفة',
       'البطاقة مرة واحدة قبل التأكيد', 'بند العرض يقبل الإنهاء وحده'])

# ---------------------------------------------------------------- 2) السجل
it = BY['3-5-3/checkA/15']
cases = []
for raw in ([('confirm', it['answer'])], [('confirm', it['answer'] + 1)], [('support', 'requested'), ('interrupt',)]):
    with_how = [('how', 'up')] + raw
    cases.append([fold_item(with_how, it['answer'], True) == fold_item(raw, it['answer'], True),
                  classify(fold_item(with_how, it['answer'], True)), evidence(with_how, it['answer']).get('how'),
                  'how' in evidence(raw, it['answer'])])
check('السجل: البطاقة تُحفظ في evidence.how، والحقول المطوية والتصنيف كما بلا بطاقة (صحيح، خطأ، طلب مساعدة)',
      cases, [[True, 'correct', 'up', False], [True, 'wrong', 'up', False], [True, 'help', 'up', False]])


# ---------------------------------------------------------------- 3) مسار كامل حتى اجتياز فحص 3-5-3
class Run:
    def __init__(self, how):
        self.how, self.hits, self.kid = how, [], Kid()
        self.e = Engine(NET, group='older')
        for k, (skill, bypass) in enumerate([('3-5-1', ['3-3-2', '3-2-3']), ('3-5-2', ['3-2-1', '3-3-1', '2-5-2'])]):
            self.e.apply(dict(id='d%d' % k, type='teacher_open', skill=skill, bypass=bypass, reason='قرار الشريحة في 10.2'))
        self.sc = Scheduler(self.e, TYPES, ContentSource(ITEMS), None, group='older', scope={'3-5-1', '3-5-2', '3-5-3'},
                            learning=True, cap=600, item_seconds=lambda w: 45, records=[], retention=True, day_cap=3000)

    def go(self, days=60):
        for d in range(days):
            self.sc.today = d
            st = Stepper(self.e, self.sc)
            st.open(self.sc.g_session())
            while st.pending is not None:
                item, w = st.pending
                evs = list(self.kid.events(item, w))
                if self.how and item.get('how'):
                    self.hits.append(item['id'])
                    evs = [('how', self.how)] + evs
                for ev in evs:
                    if st.event(st.seq, ev) == 'rejected':
                        raise AssertionError(st.reject)
            if any(x[1] == 'check_pass' and x[2] == '3-5-3' for x in self.sc.log):
                return self
        raise AssertionError('لم يُجتز فحص 3-5-3 في %d يومًا' % days)


a, b = Run('up').go(), Run(None).go()
fa, fb = json.loads(dump(final(a.e, a.sc))), json.loads(dump(final(b.e, b.sc)))
ra, rb = fa.pop('records'), fb.pop('records')
diff = [(x.get('item'), x.get('how')) for x, y in zip(ra, rb) if x != y]
strip = [{k: v for k, v in x.items() if k != 'how'} for x in ra]
check('مسار حتى اجتياز فحص 3-5-3: البطاقة عُرضت مرة، والمحرك والمجدول واحدان معها وبلاها، والسجلات واحدة إلا how في بند الخانة 8',
      [a.hits, fa == fb, len(ra) == len(rb), diff, strip == rb],
      [['3-5-3/checkA/15'], True, True, [('3-5-3/checkA/15', 'up')], True])
fa['records'] = ra
if WRITE:
    json.dump(dict(final=fa, hits=a.hits), open(os.path.join(HERE, 'how_tape.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, sort_keys=True)
    print('كُتب tests/how_tape.json')
tape = json.load(open(os.path.join(HERE, 'how_tape.json'), encoding='utf-8'))
check('الشريط المحفوظ يطابق المسار الآن', [dump(tape['final']) == dump(fa), tape['hits']], [True, a.hits])

ok = sum(results)
print('النتيجة: نجح %d من %d' % (ok, len(results)))
sys.exit(0 if ok == len(results) else 1)
