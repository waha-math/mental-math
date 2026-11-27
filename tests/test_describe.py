#!/usr/bin/env python3
"""الفحص الوصفي للمقارنة (10.2، خ7؛ موضعه بقرار الأب في 19 نوفمبر).

    python3 tests/test_describe.py <ملف الخريطة> [--write]

القاعدة، مكتوبة قبل التشغيل:
- 4 بنود descriptive_check لـ 3-5-3، بترتيبها، مرة واحدة، في أول جلسة تلي الجلسة التي اجتاز فيها فحص الاستقلال.
- لا حدث له في المحرك: حالة المحرك بعد البنود الأربعة هي حالته قبلها. ولا يغيّر شيئًا مما يليه.
- بلا تغذية راجعة: البند ينتهي بأول تأكيد، والتأكيد بطاقة من بطاقات البند. عدد أو بطاقة غريبة يُرفضان.
- كل بند يُختم يُسجَّل (activity=describe). إن أُغلق التطبيق أثناءه: البند المعروض يُختم منقطعًا، والفحص لا يُحفظ
  ولا يُعاد في جلسة لاحقة (described).

--write يكتب tests/describe_tape.json: الحالة الدائمة لمساري الحالتين 2 و4. test_describe.mjs يعيدهما ويطابقها.
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

Engine, Scheduler, ContentSource, NET, TYPES, ITEMS, Kid, persist, final, dump = (g[k] for k in (
    'Engine', 'Scheduler', 'ContentSource', 'NET', 'TYPES', 'ITEMS', 'Kid', 'persist', 'final', 'dump'))
DESC = [i['id'] for i in ITEMS if i['role'] == 'descriptive_check']
results, TAPE = [], {}


def check(title, got, want):
    ok = dump(got) == dump(want)
    results.append(ok)
    print('  %s  %d. %s' % ('نجح' if ok else 'أخفق', len(results), title))
    if not ok:
        print('        المتوقع %s\n        الناتج  %s' % (dump(want)[:500], dump(got)[:500]))


class Run:
    def __init__(self):
        self.kid, self.trace, self.engine_at = Kid(), [], {}
        self.e = Engine(NET, group='older')
        for k, (skill, bypass) in enumerate([('3-5-1', ['3-3-2', '3-2-3']), ('3-5-2', ['3-2-1', '3-3-1', '2-5-2'])]):
            self.e.apply(dict(id='d%d' % k, type='teacher_open', skill=skill, bypass=bypass, reason='قرار الشريحة في 10.2'))
        self.sc = self.new_sc()

    def new_sc(self):
        return Scheduler(self.e, TYPES, ContentSource(ITEMS), None, group='older', scope={'3-5-1', '3-5-2', '3-5-3'},
                         learning=True, cap=600, item_seconds=lambda w: 45, records=[], retention=True, day_cap=3000)

    def day(self, d, stop_at=None, answer=None):
        """جلسة اليوم d. stop_at: معرّف بند يُغلق التطبيق وهو معروض عليه، وتعيد اللقطة. answer(item): الإجابة بديلًا."""
        self.sc.today = d
        st = Stepper(self.e, self.sc)
        st.open(self.sc.g_session())
        while st.pending is not None:
            item, w = st.pending
            self.trace.append((d, self.sc.cur, item['id'], w['activity']))
            if w['activity'] == 'describe' and 'before' not in self.engine_at:
                self.engine_at['before'] = self.e.dump()
            st.show(st.seq)
            if item['id'] == stop_at:
                return st.snapshot()
            for ev in (answer(item) if answer and w['activity'] == 'describe' else self.kid.events(item, w)):
                if st.event(st.seq, ev) == 'rejected':
                    raise AssertionError(st.reject)
            if w['activity'] == 'describe' and item['id'] == DESC[-1]:
                self.engine_at['after'] = self.e.dump()
        return None

    def days(self, a, b, **kw):
        for d in range(a, b + 1):
            if self.day(d, **kw) is not None:
                raise AssertionError('إغلاق غير متوقع')
        return self


print('=== الفحص الوصفي للمقارنة، المرجع')
# ---------------------------------------------------------------- 1) عقد الحدث
st = Stepper(None, None)
BY = {i['id']: i for i in ITEMS}


def allowed(ev, item=DESC[0], activity='describe'):
    st.pending, st.raw = (BY[item], dict(activity=activity, role='descriptive_check', pos=0)), []
    return st.allowed(ev)


check('عقد الحدث: التأكيد بإحدى بطاقات البند، والعدد والبطاقة الغريبة مرفوضان، وطلب المساعدة كبند تقييم، ولا إنهاء',
      [allowed(('confirm', 'A')), allowed(('confirm', 'same')), allowed(('confirm', 3)), allowed(('confirm', 'C')),
       allowed(('support', 'requested')), allowed(('support', 'hint')), allowed(('end',))],
      [None, None, 'بند البطاقة يُجاب ببطاقة', 'بطاقة ليست من بطاقات البند', None,
       'بند التقييم يقبل طلب «أحتاج مساعدة» (requested) وحده', 'بند التقييم ينتهي بالتأكيد أو بطلب المساعدة'])

# ---------------------------------------------------------------- 2) مسار كامل
# أحداث المحرك بين أول بند وصفي وما بعد ختم آخرها. كتبتُ التوقع أول مرة «المحرك نفسه»، ونقطة القياس بعد آخر إجابة
# تشمل ما يليها في الانتقال نفسه: هنا ختم الجلسة. فالمتوقع أن لا حدث غيره
new_events = lambda run: [x['type'] for x in json.loads(run.engine_at['after'])['log'][
    len(json.loads(run.engine_at['before'])['log']):]]
r = Run().days(0, 14)
passed = [x[0] for x in r.sc.log if x[1] == 'check_pass' and x[2] == '3-5-3']
pass_day = next(t[0] for t in r.trace if t[2].startswith('3-5-3/check') and t[3] == 'check' and t[1] == 'S%d' % passed[0]) \
    if passed else None
desc = [t for t in r.trace if t[3] == 'describe']
recs = [x for x in r.sc.records if x.get('activity') == 'describe']
check('مسار طفل يتعلّم: البنود الأربعة بترتيبها مرة واحدة، في الجلسة التالية لجلسة اجتياز فحص 3-5-3 وفي يومها التالي، '
      'وسجلاتها الأربعة صحيحة، والمحرك بعدها هو المحرك قبلها',
      [[t[2] for t in desc], len({t[1] for t in desc}), desc[0][0] - pass_day if desc and pass_day is not None else None,
       [(x['item'], x['values'], x['final']) for x in recs], new_events(r),
       r.sc.described],
      [DESC, 1, 1, [(i, [BY[i]['answer']], 'correct') for i in DESC], ['session_end'], ['3-5-3']])
TAPE['full'] = dict(trace=[list(t) for t in r.trace], final=json.loads(dump(final(r.e, r.sc))))

# ---------------------------------------------------------------- 3) إجابة خاطئة: تُسجَّل ولا تغيّر شيئًا آخر
other = lambda item: [('confirm', next(c for c in item['cards'] if c != item['answer']))]
w = Run().days(0, 14, answer=other)
fw, fr = json.loads(dump(final(w.e, w.sc))), json.loads(dump(final(r.e, r.sc)))
check('الإجابات الخاطئة في الوصفي تُسجَّل خطأً، والمحرك والمجدول ومسار الأيام التالية كما مع الصحيحة',
      [[x['final'] for x in w.sc.records if x.get('activity') == 'describe'], fw['engine'] == fr['engine'],
       [t for t in w.trace if t[3] != 'describe'] == [t for t in r.trace if t[3] != 'describe']],
      [['wrong'] * 4, True, True])

# ---------------------------------------------------------------- 4) إغلاق أثناءه
c = Run()
c.days(0, desc[0][0] - 1)
snap = c.day(desc[0][0], stop_at=DESC[1])
e2, sc2, notes = persist.restore(json.loads(json.dumps(snap)), NET, TYPES, ContentSource(ITEMS), None,
                                 item_seconds=lambda w: 45, records=[], today=desc[0][0])
c.e, c.sc = e2, sc2
after = [x for x in sc2.records if x.get('activity') == 'describe']
check('إغلاق والبند الثاني معروض: الأول مسجَّل، والثاني يُختم منقطعًا، والفحص لا يُحفظ ولا يُستأنف',
      [[(x['item'], x['status']) for x in after], [n for n in notes if n[0] == 'describe_dropped'],
       [x['kind'] for x in sc2.saved], sc2.described],
      [[(DESC[0], 'complete'), (DESC[1], 'interrupted')], [('describe_dropped', '3-5-3')], [], ['3-5-3']])
k = len(c.trace)
st2 = Stepper(c.e, c.sc)
st2.open(c.sc.g_continue())
while st2.pending is not None:
    item, w2 = st2.pending
    c.trace.append((desc[0][0], c.sc.cur, item['id'], w2['activity']))
    for ev in c.kid.events(item, w2):
        st2.event(st2.seq, ev)
for d in range(desc[0][0] + 1, 15):
    c.day(d)
check('بعد الإغلاق: لا بند وصفي في بقية الجلسة ولا في الأيام التالية',
      [t[2] for t in c.trace[k:] if t[3] == 'describe'], [])
TAPE['closed'] = dict(trace=[list(t) for t in c.trace], final=json.loads(dump(final(c.e, c.sc))))

if WRITE:
    json.dump(TAPE, open(os.path.join(HERE, 'describe_tape.json'), 'w', encoding='utf-8'), ensure_ascii=False, sort_keys=True)
    print('كُتب tests/describe_tape.json')
tape = json.load(open(os.path.join(HERE, 'describe_tape.json'), encoding='utf-8'))
check('الشريط المحفوظ يطابق المسارين الآن', [dump(tape['full']) == dump(TAPE['full']), dump(tape['closed']) == dump(TAPE['closed'])],
      [True, True])
ok = sum(results)
print('النتيجة: نجح %d من %d' % (ok, len(results)))
sys.exit(0 if ok == len(results) else 1)
