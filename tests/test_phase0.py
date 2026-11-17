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
        assess = a in ('gate', 'short', 'check', 'retention')
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
        return evs, item['answer'], w['activity'] in ('gate', 'short', 'check', 'retention')
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
    e, sc, st, kid = at(13)                                 # البند 1-4-1/evidence/02 وجوابه 4
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
         'الذي يُختم منقطعًا أثناء الاستعادة يدخل العدّاد عندها، فيصير المجموع 21 و41 مع بديله', case_counters)):
    try:
        bad = fn()
    except Exception as x:                                   # noqa: BLE001
        import traceback
        bad = ['استثناء: %r %s' % (x, traceback.format_exc().splitlines()[-3].strip())]
    check(title, bad)
print('النتيجة: نجح %d من %d' % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
