#!/usr/bin/env python3
"""الجلسة الإضافية: الطفل الذي يريد أن يستمر بعد جلسة يومه (قرار الأب، 19 نوفمبر 2026).

    python3 tests/test_extra.py <ملف الخريطة> [--write]

القاعدة التي يُختبر عليها، وهي مكتوبة قبل التشغيل:
- الإضافية بعد جلسة مختومة في يوم الأسرة نفسه، وبعد جلسة البدء، وما دام في اليوم وقت (day_cap) وعندنا ما يُعرض.
- فيها تعليم وتدريب فقط: يُكمَل ما قطعه السقف، والدرس الجاري، وتدريب المهارة التي تنتظر فحص استقلالها مرة في اليوم،
  ودرس جديد إن لم يُفتح اليوم درس. لا بوابة ولا تحقق قصير ولا فحص استقلال ولا فحص احتفاظ.
- المهارة المستوفاة لا تُدرَّب فيها، فتبقى جولات احتفاظها «احتفاظ».
- حد اليوم لا يقطع بندًا. ما قطعه من درس يُحفظ لجلسة الغد، وما قطعه من تدريب حر لا يُحفظ.
- الجلسات العادية لا تتغير بوجودها إلا بما أُنجز فيها.

--write يكتب tests/extra_tape.json: ما عُرض في كل مسار والحالة النهائية. اختبار التطبيق (test_extra.mjs) يعيد المسارات
ويطابقها. ما كُتب من التوقعات بعد رؤية المسار مذكور عند حالته.
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
TEACHING = ('opening', 'lesson', 'evidence', 'practice')
PRACTICE = {s: [i['id'] for i in ITEMS if i['skill'] == s and i['role'] == 'practice'] for s in {i['skill'] for i in ITEMS}}
# الشريحة (10.2). السقف وحد اليوم بقرار الأب: 6 دقائق و30 دقيقة للصغير، و10 و50 للكبيرين. ثواني البند قيمة اختبار
SCEN = dict(
    young=dict(group='young', scope=['1-4-1', '1-4-2'], decisions=[('1-4-1', ['1-3-3'])], cap=360, day_cap=1800, secs=30),
    older=dict(group='older', scope=['3-5-1', '3-5-2', '3-5-3'],
               decisions=[('3-5-1', ['3-3-2', '3-2-3']), ('3-5-2', ['3-2-1', '3-3-1', '2-5-2'])], cap=600, day_cap=3000,
               secs=45))
results, TAPE = [], {}


def check(title, bad):
    results.append(not bad)
    print('  %s  %d. %s' % ('نجح' if not bad else 'أخفق', len(results), title))
    for b in bad[:5]:
        print('        ' + str(b))


class Run:
    """طفل يتعلّم (لا يعرف المهارة حتى يرى درسها) يمضي يومًا بعد يوم. extra: هل يطلب الاستمرار كلما عُرض عليه؟"""

    def __init__(self, name, extra=True, **over):
        c = dict(SCEN[name], **over)
        self.c, self.extra, self.kid, self.trace, self.n, self.shown = c, extra, Kid(), [], 0, False
        self.e = Engine(NET, group=c['group'])
        for k, (skill, bypass) in enumerate(c['decisions']):
            self.e.apply(dict(id='d%d' % k, type='teacher_open', skill=skill, bypass=bypass, reason='قرار الشريحة في 10.2'))
        self.sc = Scheduler(self.e, TYPES, ContentSource(ITEMS), None, group=c['group'], scope=set(c['scope']),
                            learning=True, cap=c['cap'], item_seconds=lambda w: c['secs'], records=[], retention=True,
                            day_cap=c['day_cap'])

    def reopen(self, rec, today):
        self.e, self.sc, notes = persist.restore(json.loads(json.dumps(rec)), NET, TYPES, ContentSource(ITEMS), None,
                                                 item_seconds=lambda w: self.c['secs'], records=[], today=today)
        return notes

    def session(self, gen, day, stop=None):
        """جلسة واحدة. stop: رقم طلب البند (في المسار كله) الذي يُغلق التطبيق عنده. self.shown: هل عُرض البند قبل
        الإغلاق؟ تعيد اللقطة عند الإغلاق، أو None إن انتهى المولّد."""
        self.sc.today = day
        st = Stepper(self.e, self.sc)
        st.open(getattr(self.sc, gen)())
        while st.pending is not None:
            item, w = st.pending
            if stop is not None and self.n == stop:
                if self.shown:
                    st.show(st.seq)
                return st.snapshot()
            ses = self.sc.cur                               # تُلتقط قبل الإجابة: الطبقة قد تختم الجلسة بعدها
            self.trace.append((ses, self.e.s['sessions'][ses]['kind'], day, item['id'], w['activity']))
            self.n += 1
            for ev in self.kid.events(item, w):
                st.event(st.seq, ev)
        self.last = st
        return None

    def day(self, d, stop=None, reopen_day=None):
        """يوم كامل: جلسته، ثم الإضافيات ما دامت تُعرض. stop: يُغلق عند ذلك الطلب ثم يُفتح في reopen_day (اليوم نفسه
        إن لم يُعطَ) ويُكمَل."""
        gens = ['g_session'] + (['g_extra'] * 20 if self.extra else [])
        for gen in gens:
            if gen == 'g_extra' and not self.sc.can_extra(d):
                break
            rec = self.session(gen, d, stop)
            while rec is not None:                          # أُغلق التطبيق: يُستعاد ثم تُكمَل الجلسة الجارية
                stop = None
                back = d if reopen_day is None else reopen_day
                self.notes = self.reopen(rec, back)
                if back != d:
                    return
                rec = self.session('g_session', d) if self.sc.cur is not None else None

    def days(self, first, last):
        for d in range(first, last + 1):
            self.day(d)
        return self

    def of(self, kind=None, day=None, ses=None):
        return [t for t in self.trace if (kind is None or t[1] == kind) and (day is None or t[2] == day)
                and (ses is None or t[0] == ses)]

    def first_day(self, skill, activity):
        return next((t[2] for t in self.trace if t[3].startswith(skill + '/') and t[4] == activity), None)

    def tape(self):
        return dict(trace=[list(t) for t in self.trace], final=json.loads(dump(final(self.e, self.sc))))


print('=== الجلسة الإضافية، المرجع')

# ---------------------------------------------------------------- 1) الصغير: الدرس الذي قطعه السقف يُكمَل في يومه
a, b = Run('young').days(0, 12), Run('young', extra=False).days(0, 12)
TAPE['young'], TAPE['young_control'] = a.tape(), b.tape()
bad = []
x1 = a.of(kind='extra', day=1)
cut = len(b.of(day=1))                                      # بنود جلسة البدء حتى السقف
if a.of(day=0) != b.of(day=0) or a.of(kind='start') != b.of(kind='start'):
    bad.append('الجلسات العادية قبل أول إضافية تخالف المسار بلا إضافيات')
if cut * 30 < 360 or (cut - 1) * 30 >= 360:
    bad.append('السقف لم يقطع جلسة البدء حيث يجب: %d بندًا' % cut)
if not x1 or len({t[0] for t in x1}) != 1:
    bad.append('اليوم 1: المتوقع جلسة إضافية واحدة، والناتج %r' % sorted({t[0] for t in x1}))
# ما يكمله الطفل غدًا بلا إضافية هو نفسه ما يكمله اليوم بها: البنود نفسها بترتيبها
rest = [t[3] for t in b.of(day=2) if t[4] in TEACHING]
if [t[3] for t in x1][:len(rest)] != rest or not rest:
    bad.append('الإضافية لم تبدأ ببنود الدرس الباقية نفسها: %r مقابل %r' % ([t[3] for t in x1][:len(rest)], rest))
if [t[3] for t in x1][len(rest):] != PRACTICE['1-4-1']:
    bad.append('بعد اكتمال الدرس: المتوقع تدريب المهارة مرة واحدة، والناتج %r' % [t[3] for t in x1][len(rest):])
if any(t[4] not in TEACHING for t in a.of(kind='extra')):
    bad.append('في الإضافيات نشاط غير تعليمي: %r' % sorted({t[4] for t in a.of(kind='extra')}))
if (a.first_day('1-4-1', 'check'), b.first_day('1-4-1', 'check')) != (2, 3):
    bad.append('فحص استقلال 1-4-1: المتوقع اليوم 2 بالإضافية و3 بدونها، والناتج %r' % (
        (a.first_day('1-4-1', 'check'), b.first_day('1-4-1', 'check')),))
if a.e.derive()['1-4-1'] != 'met' or a.e.derive()['1-4-2'] != 'met' or a.e.derive() != b.e.derive():
    bad.append('حالة المهارتين في النهاية: %r و%r' % (a.e.derive(), b.e.derive()))
check('الصغير: السقف يقطع درس 1-4-1، والإضافية في اليوم نفسه تكمله بالبنود التي كانت ستُعرض غدًا، ثم تدريب المهارة مرة. لا نشاط '
      'تقييم فيها. وفحص الاستقلال يتقدم يومًا، والمهارتان مستوفاتان في المسارين', bad)

# ---------------------------------------------------------------- 2) لا إضافية حيث لا تجوز
bad = []
r = Run('young')
r.day(0)
if r.sc.can_extra(0):
    bad.append('بعد جلسة البحث (قبل جلسة البدء) عُرضت إضافية')
r.sc.today = 0
st = Stepper(r.e, r.sc)
before = dump(final(r.e, r.sc))
st.open(r.sc.g_extra())
if st.result is not False or st.pending is not None or dump(final(r.e, r.sc)) != before:
    bad.append('g_extra حيث لا تجوز غيّرت شيئًا أو عرضت بندًا')
r.session('g_session', 1)
if not r.sc.can_extra(1) or r.sc.can_extra(2):
    bad.append('بعد جلسة اليوم 1: المتوقع إضافية متاحة لليوم 1 لا لليوم 2')
if r.sc.extra_plan(1) != [('resume', '1-4-1')]:
    bad.append('خطة الإضافية: المتوقع إكمال ما قطعه السقف وحده، والناتج %r' % r.sc.extra_plan(1))
n = Run('young', day_cap=None)
n.day(0)
n.session('g_session', 1)
if n.sc.can_extra(1) or n.sc.used is not None:
    bad.append('بلا حد لليوم (day_cap) عُرضت إضافية أو حُفظ زمن اليوم')
if [t for t in a.trace if t[1] == 'extra' and t[2] >= 5]:
    bad.append('إضافية بعد استيفاء المهارتين: %r' % [t[:3] for t in a.trace if t[1] == 'extra' and t[2] >= 5][:3])
check('لا إضافية قبل جلسة البدء، ولا في يوم بلا جلسة، ولا بلا حد لليوم، ولا بعد استيفاء المهارتين. و g_extra حيث لا تجوز لا '
      'تغيّر شيئًا', bad)

# ---------------------------------------------------------------- 3) المستوفاة لا تُدرَّب، والاحتفاظ يبقى «احتفاظ»
bad = []
for run, name in ((a, 'بالإضافية'), (b, 'بدونها')):
    got = [(x['skill'], x['round'], x['label'], run.e.s['sessions'][x['session']]['kind']) for x in run.e.s['retention']]
    if got != [('1-4-1', 1, 'retention', 'follow'), ('1-4-2', 1, 'retention', 'follow')][:len(got)] or not got:
        bad.append('%s: جولات الاحتفاظ %r' % (name, got))
if len(a.e.s['retention']) != 2:
    bad.append('بالإضافية: المتوقع جولتان حتى اليوم 12 (7 أيام بعد فحصَي اليومين 2 و4)، والناتج %d' % len(a.e.s['retention']))
check('جولات الاحتفاظ في جلسات عادية في المسارين، ووصف نتائجها «احتفاظ» (لم تُدرَّب مهارة مستوفاة في إضافية)', bad)

# ---------------------------------------------------------------- 4) حد اليوم يقطع الدرس: يُحفظ لجلسة الغد
bad = []
c = Run('young', day_cap=cut * 30 + 30).days(0, 3)          # يتسع لبند واحد بعد جلسة البدء
TAPE['young_daycap_lesson'] = c.tape()
x = c.of(kind='extra', day=1)
if [t[3] for t in x] != rest[:1]:
    bad.append('المتوقع بند واحد في الإضافية (%r)، والناتج %r' % (rest[:1], [t[3] for t in x]))
if [t[3] for t in c.of(day=2) if t[4] in TEACHING][:len(rest) - 1] != rest[1:]:
    bad.append('جلسة الغد لم تكمل الدرس من موضعه: %r' % [t[3] for t in c.of(day=2)][:4])
if c.of(kind='extra', day=2) and c.first_day('1-4-1', 'check') != 3:
    bad.append('فحص 1-4-1 في اليوم %r' % c.first_day('1-4-1', 'check'))
check('حد اليوم يتسع لبند واحد: الإضافية تعرضه ثم تُختم، ولا إضافية ثانية، والدرس محفوظ فتكمله جلسة الغد من موضعه', bad)

# ---------------------------------------------------------------- 5) حد اليوم يقطع التدريب الحر: لا يُحفظ
bad = []
d = Run('young', day_cap=(cut + len(rest) + 2) * 30).days(0, 2)   # يتسع لباقي الدرس وبندَي تدريب
TAPE['young_daycap_practice'] = d.tape()
x = [t[3] for t in d.of(kind='extra', day=1)]
if x != rest + PRACTICE['1-4-1'][:2]:
    bad.append('الإضافية: المتوقع باقي الدرس وبندا تدريب، والناتج %r' % x)
rec1 = Run('young', day_cap=(cut + len(rest) + 2) * 30).days(0, 1)
if any(s['kind'] == 'show' for s in rec1.sc.saved) or (rec1.sc.free or {}).get('skills') != ['1-4-1']:
    bad.append('بعد القطع: المحفوظ %r، وما دُرّب %r' % (rec1.sc.saved, rec1.sc.free))
first = [t for t in d.of(day=2)][:1]
if not first or first[0][4] != 'check':
    bad.append('جلسة الغد: المتوقع أن تبدأ بفحص الاستقلال، والناتج %r' % first)
check('حد اليوم يقطع التدريب الحر بعد بندين: لا يُحفظ، فلا يأخذ حصة الغد، وجلسة الغد تبدأ بفحص الاستقلال', bad)

# ---------------------------------------------------------------- 6) الإغلاق داخل الإضافية
bad = []
ref = Run('young').days(0, 4)
base, total = dump(final(ref.e, ref.sc)), ref.n
diff = []
for k in range(total):                                      # الإغلاق قبل عرض البند: لا أثر له
    r = Run('young')
    for dd in range(0, 5):
        r.day(dd, stop=k)
    if dump(final(r.e, r.sc)) != base or r.trace != ref.trace:
        diff.append(k)
if diff:
    bad.append('%d من %d موضع إغلاق تخالف المسار المتصل. أولها %r' % (len(diff), total, diff[:5]))
ex = [i for i, t in enumerate(ref.trace) if t[1] == 'extra']
if not ex:
    bad.append('لا بند إضافية في المسار المرجعي')
check('الإغلاق قبل عرض البند، عند كل طلب في الأيام 0 إلى 4 (%d موضعًا، منها %d في إضافيات)، ثم العودة في اليوم نفسه: الحالة '
      'الدائمة كاملة وما عُرض كما في المسار المتصل' % (total, len(ex)), bad)

# الإغلاق والبند معروض لم يُجب، داخل الإضافيات: بنود التعليم يُعاد عرضها (R22-02)، فما عُرض والجلسات وحالة المهارات كما
# في المتصل. سجلات البنود تزيد سجلًا منقطعًا للبند الذي أُغلق عليه. وكتبتُ التوقع أولًا «حالة المحرك كلها»، وهو خطأ: بند دليل
# الفهم الذي أُعيد عرضه يُكتب مرتين في بنود الدليل، في الجلسة العادية كما في الإضافية (قستُه في المسارين).
bad, diff = [], []
for k in ex:
    r = Run('young')
    r.shown = True
    for dd in range(0, 5):
        r.day(dd, stop=k)
    same = (r.e.derive() == ref.e.derive() and r.e.s['order'] == ref.e.s['order'] and all(
        (r.e.s['sessions'][x]['kind'], r.e.s['sessions'][x]['day'], r.e.s['sessions'][x]['ended']) == (
            ref.e.s['sessions'][x]['kind'], ref.e.s['sessions'][x]['day'], ref.e.s['sessions'][x]['ended'])
        for x in ref.e.s['order']) and r.sc.used == ref.sc.used and r.sc.free == ref.sc.free)
    if r.trace != ref.trace or not same:
        diff.append((k, ref.trace[k][3], r.trace != ref.trace, not same))
if diff:
    bad.append('%d من %d: (الموضع، البند، اختلف المعروض، اختلفت الحالة) %r' % (len(diff), len(ex), diff[:6]))
check('الإغلاق والبند معروض، عند كل بند في الإضافيات (%d): تُكمَل الإضافية نفسها بالبند نفسه، وما عُرض والجلسات وحالة المهارات '
      'ووقت اليوم كما في المسار المتصل' % len(ex), bad)

bad = []
pk = next(i for i, t in enumerate(ref.trace) if t[1] == 'extra' and t[4] == 'practice') + 2   # ثالث بنود التدريب الحر
r = Run('young')
r.shown = True
r.day(0)
r.day(1, stop=pk, reopen_day=2)
if ('session_closed', 'S3') not in r.notes or ('free_practice_dropped', '1-4-1') not in r.notes:
    bad.append('ملاحظات الاستعادة: %r' % (r.notes,))
if any(s['kind'] == 'show' for s in r.sc.saved) or r.sc.cur is not None:
    bad.append('بعد الاستعادة في يوم جديد: المحفوظ %r، والجلسة %r' % (r.sc.saved, r.sc.cur))
r.day(2)
first = r.of(day=2)[:1]
if not first or first[0][4] != 'check':
    bad.append('جلسة اليوم التالي: المتوقع أن تبدأ بفحص الاستقلال، والناتج %r' % first)
TAPE['young_closed_overnight'] = r.tape()
check('الإغلاق في التدريب الحر والعودة في اليوم التالي: الإضافية تُختم، والتدريب لا يُحفظ، وجلسة اليوم تبدأ بفحص الاستقلال', bad)

# ---------------------------------------------------------------- 7) الكبيران: درس جديد في الإضافية، وواحد في اليوم
bad = []
o, oc = Run('older').days(0, 13), Run('older', extra=False).days(0, 13)
TAPE['older'], TAPE['older_control'] = o.tape(), oc.tape()
for run, name in ((o, 'بالإضافية'), (oc, 'بدونها')):
    per = {}
    for s, op in run.e.s['opened'].items():
        per.setdefault(run.e.s['sessions'][op['session']]['day'], []).append(s)
    if any(len(v) > 1 for v in per.values()):
        bad.append('%s: أكثر من درس جديد في يوم: %r' % (name, per))
new = [s for s, op in o.e.s['opened'].items() if o.e.s['sessions'][op['session']]['kind'] == 'extra']
if new != ['3-5-2']:
    bad.append('الدروس التي فُتحت في إضافية: المتوقع 3-5-2 وحده، والناتج %r' % new)
if any(t[4] not in TEACHING for t in o.of(kind='extra')):
    bad.append('في إضافيات الكبيرين نشاط غير تعليمي')
days = lambda run: [run.first_day(s, 'check') for s in ('3-5-1', '3-5-2', '3-5-3')]
if days(o) != [2, 3, 5] or days(oc) != [3, 6, 8]:
    bad.append('أيام فحوص الاستقلال: %r بالإضافية و%r بدونها' % (days(o), days(oc)))
if o.e.derive() != oc.e.derive():
    bad.append('حالة المهارات تختلف في النهاية')
check('الكبيران: بوابة 3-5-2 تخفق في يوم ذهبت حصته لفحص 3-5-1، فيُفتح درسها في إضافية اليوم نفسه. درس جديد واحد في كل يوم '
      'أسرة. وفحوص الاستقلال في الأيام 2 و3 و5 بدل 3 و6 و8 (الأيام مقيسة من المسار)، والحالة النهائية واحدة', bad)

path = os.path.join(HERE, 'extra_tape.json')
if WRITE:
    json.dump(TAPE, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=0, sort_keys=True)
    print('كُتب %s' % path)
else:
    old = json.load(open(path, encoding='utf-8'))
    check('الشريط المحفوظ يطابق هذا التشغيل (يُجدَّد بـ --write)', [k for k in sorted(set(old) | set(TAPE))
                                                                 if dump(old.get(k)) != dump(TAPE.get(k))])
print('نجحت الاختبارات كلها: %d' % len(results) if all(results) else 'أخفق %d من %d' % (results.count(False), len(results)))
sys.exit(0 if all(results) else 1)
