#!/usr/bin/env python3
"""المرحلة 0 بلغة بايثون: التوقف عند انتظار الطفل، والإغلاق، والاستعادة، وتكملة الجلسة نفسها.

    python3 tests/test_phase0.py <ملف الخريطة> [--code=مجلد]

--code يشغّل الحالات على نسخة أخرى من الكود (مثلًا الالتزام 0189879).

قسمان:
أ) مسح شامل: في كل مسار كامل بمحتوى الشريحة يُغلق التطبيق عند كل طلب بند قبل عرضه، واحدًا واحدًا. تؤخذ اللقطة، وتُستعاد
   في محرك ومجدول جديدين، وتُكمَل الجلسة نفسها ثم بقية المسار. النتيجة المتوقعة مصدرها التشغيل المتصل بلا إغلاق:
   المحرك وسجلات البنود وسجل المجدول ومخزناه حرفًا بحرف. هذا يفحص أن المتابعة تُبنى من المحفوظ لا من المولّد.
ب) حالات بنتائج مكتوبة يدويًا: الإغلاق عند عرض البند، وبعد الدعم، وبعد إجابة غير نهائية، وبعد الإجابة النهائية، وعند
   السقف، والإجابة المكررة، واستثناء داخل الانتقال، وضمانات الجلسة (لا جلسة جديدة، لا وقت جديد، لا حصة جديدة)،
   وانتقال اليوم.
"""
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
from stepper import Stepper  # noqa: E402
from item_layer import indicators  # noqa: E402
import persist  # noqa: E402

MAP = args[0]
NET = load_network(MAP)
TYPES = {}
for sid, _t, _m, _r, ev, _a in ROW.findall(open(MAP, encoding='utf-8').read()):
    if sid in NET[1] and sid not in TYPES:
        TYPES[sid] = re.findall(r'ف\d', ev)
ITEMS = json.load(open(os.path.join(HERE, '..', 'slice-content.json'), encoding='utf-8'))['items']
results = []


def check(title, bad):
    results.append(not bad)
    print('  %s  %s' % ('نجح' if not bad else 'أخفق', title))
    for b in bad[:4]:
        print('        ' + b)


class Kid:
    """طفل نموذجي: يعرف المهارة بعد أن يرى درسها. wrong: معرّفات بنود يخطئ فيها. help: بنود يطلب فيها تلميحًا أولًا."""

    def __init__(self, wrong=(), help=()):
        self.known, self.wrong, self.help = set(), set(wrong), set(help)

    def events(self, item, w):
        a = w['activity']
        if a in ('lesson', 'practice'):
            if a == 'lesson':
                self.known.add(item['skill'])
            return [('end',)]
        assess = a in ('gate', 'short', 'check', 'retention', 'describe')
        ok = item['skill'] in self.known and item['id'] not in self.wrong
        ans = item['answer'] if ok else (item['answer'] + 1 if item['answer'] < 99 else item['answer'] - 1)
        pre = [('support', 'hint')] if item['id'] in self.help else []
        return pre + [('confirm', ans)] + ([] if assess else [('end',)])


SCEN = dict(
    young=dict(group='young', scope=['1-4-1', '1-4-2'], decisions=[('1-4-1', ['1-3-3'])], cap=240, sessions=14,
               secs=lambda w: 60 if w['activity'] == 'check' else 25),
    older=dict(group='older', scope=['3-5-1', '3-5-2', '3-5-3'],
               decisions=[('3-5-1', ['3-3-2', '3-2-3']), ('3-5-2', ['3-2-1', '3-3-1', '2-5-2'])], cap=600, sessions=16,
               secs=lambda w: 45),
)
SCEN['retention'] = dict(SCEN['young'], scope=['1-4-1'], retention=True, sessions=100)   # فحوص الاحتفاظ الثلاثة


def build(name, records=None):
    c = SCEN[name]
    e = Engine(NET, group=c['group'])
    for k, (skill, bypass) in enumerate(c['decisions']):
        e.apply(dict(id='d%d' % k, type='teacher_open', skill=skill, bypass=bypass, reason='قرار الشريحة في 10.2'))
    sc = Scheduler(e, TYPES, ContentSource(ITEMS), None, group=c['group'], scope=set(c['scope']), learning=True,
                   cap=c['cap'], item_seconds=c['secs'], records=[] if records is None else records,
                   retention=c.get('retention', False))
    return e, sc


def reopen(name, rec, today=None, records=None):
    c = SCEN[name]
    e, sc, notes = persist.restore(json.loads(json.dumps(rec)), NET, TYPES, ContentSource(ITEMS), None,
                                   item_seconds=c['secs'], records=[] if records is None else records, today=today)
    return e, sc, notes


def play(st, kid, stop_at=None, n=0):
    """يجيب الطفل عن الطلبات حتى ينتهي المولّد، أو حتى الطلب رقم stop_at (لا يُعرض ولا يُجاب). يعيد عدد ما أُجيب."""
    while st.pending is not None:
        if stop_at is not None and n == stop_at:
            return n
        item, w = st.pending
        for ev in kid.events(item, w):
            st.event(st.seq, ev)
        n += 1
    return n


def final(e, sc):
    """الحالة الدائمة كاملة: كل ما يحفظه persist من المجدول (state_of، ومنه العدّادات n وموضع الجلسة stage والوقت
    elapsed وعدّادات البحث وسجل المجدول والمخزنان)، والمحرك، وسجلات البنود. لا حقل مستثنى."""
    d = persist.state_of(sc)
    d['engine'], d['records'] = e.dump(), persist.plain(sc.records)
    return d


def dump(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False)


def sweep(name, wrong=(), help=()):
    c = SCEN[name]
    e, sc = build(name)
    st = Stepper(e, sc)
    st.open(sc.g_run(c['sessions']))
    total = play(st, Kid(wrong, help))
    base = final(e, sc)
    # الغلاف المتزامن يعطي النتيجة نفسها
    e0, sc0 = build(name)
    kid0 = Kid(wrong, help)

    def answer(item, w):
        evs = kid0.events(item, w)
        if w['activity'] in ('lesson', 'practice'):
            return 'correct'
        return evs, item['answer'], w['activity'] in ('gate', 'short', 'check', 'retention', 'describe')
    sc0.answer = answer
    sc0.run(c['sessions'])
    bad = []
    if dump(final(e0, sc0)) != dump(base):
        bad.append('التشغيل خطوة خطوة يخالف الغلاف المتزامن')
    if base['refused']:
        bad.append('المحرك رفض %d اقتراحًا في التشغيل المتصل' % len(base['refused']))
    diff = []
    for k in range(total):
        e1, sc1 = build(name)
        s1 = Stepper(e1, sc1)
        kid = Kid(wrong, help)
        s1.open(sc1.g_run(c['sessions']))
        play(s1, kid, stop_at=k)
        rec = s1.snapshot()
        try:
            e2, sc2, notes = reopen(name, rec)
            s2 = Stepper(e2, sc2)
            s2.open(sc2.g_run(c['sessions']))
            play(s2, kid)
            got = final(e2, sc2)
        except Exception as x:                               # noqa: BLE001
            diff.append((k, 'استثناء %r' % (x,)))
            continue
        if dump(got) != dump(base):
            diff.append((k, '، '.join(f for f in base if dump(got[f]) != dump(base[f]))))
    if diff:
        bad.append('%d من %d موضع إغلاق تخالف التشغيل المتصل. أولها: %r' % (len(diff), total, diff[:3]))
    return bad, total, base


print('=== المرحلة 0، بلغة بايثون، على الكود في %s' % os.path.relpath(os.path.abspath(code)))
print('أ) إغلاق عند كل طلب بند قبل عرضه، ثم استعادة وتكملة: النتيجة كما في التشغيل المتصل')
for name, wrong, help, label in (
        ('young', (), (), 'الصغير في 1-4، بسقف 240 ثانية'),
        ('young', ('1-4-1/evidence/01', '1-4-1/checkA/03', '1-4-1/checkA/05'), ('1-4-2/evidence/01',),
         'الصغير، بأخطاء في دليل الفهم والفحص وطلب تلميح'),
        ('older', (), (), 'الكبيران في 3-5، بسقف 600 ثانية'),
        ('older', ('3-5-1/checkA/01', '3-5-1/checkA/03', '3-5-2/evidence/01'), (),
         'الكبيران، بأخطاء في الفحص ودليل الفهم'),
        ('retention', (), (), 'الصغير في 1-4-1 مع فحوص الاحتفاظ الثلاثة')):
    ids = {i['id'] for i in ITEMS}
    missing = [x for x in list(wrong) + list(help) if x not in ids]
    bad, total, base = sweep(name, wrong, help)
    if missing:
        bad.append('بنود الإعداد غير موجودة في المحتوى: %r' % missing)
    check('%s: %d موضع إغلاق في %d جلسة و%d سجل بند' % (label, total, base['sessions'], len(base['records'])), bad)
# ---------------------------------------------------------------- ب) حالات بنتائج مكتوبة يدويًا
# مسار الصغير بلا أخطاء، كما تعطيه القواعد: S1 بوابة 1-4-1 (بندان)، S2 افتتاح ودرس حتى السقف، S3 دليل الفهم،
# S4 بدء الفحص: الخانات 1 إلى 4 (60 ثانية للبند، والسقف 240)، S5 الخانات 5 إلى 8، S6 الخانتان 9 و10 والنتيجة.
# الطلب رقم 16 هو الخانة 1، و17 الخانة 2 (البند 1-4-1/checkA/03 وبديله 1-4-1/checkA/04)، و25 الخانة 10.
def at(n, source=None):
    e, sc = build('young')
    if source:
        sc.source = source(sc.source)
    st, kid = Stepper(e, sc), Kid()
    st.open(sc.g_run(14))
    play(st, kid, stop_at=n)
    return e, sc, st, kid


def count(e, typ, session=None, **kw):
    return sum(1 for x in e.s['log'] if x['type'] == typ and (session is None or x.get('session') == session)
               and all(x.get(k) == v for k, v in kw.items()))


def expect(bad, label, got, want):
    if got != want:
        bad.append('%s: %r، والمتوقع %r' % (label, got, want))


def case_shown():
    e, sc, st, kid = at(17)
    st.show(st.seq)
    e2, sc2, notes = reopen('young', st.snapshot())
    bad = []
    expect(bad, 'ملاحظات الاستعادة', [list(n) for n in notes],
           [['unsettled_item', '1-4-1', '1-4-1/checkA/03', 'interrupted'], ['current_saved', 'check', '1-4-1']])
    expect(bad, 'الجلسة الجارية في المحرك والمجدول وعدد الجلسات والوقت المستهلك',
           [e2.s['current'], sc2.cur, sc2.sessions, sc2.elapsed], ['S4', 'S4', 4, 60])
    last = sc2.records[-1]
    expect(bad, 'سجل البند المعروض', [last['item'], last['status'], last['first'], last.get('unsettled')],
           ['1-4-1/checkA/03', 'interrupted', None, True])
    s2 = Stepper(e2, sc2)
    s2.open(sc2.g_run(14))
    item, w = s2.pending
    expect(bad, 'البند التالي بعد العودة', [item['id'], w['role'], w['slot'], sc2.cur], ['1-4-1/checkA/04', 'check.alternate', 2, 'S4'])
    play(s2, kid)
    expect(bad, 'بدايات S4 واستئنافات الفحص فيها', [count(e2, 'session_start', 'S4'), count(e2, 'check_resumed', 'S4')], [1, 0])
    expect(bad, 'نتيجة فحص 1-4-1', [x['result'] for x in e2.s['log'] if x['type'] == 'independence_result'
                                    and x['skill'] == '1-4-1'], ['pass'])
    expect(bad, 'مرات ظهور البند المنقطع في السجلات', sum(1 for r in sc2.records if r['item'] == '1-4-1/checkA/03'), 1)
    return bad


def case_support():
    e, sc, st, kid = at(12)                                 # أول بند دليل فهم في S3
    r = st.event(st.seq, ('support', 'hint'))
    e2, sc2, notes = reopen('young', st.snapshot())
    last = sc2.records[-1]
    bad = []
    expect(bad, 'نتيجة الحدث', r, 'open')
    expect(bad, 'سجل البند', [last['item'], last['status'], last['first'], last['support_before'], last.get('unsettled')],
           ['1-4-1/evidence/01', 'interrupted', None, ['hint'], True])
    expect(bad, 'الجلسة', [sc2.cur, sc2.sessions, count(e2, 'session_start', 'S3'), count(e2, 'resume_lesson', 'S3')],
           ['S3', 3, 1, 1])
    s2 = Stepper(e2, sc2)
    s2.open(sc2.g_continue())
    play(s2, kid)
    expect(bad, 'بعد تكملة الجلسة: استئنافات الدرس في S3، والجلسة الجارية', [count(e2, 'resume_lesson', 'S3'), sc2.cur], [1, None])
    return bad


def case_nonfinal():
    e, sc, st, kid = at(13)                                 # البند 1-4-1/evidence/02
    r = st.event(st.seq, ('confirm', 5))
    e2, sc2, notes = reopen('young', st.snapshot())
    last = sc2.records[-1]
    bad = []
    expect(bad, 'نتيجة الحدث', r, 'open')
    expect(bad, 'سجل البند', [last['item'], last['status'], last['first'], last['final'], last.get('unsettled')],
           ['1-4-1/evidence/02', 'complete', False, 'incomplete', True])   # 3.1: مكتمل لأن إجابة أولى أُكّدت
    expect(bad, 'الجلسة', [sc2.cur, sc2.sessions], ['S3', 3])
    return bad


def case_final():
    e, sc, st, kid = at(25)                                 # الخانة العاشرة: إجابتها تنهي الفحص وتصدر نتيجته
    st.show(st.seq)
    before, old = st.snapshot(), st.seq
    n_rec = len(before['records'])                         # سجلات البنود في اللقطة قبل الإجابة
    r1 = st.event(old, ('confirm', 4))
    r2 = st.event(old, ('confirm', 4))                      # نقرة ثانية على التأكيد نفسه
    bad = []
    expect(bad, 'نتيجة الإجابة ثم تكرارها', [r1, r2], ['next', 'ignored'])
    expect(bad, 'نتائج الفحص في المحرك، وحالة المحاولة، وعدد السجلات الجديدة',
           [count(e, 'independence_result'), e.s['checks']['1-4-1/check/1']['state'], len(sc.records) - n_rec],
           [1, 'closed', 1])
    after = st.snapshot()
    try:                                                    # اللقطة بعد الانتقال: كاملة وتُستعاد
        e2, sc2, notes = reopen('young', after)
        expect(bad, 'بعد الاستعادة من اللقطة الجديدة', [count(e2, 'independence_result'), len(sc2.records),
                                                       [list(n) for n in notes]],
               [1, n_rec + 1, [['current_saved', 'gate', '1-4-2']]])
        s2 = Stepper(e2, sc2)
        s2.open(sc2.g_run(14))
        expect(bad, 'البند التالي لم يُعرض فيُطلب نفسه', s2.pending[0]['id'], '1-4-2/gate/01')
        play(s2, kid)
        expect(bad, 'نتائج فحص 1-4-1 بعد إكمال المسار', count(e2, 'independence_result', skill='1-4-1'), 1)
    except persist.Inconsistent as x:
        bad.append('اللقطة بعد الانتقال رُفضت: %s' % x)
    e3, sc3, notes3 = reopen('young', before)               # كتابة الانتقال لم تُقرّ: المحفوظ هو ما قبله، كاملًا
    last = sc3.records[-1]
    expect(bad, 'الاستعادة مما قبل الانتقال', [count(e3, 'independence_result'), e3.s['checks']['1-4-1/check/1']['state'],
                                             last['item'], last['status'], last.get('unsettled'), len(sc3.records)],
           [0, 'pending', '1-4-1/checkA/19', 'interrupted', True, n_rec + 1])
    return bad


def case_cap():
    e, sc = build('young')
    st, kid = Stepper(e, sc), Kid()
    for g in (sc.g_search, sc.g_start_session, sc.g_follow_learning, sc.g_follow_learning):
        st.open(g())
        play(st, kid)                                       # حتى نهاية S4: أربع خانات ثم السقف
    bad = []
    expect(bad, 'بعد بلوغ السقف: المولّد، والجلسة، والمحفوظ', [st.finished, e.s['current'], sc.cur, sc.elapsed,
                                                           [(c['kind'], c['act']['slot']) for c in sc.saved]],
           [True, None, None, 240, [('check', 5)]])
    rec = st.snapshot()
    expect(bad, 'النشاط الجاري في اللقطة', rec['current'], None)
    e2, sc2, notes = reopen('young', rec)
    expect(bad, 'ملاحظات الاستعادة والجلسة', [[list(n) for n in notes], sc2.cur, sc2.sessions], [[], None, 4])
    s2 = Stepper(e2, sc2)
    s2.open(sc2.g_follow_learning())
    expect(bad, 'الجلسة التالية', [sc2.cur, count(e2, 'check_resumed', 'S5'), s2.pending[0]['id'], sc2.elapsed],
           ['S5', 1, '1-4-1/checkA/09', 0])
    return bad


def case_broken():
    def failing(src):
        def source(skill, w):
            if w['activity'] == 'check' and w.get('slot') == 3:
                raise OSError('تعذّر تحميل البند')
            return src(skill, w)
        return source
    e, sc, st, kid = at(17, failing)
    st.show(st.seq)
    before = st.snapshot()
    bad = []
    try:
        st.event(st.seq, ('confirm', 3))                    # الانتقال يطلب الخانة 3 فيفشل تحميلها
        bad.append('لم يظهر استثناء التحميل')
    except OSError:
        pass
    expect(bad, 'الطبقة معطّلة', st.broken, True)
    for label, fn in (('لقطة', st.snapshot), ('حدث', lambda: st.event(st.seq, ('confirm', 3)))):
        try:
            fn()
            bad.append('%s بعد انتقال لم يكتمل قُبل' % label)
        except RuntimeError:
            pass
    e2, sc2, notes = reopen('young', before)                # المحفوظ السابق كامل
    expect(bad, 'الاستعادة من المحفوظ السابق', [sc2.cur, sc2.elapsed, sc2.records[-1]['item'], count(e2, 'independence_result')],
           ['S4', 60, '1-4-1/checkA/03', 0])
    return bad


def case_session():
    e, sc, st, kid = at(17)
    seen = []
    for _ in range(3):                                      # ثلاثة إغلاقات في الجلسة نفسها، كل مرة قبل عرض البند
        e, sc, notes = reopen('young', st.snapshot())
        seen.append([sc.cur, sc.sessions, sc.searches, sc.elapsed])
        st = Stepper(e, sc)
        st.open(sc.g_continue())
        if st.pending is not None:
            item, w = st.pending
            for ev in kid.events(item, w):
                st.event(st.seq, ev)
    play(st, kid)
    bad = []
    expect(bad, 'الجلسة وعددها وجلسات البحث والوقت بعد كل استعادة', seen,
           [['S4', 4, 1, 60], ['S4', 4, 1, 120], ['S4', 4, 1, 180]])
    expect(bad, 'أحداث S4: بداية، بدء فحص، استئناف فحص، استئناف درس، ختم',
           [count(e, t, 'S4') for t in ('session_start', 'check_started', 'check_resumed', 'resume_lesson', 'session_end')],
           [1, 1, 0, 0, 1])
    expect(bad, 'بنود S4 المعروضة: الخانات الأربع ثم السقف', [(r['item']) for r in sc.records if r['activity'] == 'check'],
           ['1-4-1/checkA/01', '1-4-1/checkA/03', '1-4-1/checkA/05', '1-4-1/checkA/07'])
    expect(bad, 'بعد السقف', [sc.cur, sc.sessions, [(c['kind'], c['act']['slot']) for c in sc.saved]],
           [None, 4, [('check', 5)]])
    return bad


def case_newday():
    e, sc, st, kid = at(17)
    day = e.s['sessions']['S4']['day']
    e2, sc2, notes = reopen('young', st.snapshot(), today=day + 1)
    bad = []
    expect(bad, 'يوم S4', day, 3)
    expect(bad, 'ملاحظات الاستعادة في يوم جديد', [list(n) for n in notes], [['current_saved', 'check', '1-4-1'], ['session_closed', 'S4']])
    expect(bad, 'الجلسة بعدها', [sc2.cur, e2.s['current'], sc2.stage], [None, None, None])
    sc2.today = day + 1
    s2 = Stepper(e2, sc2)
    s2.open(sc2.g_follow_learning())
    expect(bad, 'الجلسة الجديدة', [sc2.cur, e2.s['sessions']['S5']['day'], count(e2, 'check_resumed', 'S5'), s2.pending[1]['slot']],
           ['S5', 4, 1, 2])
    e3, sc3, notes3 = reopen('young', st.snapshot(), today=day)
    expect(bad, 'الاستعادة في اليوم نفسه', [[list(n) for n in notes3], sc3.cur], [[['current_saved', 'check', '1-4-1']], 'S4'])
    return bad


def case_counters():
    # القاعدة: كل بند خُتم يدخل العدّاد مرة واحدة. المسار المتصل يعرض 20 بند فحص (10 لكل مهارة) و40 بندًا مسجَّلًا
    bad = []
    e0, sc0 = build('young')
    s0 = Stepper(e0, sc0)
    s0.open(sc0.g_run(14))
    play(s0, Kid())
    expect(bad, 'بلا إغلاق: عدّاد بنود الفحص وعدد السجلات', [sc0.n['check'], len(sc0.records)], [20, 40])
    e, sc, st, kid = at(17)                                 # بعد ختم الخانة 1، والخانة 2 لم تُعرض
    expect(bad, 'عدّاد الفحص في اللقطة بعد خانة واحدة', st.snapshot()['scheduler']['state']['n'].get('check'), 1)
    e2, sc2, _ = reopen('young', st.snapshot())
    s2 = Stepper(e2, sc2)
    s2.open(sc2.g_run(14))
    play(s2, kid)
    expect(bad, 'بعد إغلاق قبل العرض واستعادة: العدّاد والسجلات', [sc2.n['check'], len(sc2.records)], [20, 40])
    e, sc, st, kid = at(17)
    st.show(st.seq)                                         # الخانة 2 معروضة: تُختم منقطعة عند الاستعادة
    e3, sc3, _ = reopen('young', st.snapshot())
    expect(bad, 'بعد الاستعادة مباشرة: الخانة 1 والخانة 2 المنقطعة', [sc3.n['check'], len(sc3.records)], [2, 11])   # بوابة 2، افتتاح 3، دليل فهم 4، فحص 2. بنود الدرس بلا سجل
    s3 = Stepper(e3, sc3)
    s3.open(sc3.g_run(14))
    play(s3, kid)
    expect(bad, 'بعد إكمال المسار: البند المنقطع وبديله محتسبان مرة واحدة', [sc3.n['check'], len(sc3.records)], [21, 41])
    return bad


def void_of(records, item):
    return [(r['status'], r['first'], r['final'], r['support_before'], r.get('support_unanswered') or [], r.get('void'))
            for r in records if r['item'] == item]


def base_counts(sc):
    return [len(sc.records), dict(sc.n)]


def case_valid_restore():
    # القاعدة (8.3): إبطال جلسة أسهمت في محاولة غير مكتملة يجعلها «تحتاج إعادة بدء»، فلا تُستأنف. والاستئناف في
    # الجلسة نفسها لا يستهلك حصة، لكنه يتحقق من الصلاحية لحظة التنفيذ
    e, sc, st, kid = at(21)                                 # S5، خمس خانات منجزة، والخانة 6 (1-4-1/checkA/11) تنتظر
    r = e.apply(dict(id='t1', type='invalidate_session', target='S4'))
    rec = st.snapshot()
    e2, sc2, notes = reopen('young', rec)
    before = base_counts(sc2)
    s2 = Stepper(e2, sc2)
    s2.open(sc2.g_continue())
    bad = []
    expect(bad, 'قبول الإبطال وحالة المحاولة', [r['ok'], e2.s['checks']['1-4-1/check/1']['state']], [True, 'needs_restart'])
    expect(bad, 'بعد الاستعادة: لا بند معروض، والمولّد انتهى، والجلسة خُتمت', [s2.pending, s2.finished, sc2.cur], [None, True, None])
    expect(bad, 'سجل المجدول', [list(x) for x in sc2.log[-1:]], [[5, 'carry_dropped:check_state', '1-4-1']])
    expect(bad, 'المخزنان', [sc2.saved, sc2.parked], [[], {}])
    expect(bad, 'السجلات والعدّادات لم تتغير', base_counts(sc2), before)
    expect(bad, 'عدّاد بنود الفحص: الخانات الخمس', sc2.n['check'], 5)
    expect(bad, 'أحداث S5: استئناف واحد، ولا نتيجة', [count(e2, 'check_resumed', 'S5'), count(e2, 'independence_result')], [1, 0])
    return bad


def case_valid_live():
    bad = []
    # قبل عرض السؤال التالي
    e, sc, st, kid = at(21)
    before = base_counts(sc)
    e.apply(dict(id='t1', type='invalidate_session', target='S4'))
    shown = st.show(st.seq)
    expect(bad, 'قبل العرض: لم يُعرض، وسبب التوقف للبالغ', [shown, list(st.halt)], [False, ['S5', 'check_state', '1-4-1', 'check']])
    expect(bad, 'قبل العرض: سجل المجدول بلا إجابة مُهملة', [list(x) for x in sc.log if x[0] == 5],
           [[5, 'carry_dropped:check_state', '1-4-1']])
    expect(bad, 'قبل العرض: السجلات والعدّادات', base_counts(sc), before)
    # بعد عرض السؤال وقبل تأكيده
    e, sc, st, kid = at(21)
    st.show(st.seq)
    before, old = base_counts(sc), st.seq
    e.apply(dict(id='t1', type='invalidate_session', target='S4'))
    r1 = st.event(old, ('confirm', 7))
    r2 = st.event(old, ('confirm', 7))
    expect(bad, 'بعد العرض: نتيجة الإجابة ثم تكرارها', [r1, r2], ['void', 'ignored'])
    expect(bad, 'بعد العرض: سجل المجدول', [list(x) for x in sc.log if x[0] == 5],
           [[5, 'carry_dropped:check_state', '1-4-1'], [5, 'answer_void:check_state', '1-4-1']])
    # البند عُرض قبل الإبطال: عرضه يُحفظ سجلًا مستبعدًا بلا إجابة (R17-01، و9.1: عرض البند حدث في السجل). والإجابة التي
    # جاءت بعد الإبطال ليست فيه، ولا عدّاد ولا نتيجة
    expect(bad, 'بعد العرض: سجل واحد مستبعد بلا إجابة، والعدّادات كما هي، ولا نتيجة',
           [len(sc.records) - before[0], dict(sc.n) == before[1], void_of(sc.records, '1-4-1/checkA/11'),
            count(e, 'independence_result')],
           [1, True, [('interrupted', None, 'incomplete', [], [], 'check_state')], 0])
    expect(bad, 'بعد العرض: الجلسة خُتمت والمحاولة كما هي', [e.s['sessions']['S5']['ended'],
                                                           e.s['checks']['1-4-1/check/1']['state']], [True, 'needs_restart'])
    return bad


def case_valid_temporary():
    # القاعدة (8.3): إبطال الدليل الذي فتح مهارة يعلّق أنشطتها حتى إعادة التحقق. هذا منع مؤقت: يُركن النشاط بتقدّمه
    e, sc, st, kid = at(39)                                 # S8، دليل فهم 1-4-2: بند واحد منجز، والثاني معروض
    st.show(st.seq)
    before = base_counts(sc)
    r = e.apply(dict(id='t1', type='invalidate_session', target='S6'))   # الجلسة التي اجتيز فيها فحص 1-4-1
    res = st.event(st.seq, ('confirm', 4))
    bad = []
    expect(bad, 'الإبطال والتعليق', [r['ok'], sorted(e.s['suspended'])], [True, ['1-4-2']])
    expect(bad, 'نتيجة الإجابة وسبب التوقف', [res, list(st.halt)], ['void', ['S8', 'suspended', '1-4-2', 'evidence']])
    p = sc.parked.get('1-4-2') or {}
    expect(bad, 'النشاط مركون بتقدّمه: بند واحد منجز', [p.get('kind'), (p.get('act') or {}).get('shown'), p.get('items')],
           ['evidence', {'evidence': 1}, ['1-4-2/evidence/01']])
    expect(bad, 'سجل المجدول في S8', [list(x) for x in sc.log if x[0] == 8],
           [[8, 'carry_parked:suspended', '1-4-2'], [8, 'answer_void:suspended', '1-4-2']])
    expect(bad, 'سجل واحد مستبعد للبند المعروض بلا إجابة (R17-01)، والعدّادات كما هي',
           [len(sc.records) - before[0], dict(sc.n) == before[1], void_of(sc.records, '1-4-2/evidence/02')],
           [1, True, [('interrupted', None, 'incomplete', [], [], 'suspended')]])
    expect(bad, 'S8 خُتمت', e.s['sessions']['S8']['ended'], True)
    return bad


RESULTS = ('pass', 'fail', 'help')
VARIANTS = dict(gate=[dict(result=r) for r in RESULTS + ('interrupted',)], short=[dict(ok=True), dict(ok=False)],
                opening=[dict(outcome=o) for o in ('skip', 'full_error', 'full_help')], evidence=[dict()],
                check=[dict(result=r) for r in RESULTS], retention=[dict(correct=c) for c in range(6)])
TYPE = dict(gate='gate_result', short='short_check_result', opening='lesson_opening_result',
            evidence='understanding_proved', check='independence_result', retention='retention_result')


def verdicts(e, sc):
    v = sc.live
    if v is None or v['kind'] == 'show':
        return None
    act, kind = v['act'], v['kind']
    base = dict(type=TYPE[kind], id='ask', session=sc.cur, skill=act.skill)
    if kind == 'check':
        base['check_id'] = act.check_id
    got = []
    for extra in VARIANTS[kind]:
        r = e.preflight(dict(base, **extra))
        got.append('ok' if r['ok'] else r['code'])
    c = e.may_continue(kind, sc.cur, act.skill, getattr(act, 'check_id', None))
    return kind, got, 'ok' if c['ok'] else c['code']


def case_valid_healthy():
    bad = []
    # حالة سليمة: الاستئناف في الجلسة نفسها يعرض البند نفسه بلا حصة ولا حدث استئناف إضافيين
    e, sc, st, kid = at(21)
    e2, sc2, notes = reopen('young', st.snapshot())
    s2 = Stepper(e2, sc2)
    s2.open(sc2.g_continue())
    expect(bad, 'سليمة: البند المعروض، واستئنافات S5، وحصتها التعليمية المستهلكة',
           [s2.pending[0]['id'], count(e2, 'check_resumed', 'S5'), e2.s['sessions']['S5']['teach']], ['1-4-1/checkA/11', 1, 1])
    # حكم الاستمرار لا يقرأ النتيجة: عند كل طلب بند في المسار، وبعد كل إبطال من الثلاثة، حكم قبول حدث الختام واحد
    # لكل قيم نتيجته، وهو حكم may_continue نفسه
    seen, split = {}, []
    def probe(e, sc, label):
        v = verdicts(e, sc)
        if v is None:
            return
        kind, got, c = v
        seen.setdefault(kind, set()).add(c)
        if len(set(got)) != 1 or got[0] != c:
            split.append((label, kind, got, c))
    e, sc = build('retention')
    st, kid = Stepper(e, sc), Kid()
    st.open(sc.g_run(100))
    k = 0
    while st.pending is not None:
        probe(e, sc, k)
        item, w = st.pending
        for ev in kid.events(item, w):
            st.event(st.seq, ev)
        k += 1
    for n, target in ((21, 'S4'), (21, 'S3'), (39, 'S6'), (1, None), (13, 'S2')):
        e, sc, st, kid = at(n)
        if target:
            e.apply(dict(id='t1', type='invalidate_session', target=target))
        else:
            e.apply(dict(id='t1', type='session_end', session=sc.cur))      # جلسة خُتمت من خارج المجدول
        probe(e, sc, (n, target))
    expect(bad, 'مواضع يختلف فيها الحكم باختلاف النتيجة', split, [])
    # جرد لما بلغه الفحص، لا نتيجة مشتقة من قاعدة: يثبت أن المقارنة جرت على أحكام قبول ورفض متنوعة
    expect(bad, 'الأنواع المفحوصة وأحكامها', {k: sorted(v) for k, v in sorted(seen.items())},
           dict(check=['check_state', 'ok', 'understanding_first'], evidence=['lesson_idle', 'ok', 'suspended'],
                gate=['no_session', 'ok'], opening=['ok'], retention=['ok']))
    return bad


def case_help_check():
    # القاعدة (3.1 و3.6): «أحتاج مساعدة» في بند فحص ينهي البند منقطعًا ومعه الطلب، ويغلق المحاولة «انتهت بطلب دعم»،
    # لا «لم تُجتز». والمحاولة التالية في يوم لاحق وببنود جديدة
    e, sc, st, kid = at(17)                                 # S4، الخانة 2، البند 1-4-1/checkA/03
    st.show(st.seq)
    old = st.seq
    r1 = st.event(old, ('support', 'requested'))
    r2 = st.event(old, ('support', 'requested'))
    bad = []
    expect(bad, 'نتيجة الطلب ثم تكراره', [r1, r2], ['next', 'ignored'])
    res = [x['result'] for x in e.s['log'] if x['type'] == 'independence_result']
    expect(bad, 'نتائج الفحص في المحرك وحالة المحاولة', [res, e.s['checks']['1-4-1/check/1']['state']], [['help'], 'closed'])
    rec = [r for r in sc.records if r['item'] == '1-4-1/checkA/03']
    expect(bad, 'سجل البند: مرة واحدة، منقطع، ومعه الطلب، بلا إجابة',
           [(r['status'], r['first'], r['support_before'], r['final']) for r in rec],
           [('interrupted', None, ['requested'], 'incomplete')])
    e2, sc2, notes = reopen('young', st.snapshot())         # اللقطة بعد الطلب لا تعيد فتح الفحص
    # المولّد مضى إلى اليوم التالي وبدأ المحاولة الثانية (3.6: بعد «انتهت بطلب دعم» يكفي اليوم اللاحق)، فالفحص
    # الجاري في اللقطة هو المحاولة الثانية. المحاولة الأولى مغلقة ولا تُفتح
    expect(bad, 'بعد الاستعادة: الفحص المحفوظ هو المحاولة الثانية وحدها، والأولى مغلقة بنتيجة واحدة',
           [[c['act']['check_id'] for c in sc2.saved if c['kind'] == 'check'], count(e2, 'independence_result'),
            e2.s['checks']['1-4-1/check/1']['state']], [['1-4-1/check/2'], 1, 'closed'])
    s2 = Stepper(e2, sc2)
    s2.open(sc2.g_run(14))
    play(s2, kid)
    second = [x for x in e2.s['log'] if x['type'] == 'check_started' and x['check_id'] == '1-4-1/check/2']
    day = lambda x: e2.s['sessions'][x['session']]['day']
    expect(bad, 'المحاولة الثانية: بدأت مرة، وفي يوم بعد يوم الأولى (3)', [len(second), bool(second) and day(second[0]) > 3], [1, True])
    later = [r['item'].split('/')[1] for r in sc2.records if r['activity'] == 'check' and r['skill'] == '1-4-1'][2:]
    expect(bad, 'بنود المحاولة الثانية كلها من مجموعتها الجديدة', sorted(set(later)), ['checkB'])
    expect(bad, 'نتائج فحص 1-4-1 بترتيبها', [x['result'] for x in e2.s['log'] if x['type'] == 'independence_result'
                                               and x['skill'] == '1-4-1'], ['help', 'pass'])
    return bad


def case_help_gate():
    # القاعدة (6.1): طلب الدعم في البوابة ينهيها «انتهت بطلب دعم»، ولا تُسجَّل المهارة «متعثّر فيها»
    e, sc, st, kid = at(0)                                  # S1، أول بند في بوابة 1-4-1
    old = st.seq
    r1 = st.event(old, ('support', 'requested'))
    r2 = st.event(old, ('support', 'requested'))
    bad = []
    expect(bad, 'نتيجة الطلب ثم تكراره', [r1, r2], ['next', 'ignored'])
    expect(bad, 'نتائج البوابة في المحرك', [x['result'] for x in e.s['log'] if x['type'] == 'gate_result'], ['help'])
    expect(bad, 'حالة المهارة ليست «متعثّر فيها»', e.derive()['1-4-1'] != 'stumbled', True)
    rec = sc.records[0]
    expect(bad, 'سجل البند', [rec['item'], rec['status'], rec['first'], rec['support_before']],
           ['1-4-1/gate/01', 'interrupted', None, ['requested']])
    expect(bad, 'عدد سجلات البوابة: بند واحد', len(sc.records), 1)
    return bad


def case_contract():
    # العقد: الحدث غير المسموح يُرفض قبل أي تغيير، بسبب واضح
    bad = []

    def refused(n, events, label):
        e, sc, st, kid = at(n)
        st.show(st.seq)
        before, seq = dump(st.snapshot()), st.seq
        got = [(st.event(seq, ev), bool(st.reject)) for ev in events]
        expect(bad, label + ': كلها مرفوضة بسبب', got, [('rejected', True)] * len(events))
        expect(bad, label + ': لا تغيير في اللقطة ولا في الطلب', [dump(st.snapshot()) == before, st.seq == seq, st.raw], [True, True, []])
        return st, seq
    st, seq = refused(12, [('support', 'requested'), ('support', 'adult'), ('end',), ('foo',), ('confirm',),
                           ('confirm', '6'), 'confirm', ('support',), ()], 'بند تعليم (دليل فهم)')
    expect(bad, 'بند تعليم: تلميح ثم إجابة ثم إنهاء', [st.event(seq, ('support', 'hint')), st.event(seq, ('confirm', 6)),
                                                    st.event(seq, ('end',))], ['open', 'open', 'next'])
    st, seq = refused(17, [('support', 'hint'), ('support', 'someone'), ('support', 'adult'), ('end',), ('interrupt',)],
                      'بند تقييم (فحص)')
    expect(bad, 'بند تقييم: التأكيد ينهيه', st.event(seq, ('confirm', 3)), 'next')
    st, seq = refused(5, [('confirm', 5), ('support', 'hint'), ('support', 'requested')], 'بند عرض (درس)')
    expect(bad, 'بند عرض: الإنهاء', st.event(seq, ('end',)), 'next')
    return bad


def case_help_retention():
    # مستوى البند وحده (3.1 بقرار 17 نوفمبر): الطلب ينهي بند فحص الاحتفاظ منقطعًا ومعه الطلب. أثره على الجولة
    # (تنتهي بلا نتيجة، ثم تثبيت، ثم جولة في يوم لاحق ببنود بديلة) نُفّذ في ت3 وتفحصه tests/test_retention_help
    e, sc = build('retention')
    st, kid = Stepper(e, sc), Kid()
    st.open(sc.g_run(100))
    while st.pending is not None and st.pending[1]['activity'] != 'retention':
        item, w = st.pending
        for ev in kid.events(item, w):
            st.event(st.seq, ev)
    item, old = st.pending[0], st.seq
    r1 = st.event(old, ('support', 'requested'))
    r2 = st.event(old, ('support', 'requested'))
    rec = [r for r in sc.records if r['item'] == item['id']]
    bad = []
    expect(bad, 'نتيجة الطلب ثم تكراره', [r1, r2], ['next', 'ignored'])
    expect(bad, 'سجل البند: مرة واحدة، منقطع، ومعه الطلب', [(r['activity'], r['status'], r['first'], r['support_before']) for r in rec],
           [('retention', 'interrupted', None, ['requested'])])
    return bad


def served_after(e, st, kid, skill='1-4-2'):
    """يكمل المسار إلى نهايته، ويعيد بنود دليل فهم المهارة التي عُرضت: المعرّف والدور والبند الذي يحل محله وعدّ الإعادة."""
    out = []
    while st.pending is not None:
        item, w = st.pending
        if w['activity'] == 'evidence' and item['skill'] == skill:
            out.append((item['id'][-2:], w['role'], (w.get('replaces') or '')[-2:], w['reshown']))
        for ev in kid.events(item, w):
            st.event(st.seq, ev)
    return out


def proofs(e, skill='1-4-2'):
    return [[i[-2:] for i in x.get('items', [])] for x in e.s['log'] if x['type'] == 'understanding_proved' and x['skill'] == skill]


def case_void_history():
    # القاعدة (R17-01): ما سُجّل في البند قبل تغيّر الصلاحية يبقى محفوظًا مع سبب استبعاده، مرة واحدة. لا يتقدم النشاط
    # به، ولا يدخل المؤشرات، والحدث الذي جاء بعد التغيّر لا يُحتسب
    bad = []
    ITEM = '1-4-2/evidence/02'                              # S8، دليل فهم 1-4-2. قبله بند واحد منجز
    # أ) إجابة مؤكدة خاطئة ثم طلب تلميح، ثم التعليق، ثم إنهاء
    e, sc, st, kid = at(39)
    n0, ind0 = dict(sc.n), dump(indicators(sc.records))
    r = [st.event(st.seq, ('confirm', 999)), st.event(st.seq, ('support', 'hint'))]
    held = st.snapshot()['current']['journal']['raw']
    e.apply(dict(id='t1', type='invalidate_session', target='S6'))
    r.append(st.event(st.seq, ('end',)))
    expect(bad, 'أ: نتائج الأحداث الثلاثة', r, ['open', 'open', 'void'])
    expect(bad, 'أ: اللقطة قبل التعليق تحمل الحدثين', held, [['confirm', 999], ['support', 'hint']])
    want = [('complete', False, 'incomplete', [], ['hint'], 'suspended')]
    expect(bad, 'أ: سجل البند بعد التوقف: مرة واحدة، بالإجابة الأولى والتلميح وسبب الاستبعاد', void_of(sc.records, ITEM), want)
    p = sc.parked.get('1-4-2') or {}
    expect(bad, 'أ: النشاط مركون عند بنده المنجز الواحد، بلا البند المستبعد',
           [(p.get('act') or {}).get('shown'), p.get('items')], [{'evidence': 1}, ['1-4-2/evidence/01']])
    expect(bad, 'أ: العدّادات والمؤشرات لا يدخلها البند المستبعد', [dict(sc.n) == n0, dump(indicators(sc.records)) == ind0],
           [True, True])
    snap = st.snapshot()
    j = (snap['current'] or {}).get('journal') or {}
    expect(bad, 'أ: اللقطة بعد التوقف: السجل فيها مرة، وليس في بند جارٍ', [void_of(snap['records'], ITEM), j.get('item') == ITEM],
           [want, False])
    e2, sc2, _ = reopen('young', snap)
    e3, sc3, _ = reopen('young', persist.snapshot(e2, sc2))
    expect(bad, 'أ: بعد استعادتين', [void_of(sc2.records, ITEM), void_of(sc3.records, ITEM)], [want, want])
    expect(bad, 'أ: النشاط باقٍ مركونًا ولا دليل فهم جديد', ['1-4-2' in sc3.parked, count(e3, 'understanding_proved', skill='1-4-2')],
           [True, 0])
    # ب) طلب دعم بلا إجابة قبل التعليق، ثم إجابة بعده
    e, sc, st, kid = at(39)
    r = [st.event(st.seq, ('support', 'hint'))]
    e.apply(dict(id='t1', type='invalidate_session', target='S6'))
    r.append(st.event(st.seq, ('confirm', 4)))
    expect(bad, 'ب: نتائج الحدثين', r, ['open', 'void'])
    expect(bad, 'ب: سجل البند: منقطع ومعه التلميح، والإجابة اللاحقة ليست فيه', void_of(sc.records, ITEM),
           [('interrupted', None, 'incomplete', ['hint'], [], 'suspended')])
    # ج) بند عُرض بلا حدث، ثم إجابة بعد التعليق: عرضه محفوظ (9.1: عرض البند حدث في السجل)، والإجابة لا تُحتسب
    e, sc, st, kid = at(39)
    st.show(st.seq)
    e.apply(dict(id='t1', type='invalidate_session', target='S6'))
    r = st.event(st.seq, ('confirm', 4))
    expect(bad, 'ج: نتيجة الإجابة وسجل البند المعروض', [r, void_of(sc.records, ITEM)],
           ['void', [('interrupted', None, 'incomplete', [], [], 'suspended')]])
    # د) الحدثان في اللقطة، والتعليق قبل الاستعادة: الاستعادة تحفظهما مستبعدَين ولا تعطيهما للنشاط
    e, sc, st, kid = at(39)
    n0 = dict(sc.n)
    st.event(st.seq, ('confirm', 999))
    st.event(st.seq, ('support', 'hint'))
    e.apply(dict(id='t1', type='invalidate_session', target='S6'))
    e2, sc2, notes = reopen('young', st.snapshot())
    expect(bad, 'د: ملاحظات الاستعادة', [list(n) for n in notes],
           [['void_item', '1-4-2', ITEM, 'suspended'], ['current_saved', 'evidence', '1-4-2']])
    expect(bad, 'د: السجل والعدّاد والنشاط المحفوظ', [void_of(sc2.records, ITEM), dict(sc2.n) == n0,
                                                      [c['act']['shown'] for c in sc2.saved if c['kind'] == 'evidence']],
           [want, True, [{'evidence': 1}]])
    s2 = Stepper(e2, sc2)
    s2.open(sc2.g_continue())
    e3, sc3, _ = reopen('young', s2.snapshot())
    expect(bad, 'د: بعد التكملة واستعادة ثانية: مركون، والسجل مرة واحدة', ['1-4-2' in sc3.parked, void_of(sc3.records, ITEM)],
           [True, want])

    # R18-01: الاستبعاد من التقييم لا يمحو التعرّض. بعد رفع التعليق لا يعود البند الذي أُجيب عنه وطُلب فيه تلميح دليلًا
    # جديدًا: يحل محله بديل نوعه في الجولة (25: ف2، الجولة 1، حقيقته 1 و9 لم ترد في بنود نوعه الأربعة). ثم ف3 (05، 06)
    # ثم ف4 (09، 10) كما هي. والبند 01 المنجز قبل التعليق باقٍ في الدليل
    AFTER = [('25', 'evidence.alternate', '02', 0), ('05', 'evidence', '', 0), ('06', 'evidence', '', 0),
             ('09', 'evidence', '', 0), ('10', 'evidence', '', 0)]
    PROOF = [['01', '25', '05', '06', '09', '10']]

    def exposed_then_void(source=None):
        e, sc, st, kid = at(39, source)
        st.event(st.seq, ('confirm', 999))
        st.event(st.seq, ('support', 'hint'))
        e.apply(dict(id='t1', type='invalidate_session', target='S6'))
        st.event(st.seq, ('end',))
        return e, sc, st, kid

    def verdict(label, e, sc, got):
        alt = [(r['status'], r['first'], r.get('replaces'), r.get('fact_seen_before'), r.get('void'))
               for r in sc.records if r['item'] == '1-4-2/evidence/25']
        expect(bad, label + ': البنود المعروضة بعد رفع التعليق', got, AFTER)
        expect(bad, label + ': دليل الفهم مرة واحدة ببنوده، وليس البند المستبعد منها', proofs(e), PROOF)
        expect(bad, label + ': السجل المستبعد مرة واحدة، ولا سجل آخر للبند', void_of(sc.records, ITEM), want)
        expect(bad, label + ': سجل البديل يذكر البند الذي حلّ محله وأن حقيقته سبق عرضها',
               alt, [('complete', True, ITEM, True, None)])

    # هـ) المسار المتصل إلى نهايته
    e, sc, st, kid = exposed_then_void()
    verdict('هـ', e, sc, served_after(e, st, kid))
    # و) إغلاق بعد التوقف مباشرة، ثم استعادة وتكملة
    e, sc, st, kid = exposed_then_void()
    e2, sc2, _ = reopen('young', st.snapshot())
    s2 = Stepper(e2, sc2)
    s2.open(sc2.g_run(14))
    verdict('و', e2, sc2, served_after(e2, s2, kid))
    # ز) إغلاق والبديل مطلوب لم يُعرض بعد، ثم استعادة وتكملة
    e, sc, st, kid = exposed_then_void()
    while st.pending is not None and st.pending[1].get('role') != 'evidence.alternate':
        for ev in kid.events(*st.pending):
            st.event(st.seq, ev)
    e2, sc2, _ = reopen('young', st.snapshot())
    s2 = Stepper(e2, sc2)
    s2.open(sc2.g_run(14))
    verdict('ز', e2, sc2, served_after(e2, s2, kid))
    # ح) لا بديل في المحتوى: نفاده يُعلن في سجل المجدول، والجولة تنتهي بلا حكم (لا «لم يثبت»). لا يُعاد البند 02.
    # ثم الجولة الثانية ببنودها: ف2 (13، 14) ثم ف3 (17، 18) ثم ف4 (21، 22)
    def without(src):
        return lambda s, w: None if w.get('role') == 'evidence.alternate' else src(s, w)
    e, sc, st, kid = exposed_then_void(without)
    got = served_after(e, st, kid)
    marks = [x[1] for x in sc.log if x[2] == '1-4-2' and x[1].startswith('evidence_')]
    expect(bad, 'ح: نفاد البدائل معلن، وبلا «لم يثبت»', marks, ['evidence_no_alternate'])
    expect(bad, 'ح: بنود الجولة الثانية، وليس البند 02 منها', [g[0] for g in got], ['13', '14', '17', '18', '21', '22'])
    expect(bad, 'ح: دليل الفهم ببنود الجولة الثانية وحدها', proofs(e), [['13', '14', '17', '18', '21', '22']])
    expect(bad, 'ح: السجل المستبعد باقٍ مرة واحدة', void_of(sc.records, ITEM), want)
    # ط) بند عُرض بلا حدث ثم استُبعد: لم تُقبل فيه إجابة في محاولة صالحة، فيُعاد عرضه نفسه موصوفًا بالإعادة (3.5)، ويدخل الدليل
    e, sc, st, kid = at(39)
    st.show(st.seq)
    e.apply(dict(id='t1', type='invalidate_session', target='S6'))
    st.event(st.seq, ('end',))
    got = served_after(e, st, kid)
    expect(bad, 'ط: البند نفسه يُعاد عرضه وعدّ الإعادة 1', got[:2], [('02', 'evidence', '', 1), ('05', 'evidence', '', 0)])
    expect(bad, 'ط: الدليل ببنوده الأصلية', proofs(e), [['01', '02', '05', '06', '09', '10']])
    return bad


def case_first_item():
    # القاعدة (R19-01): تاريخ التعرّض في السجلات، لا في كائن النشاط. التعليق أثناء أول بند في دليل الفهم يُسقط النشاط
    # (لم يكتمل فيه بند)، ثم يُنشأ نشاط جديد بعد رفع التعليق. البند 01 (ف2، الجولة 1) إن طُلب فيه دعم أو أُكدت فيه
    # إجابة لا يعود: بديله 25. وإن عُرض فقط ولم تُقبل فيه إجابة في محاولة صالحة أُعيد عرضه وعدّ الإعادة 1.
    # وبلا بدائل في المحتوى: يُعلن النفاد، ثم الجولة الثانية ببنودها
    bad = []
    ITEM = '1-4-2/evidence/01'
    ALT = [('25', 'evidence.alternate', '01', 0), ('02', 'evidence', '', 0), ('05', 'evidence', '', 0),
           ('06', 'evidence', '', 0), ('09', 'evidence', '', 0), ('10', 'evidence', '', 0)]
    SAME = [('01', 'evidence', '', 1)] + ALT[1:]
    ROUND2 = [(i, 'evidence', '', 0) for i in ('13', '14', '17', '18', '21', '22')]
    KINDS = (('طلب دعم فقط', [('support', 'hint')], ('interrupted', None, 'incomplete', ['hint'], [], 'suspended'), ALT),
             ('إجابة مؤكدة', [('confirm', 999)], ('complete', False, 'incomplete', [], [], 'suspended'), ALT),
             ('العرض وحده', None, ('interrupted', None, 'incomplete', [], [], 'suspended'), SAME))

    def without(src):
        return lambda s, w: None if w.get('role') == 'evidence.alternate' else src(s, w)

    def run(evs, mode, bare):
        e, sc, st, kid = at(38, without if bare else None)
        if st.pending[0]['id'] != ITEM or e.s['current'] != 'S8':
            raise AssertionError('الموضع 38 ليس أول بند دليل الفهم في S8')
        if evs is None:
            st.show(st.seq)
        for ev in evs or ():
            st.event(st.seq, ev)
        e.apply(dict(id='t1', type='invalidate_session', target='S6'))
        if mode != 'قبل التوقف':
            st.event(st.seq, ('confirm', 6))                # تصل بعد التعليق: لا تُحتسب
        if mode != 'متصل':
            e, sc, _ = reopen('young', st.snapshot())
            if bare:
                sc.source = without(sc.source)
            st = Stepper(e, sc)
            st.open(sc.g_run(14))
        return e, sc, served_after(e, st, kid)

    for name, evs, rec, after in KINDS:
        for mode in ('متصل', 'قبل التوقف', 'بعد التوقف'):
            label = '%s، %s' % (name, mode)
            e, sc, got = run(evs, mode, False)
            expect(bad, label + ': البنود المعروضة بعد رفع التعليق', got, after)
            expect(bad, label + ': دليل الفهم مرة واحدة ببنوده', proofs(e), [[g[0] for g in after]])
            expect(bad, label + ': السجل المستبعد مرة واحدة' + ('' if after is SAME else '، ولا سجل آخر للبند'),
                   [x for x in void_of(sc.records, ITEM) if x[5]], [rec])
            expect(bad, label + ': عدد سجلات البند', len(void_of(sc.records, ITEM)), 2 if after is SAME else 1)
            if after is SAME:
                continue
            e, sc, got = run(evs, mode, True)               # المحتوى بلا بدائل
            marks = [x[1] for x in sc.log if x[2] == '1-4-2' and x[1].startswith('evidence_')]
            expect(bad, label + '، بلا بدائل: النفاد معلن مرة، وبلا «لم يثبت»', marks, ['evidence_no_alternate'])
            expect(bad, label + '، بلا بدائل: الجولة الثانية ببنودها، وليس 01 منها', got, ROUND2)
            expect(bad, label + '، بلا بدائل: الدليل ببنود الجولة الثانية', proofs(e), [[g[0] for g in ROUND2]])
            expect(bad, label + '، بلا بدائل: السجل المستبعد مرة واحدة', void_of(sc.records, ITEM), [rec])
    return bad


def case_opening_void():
    # القاعدة (R18-01 في افتتاح الدرس): إعادة البند للتعليم غير استعماله دليلًا لقرار.
    # افتتاح 1-4-2 في S7: «جرّب أولًا» tryfirst/03 ثم tryfirst/04، ثم الموجَّهة opening/03 و04 و05.
    # الطفل هنا يخطئ قبل الدرس، ثم يعرف المهارة بعد التعليق (كأنه تعلّمها خارج التطبيق)، ليظهر أثر البند المعاد
    bad = []

    def run(n, evs, mode):
        e, sc, st, kid = at(n)
        first = st.pending[0]['id']
        for ev in evs:
            st.event(st.seq, ev)
        e.apply(dict(id='t1', type='invalidate_session', target='S6'))
        if mode != 'قبل التوقف':
            st.event(st.seq, ('end',))
        if mode != 'متصل':
            e, sc, _ = reopen('young', st.snapshot())
            st = Stepper(e, sc)
            st.open(sc.g_run(14))
        kid.known.add('1-4-2')
        out = []
        while st.pending is not None:
            item, w = st.pending
            if w['activity'] == 'opening' and item['skill'] == '1-4-2':
                out.append((item['id'][6:], w['reshown'], bool(w.get('repeated'))))
            for ev in kid.events(item, w):
                st.event(st.seq, ev)
        res = [x['outcome'] for x in e.s['log'] if x['type'] == 'lesson_opening_result' and x['skill'] == '1-4-2']
        marked = [r['item'][6:] for r in sc.records if r.get('repeated_after_void')]
        return first[6:], out, res, marked

    GUIDED = [('opening/03', 0, False), ('opening/04', 0, False), ('opening/05', 0, False)]
    EXPOSED = [('confirm', 999), ('support', 'hint')]
    for mode in ('متصل', 'قبل التوقف', 'بعد التوقف'):
        # أ) أول بند «جرّب أولًا» مستهلك: لا يُعرض ثانية ولا بديل له. الثاني يُعرض ويصح، ولا يُتخطى الشرح بهما:
        #    تأتي الموجَّهة الثلاث، وتصح كلها فينتهي الدرس مبكرًا بها (skip)، لا بالبند المستهلك
        got = run(28, EXPOSED, mode)
        expect(bad, 'أ، %s' % mode, got, ('tryfirst/03', [('tryfirst/04', 0, False)] + GUIDED, ['skip'], []))
        # ب) ثاني بند «جرّب أولًا» مستهلك (والأول أُجيب خطأً قبل التعليق): لا يُعرض ثانية، ثم الموجَّهة الثلاث
        got = run(29, EXPOSED, mode)
        expect(bad, 'ب، %s' % mode, got, ('tryfirst/04', GUIDED, ['skip'], []))
        # ج) أول بند موجَّه مستهلك: يُعاد عرضه للتعليم موسومًا بأنه مكرر، ونجاحه لا ينهي الدرس مبكرًا ولا يُسجَّل تعثّر:
        #    الدرس كاملًا (full_help)، ولا تُعرض بقية الموجَّهة
        got = run(30, EXPOSED, mode)
        expect(bad, 'ج، %s' % mode, got, ('opening/03', [('opening/03', 1, True)], ['full_help'], ['opening/03']))
        # د) بند موجَّه عُرض ولم تُقبل فيه إجابة في محاولة صالحة: يُعاد عرضه موسومًا بالإعادة، ويُحتسب كغيره
    e, sc, st, kid = at(30)
    st.show(st.seq)
    e.apply(dict(id='t1', type='invalidate_session', target='S6'))
    st.event(st.seq, ('end',))
    kid.known.add('1-4-2')
    out = []
    while st.pending is not None:
        item, w = st.pending
        if w['activity'] == 'opening' and item['skill'] == '1-4-2':
            out.append((item['id'][6:], w['reshown'], bool(w.get('repeated'))))
        for ev in kid.events(item, w):
            st.event(st.seq, ev)
    res = [x['outcome'] for x in e.s['log'] if x['type'] == 'lesson_opening_result' and x['skill'] == '1-4-2']
    expect(bad, 'د: المعروض بلا إجابة مقبولة', [out, res], [[('opening/03', 1, False)] + GUIDED[1:], ['skip']])
    return bad


print('ب) حالات بنتائج مكتوبة يدويًا')
for title, fn in (
        ('1. إغلاق عند عرض البند (الخانة 2 من الفحص): يُختم «غير محسوم» منقطعًا، والجلسة S4 نفسها تُكمَل بوقتها (60 ثانية) '
         'وببديل الخانة، بلا بداية جلسة ولا استئناف فحص، ويُجتاز الفحص، والبند المنقطع في السجلات مرة واحدة', case_shown),
        ('2. إغلاق بعد طلب دعم في بند دليل فهم: السجل منقطع ومعه الدعم، والجلسة S3 تُكمَل بلا استئناف درس ثانٍ', case_support),
        ('3. إغلاق بعد إجابة غير نهائية (خاطئة) في بند دليل فهم: الإجابة الأولى الخاطئة محفوظة، والبند «مكتمل» بقاعدة 3.1 ونتيجته النهائية «لم تكتمل»',
         case_nonfinal),
        ('4. الإجابة النهائية انتقال واحد: آخر خانة تُصدر نتيجة الفحص مرة واحدة، وتكرار التأكيد يُهمل. اللقطة بعده تُستعاد '
         'كاملة والبند التالي يُطلب نفسه. والمحفوظ قبله كامل: لا نتيجة في المحرك والبند «غير محسوم»', case_final),
        ('5. بلوغ السقف بعد ختم البند: تُختم الجلسة ويُحفظ الفحص عند الخانة 5، واللقطة بلا نشاط جارٍ، والجلسة التالية تستأنفه '
         'بحدث واحد ووقت من الصفر', case_cap),
        ('6. استثناء داخل الانتقال: الطبقة تتعطل فلا لقطة ولا حدث بعده، والمحفوظ السابق يُستعاد كاملًا', case_broken),
        ('7. ثلاثة إغلاقات في جلسة واحدة: لا جلسة جديدة ولا جلسة بحث، والوقت 60 ثم 120 ثم 180 لا يبدأ من الصفر، ولا حدث '
         'استئناف يستهلك حصة، والسقف يحلّ بعد الخانة الرابعة كما في التشغيل المتصل', case_session),
        ('8. انتقال يوم الأسرة: الاستعادة في يوم جديد تختم S4، والجلسة التالية S5 تستأنف الفحص بحدثه. وفي اليوم نفسه تبقى '
         'S4 مفتوحة', case_newday),
        ('9. العدّادات (R16-03): كل بند خُتم يُحتسب مرة واحدة. 20 بند فحص و40 سجلًا بلا إغلاق وبعد إغلاق واستعادة. والبند '
         'الذي يُختم منقطعًا أثناء الاستعادة يدخل العدّاد عندها، فيصير المجموع 21 و41 مع بديله', case_counters),
        ('10. الصلاحية قبل الاستعادة (R16-01): أُبطلت S4 والفحص في S5 ينتظر الخانة 6، ثم حُفظ واستُعيد. لا يُعرض بند: يُسقط '
         'النشاط «يحتاج إعادة بدء»، وتُختم الجلسة، والسجلات والعدّادات كما هي، ولا نتيجة', case_valid_restore),
        ('11. الصلاحية في الجلسة الحية (R16-01): إبطال قبل عرض السؤال التالي فلا يُعرض، وإبطال بعد عرضه وقبل تأكيده فلا '
         'تُحتسب الإجابة دليلًا ولا خطأً، وتكرارها يُهمل. والسبب يُحفظ للبالغ', case_valid_live),
        ('12. المنع المؤقت (R16-01): تعليق المهارة أثناء دليل فهمها يركن النشاط بتقدّمه ولا يُسقطه، والإجابة لا تُحتسب',
         case_valid_temporary),
        ('13. حالة سليمة: الاستئناف في الجلسة نفسها بلا حصة ولا حدث إضافيين. وحكم الاستمرار لا يقرأ النتيجة: هو حكم '
         'قبول حدث الختام لكل قيم نتيجته، عند كل طلب بند وبعد كل إبطال', case_valid_healthy),
        ('14. «أحتاج مساعدة» في فحص الاستقلال (R16-02): طلب واحد ينهي البند والمحاولة «انتهت بطلب دعم» بلا إخفاق، وتكراره '
         'يُهمل، واللقطة بعده لا تعيد فتح الفحص، والمحاولة الثانية في يوم لاحق ببنود جديدة', case_help_check),
        ('15. «أحتاج مساعدة» في البوابة (R16-02): تنتهي «انتهت بطلب دعم»، ولا تُسجَّل المهارة «متعثّر فيها»', case_help_gate),
        ('16. عقد الأحداث (R16-02): نوع غير مسموح للبند يُرفض بسبب قبل أي تغيير، في بند تعليم وبند تقييم وبند عرض',
         case_contract),
        ('17. «أحتاج مساعدة» في فحص الاحتفاظ، مستوى البند وحده: ينتهي البند منقطعًا ومعه الطلب، وتكراره يُهمل',
         case_help_retention),
        ('18. تاريخ البند عند توقف نشاطه (R17-01): الإجابة المؤكدة وطلب التلميح قبل تغيّر الصلاحية يبقيان في سجل البند مرة '
         'واحدة مع سبب الاستبعاد، عبر الحفظ والاستعادة المتكررين. لا يتقدم النشاط بهما ولا يدخلان العدّاد ولا المؤشرات، '
         'والحدث اللاحق للتغيّر لا يُحتسب. وكذلك طلب دعم بلا إجابة، وبند عُرض بلا حدث، والتعليق قبل الاستعادة. '
         'وبعد رفع التعليق (R18-01): البند الذي أُجيب عنه وطُلب فيه تلميح لا يعود دليلًا، ويحل محله بديل نوعه، في المسار '
         'المتصل وبعد الإغلاق والاستعادة. وبلا بديل يُعلن النفاد ولا يُعاد البند. والبند الذي عُرض بلا حدث يُعاد عرضه',
         case_void_history),
        ('19. التعليق أثناء أول بند في دليل الفهم (R19-01): النشاط يُسقط ثم يُنشأ من جديد، وتاريخ التعرّض باقٍ في السجلات. '
         'طلب دعم فقط، أو إجابة مؤكدة: البند لا يعود ويحل محله بديله. العرض وحده: يُعاد عرضه موسومًا. كلٌّ في المسار '
         'المتصل، ومع حفظ واستعادة قبل التوقف وبعده، وبمحتوى بلا بدائل، إلى ما بعد رفع التعليق وإصدار الدليل',
         case_first_item),
        ('20. افتتاح الدرس بعد بند مستهلك (R18-01): بند «جرّب أولًا» المستهلك لا يُعرض ثانية ولا يتخطى الشرح ولا يُعدّ '
         'خطأ. والبند الموجَّه المستهلك يُعاد للتعليم موسومًا بأنه مكرر، ونجاحه لا ينهي الدرس مبكرًا ولا يُسجَّل تعثّر. '
         'في المسار المتصل ومع حفظ واستعادة قبل التوقف وبعده. والمعروض بلا إجابة مقبولة يُعاد موسومًا ويُحتسب',
         case_opening_void)):
    try:
        bad = fn()
    except Exception as x:                                   # noqa: BLE001
        import traceback
        bad = ['استثناء: %r %s' % (x, traceback.format_exc().splitlines()[-3].strip())]
    check(title, bad)
print('النتيجة: نجح %d من %d' % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
