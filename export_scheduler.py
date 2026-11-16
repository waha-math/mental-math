#!/usr/bin/env python3
"""يصدّر متجهات مطابقة المجدول (app/scheduler.mjs) من المجدول المرجعي (scheduler.py).

    python3 export_scheduler.py <ملف الخريطة>
    node app/test_scheduler_conformance.mjs

يسجّل كل مجدول يُنشأ في ثلاثة مصادر:
1. اختبارات طبقة البنود والمجدول (test_item_layer.py) واختبارا المجدول في tests/test_r11.py، كما هي.
2. عينة من تشغيلات المحاكاة فوق المحرك بأطفالها العشوائيين: engine_sim (بوضع المطابقة وبدونه) و policy_sim بتجاربها.
3. مسارات تعلّم عشوائية ببذرة ثابتة على محتوى الشريحة: مهارات الوحدتين، وطفل يجيب ويخطئ ويطلب الدعم وينقطع، وسقف
   وقت، وفحوص احتفاظ، وإبطال جلسات وقرارات للمعلم بين الجلسات، وأيام جلسات أسبق يؤكدها الوالد أحيانًا.
4. تشخيص بسقف وقت: أطفال المحاكاة على ملفاتها، وسقف ومدة بند عشوائيان، ووضع المطابقة أحيانًا.

لكل مجدول: حالة المحرك عند إنشائه، وخيارات المجدول، وشريط بكل نداء لمصدر البنود وللطفل ولمدة البند بمدخلاته وما
أعاده. ثم كل نداء من خارج المجدول، لدوالّه أو للمحرك مباشرة، بمدخلاته وما أعاده، وحالة المجدول بعده وبصمة المحرك.
وإن غيّر الاختبار حالة المجدول أو المحرك بين نداءين بغير هذه الطرق، سُجّلت الحالة قبل النداء التالي.
محرك التطبيق يعيد كل نداء بالشريط نفسه، ويطابق إن أعاد النتيجة نفسها والحالة نفسها والبصمة نفسها.
"""
import contextlib
import functools
import hashlib
import inspect
import io
import json
import os
import random
import runpy
import sys
from collections import Counter

MAP = sys.argv[1]
sys.argv = [sys.argv[0], MAP]
import scheduler as sch  # noqa: E402
import transition_engine as te  # noqa: E402
from content_source import ContentSource, load_items  # noqa: E402

NET = te.load_network(MAP)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'scheduler_vectors.json')
STATE = ('carry', 'parked', 'carried_items', 'intent', 'pending', 'proven', 'attempt', 'ev_round', 'last_items', 'n',
         'gates_run', 'searches', 'sessions', 'day', 'cur', 'log', 'refused', 'stalled', 'elapsed', 'start_at',
         'items_before', 'start_w', 'start_what')
traces, tables = [], dict(types=[], items=[])


def canon(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True)


def plain(x):
    """قيمة قابلة للنقل: المجموعات مرتبة، والعدّادات بلا أصفار، والأعداد الصحيحة بلا كسر."""
    if isinstance(x, Counter):
        return {k: plain(v) for k, v in x.items() if v}
    if isinstance(x, dict):
        return {str(k): plain(v) for k, v in x.items()}
    if isinstance(x, (set, frozenset)):
        return sorted(plain(v) for v in x)
    if isinstance(x, (list, tuple)):
        return [plain(v) for v in x]
    if isinstance(x, float) and x == int(x):
        return int(x)
    if isinstance(x, sch.Activity):
        return x.to_dict()
    return x


def digest(e):
    return hashlib.sha256(canon(dict(s=e.s, d=e.derive())).encode('utf-8')).hexdigest()


def intern(table, value):
    key = canon(value)
    lst = tables[table]
    if not hasattr(intern, 'idx'):
        intern.idx = {}
    k = (table, key)
    if k not in intern.idx:
        intern.idx[k] = len(lst)
        lst.append(value)
    return intern.idx[k]


class Ids:
    """عدّاد معرّفات الأحداث الذي يُقرأ دون أن يتقدم."""
    def __init__(self):
        self.n = 1

    def __iter__(self):
        return self

    def __next__(self):
        v, self.n = self.n, self.n + 1
        return v


def snapshot(sc):
    d = {k: plain(getattr(sc, k)) for k in STATE}
    for k in ('log', 'refused'):                            # تطول مع الجلسات: طولها وبصمتها، وآخرها للتشخيص
        v = d[k]
        d[k] = dict(n=len(v), h=hashlib.sha256(canon(v).encode()).hexdigest(), last=v[-3:])
    d['next_id'] = sc._ids.n
    d['records'] = None if sc.records is None else hashlib.sha256(canon(plain(sc.records)).encode()).hexdigest()
    return d


_init = sch.Scheduler.__init__


def init(self, engine, types, source, answer, **kw):
    _init(self, engine, types, source, answer, **kw)
    if list(engine.ids) != list(NET[0]) or {s: list(p) for s, p in engine.pre.items()} != {
            s: list(p) for s, p in NET[1].items()}:
        return                                              # شبكة غير شبكة الخريطة: لا يُسجَّل
    sig = inspect.signature(_init).bind(self, engine, types, source, answer, **kw)
    sig.apply_defaults()
    opts = {k: v for k, v in sig.arguments.items() if k not in ('self', 'engine', 'types', 'source', 'answer')}
    opts['scope'] = None if opts['scope'] is None else sorted(opts['scope'], key=engine.idx.get)
    opts['no_short'] = list(opts['no_short'])
    opts['records'] = opts['records'] is not None
    timed = opts.pop('item_seconds') is not None
    tr = dict(engine=dict(group=engine.s['group'], regate=engine.s['regate'],
                          versions=None if engine.versions is None else sorted(engine.versions), text=engine.dump()),
              types=intern('types', types), opts=plain(opts), timed=timed, tape=[], ops=[])
    self._ids = Ids()
    self._trace, self._depth = tr, 0
    self._seen = (snapshot(self), digest(engine))
    src, ans, sec = self.source, self.answer, self.item_seconds

    def source(skill, want):
        r = src(skill, want)
        tr['tape'].append(['src', skill, plain(want), None if r is None else intern('items', plain(r))])
        return r

    def answer(item, want):
        r = ans(item, want)
        tr['tape'].append(['ans', intern('items', plain(item)), plain(want), plain(r)])
        return r

    def seconds(want):
        r = sec(want)
        tr['tape'].append(['sec', plain(want), plain(r)])
        return r

    self.source, self.answer = source, answer
    if timed:                                               # بلا مدة مُعطاة: صفر، ولا يُسجَّل
        self.item_seconds = seconds
    engine._sched = self
    traces.append(tr)


def before(sc, op):
    snap, h = snapshot(sc), digest(sc.e)
    if snap != sc._seen[0]:
        op['pre'] = snap                                    # غيّره الاختبار مباشرة
    if h != sc._seen[1]:
        op['pre_engine'] = sc.e.dump()


def after(sc, op):
    op['post'], op['h'] = snapshot(sc), digest(sc.e)
    sc._seen = (op['post'], op['h'])
    sc._trace['ops'].append(op)


def wrap(name, fn):
    @functools.wraps(fn)
    def method(self, *args, **kw):
        if not hasattr(self, '_trace') or self._depth:
            if hasattr(self, '_depth'):
                self._depth += 1
                try:
                    return fn(self, *args, **kw)
                finally:
                    self._depth -= 1
            return fn(self, *args, **kw)
        if any(k in vars(sch.Scheduler) for k in vars(self) if callable(vars(self)[k]) and k not in (
                'source', 'answer', 'item_seconds')):
            self._trace['hooked'] = True                    # الاختبار بدّل دالة في هذا المجدول: لا يُعاد في التطبيق
        b = inspect.signature(fn).bind(self, *args, **kw)
        b.apply_defaults()
        op = dict(op=name, args=plain(list(b.arguments.values())[1:]))
        before(self, op)
        self._depth = 1
        try:
            r = fn(self, *args, **kw)
            op['ret'] = plain(r)
            return r
        except sch.Capped:
            op['raise'] = 'Capped'
            raise
        finally:
            self._depth = 0
            after(self, op)
    return method


for name, fn in list(vars(sch.Scheduler).items()):
    if callable(fn) and not name.startswith('__'):
        setattr(sch.Scheduler, name, wrap(name, fn))
sch.Scheduler.__init__ = init

_apply = te.Engine.apply


def apply(self, ev):
    sc = getattr(self, '_sched', None)
    if sc is None or not hasattr(sc, '_trace') or sc._depth:
        return _apply(self, ev)
    op = dict(op='engine_apply', args=[plain(ev)])         # من خارج المجدول: قرار معلم، إبطال، تأكيد تاريخ
    before(sc, op)
    r = _apply(self, ev)
    op['ret'] = plain(r)
    after(sc, op)
    return r


te.Engine.apply = apply

# ---------------------------------------------------------------- 1. الاختبارات
counts = {}
for script in ('test_item_layer.py', 'tests/test_r11.py'):
    n0 = len(traces)
    sys.argv = [script, MAP]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            runpy.run_path(script, run_name='__main__')
        except SystemExit as x:
            assert x.code == 0, out.getvalue()[-600:]
    last = out.getvalue().rstrip().split('\n')[-1]
    assert last.startswith('نجحت الاختبارات كلها') or last == 'النتيجة: نجح 10 من 10', out.getvalue()[-300:]
    counts[script] = len(traces) - n0

# ---------------------------------------------------------------- 2. المحاكاة
sys.argv = ['engine_sim.py', MAP]
import engine_sim  # noqa: E402
import policy_sim  # noqa: E402
import placement_sim as old  # noqa: E402

n0 = len(traces)
for k, (name, know, start, group) in enumerate(old.PROFILES):
    for seed in range(6):
        engine_sim.run_new(know, start, group, 1000 * k + seed, compat=bool(seed % 2))
for ei, (label, opts) in enumerate(policy_sim.EXPERIMENTS):
    opts = {x: v for x, v in opts.items() if x not in ('runs', 'only')}
    for k, (name, know, start, group) in enumerate(old.PROFILES):
        policy_sim.one(know, start, group, 7000 + 100 * ei + k, **opts)
        policy_sim.one(know, start, group, 9000 + 100 * ei + k, try_from_gate=False, **opts)
counts['المحاكاة'] = len(traces) - n0

# ---------------------------------------------------------------- 3. مسارات تعلّم عشوائية بمحتوى الشريحة
ITEMS = load_items()
TYPES = engine_sim.TYPES
UNITS = [(['1-4-1', '1-4-2'], 'young', None, [('1-4-1', ['1-3-3'])]),
         (['3-5-1', '3-5-2', '3-5-3'], 'older', '3-5-1',
          [('3-5-1', ['3-3-2', '3-2-3']), ('3-5-2', ['3-2-1', '3-3-1', '2-5-2'])])]


class RandomChild:
    """يجيب صحيحًا غالبًا، ويخطئ، ويطلب الدعم، وينقطع، بنسب ثابتة من بذرته."""
    def __init__(self, rng, p_wrong, p_help, p_cut):
        self.rng, self.p_wrong, self.p_help, self.p_cut = rng, p_wrong, p_help, p_cut

    def __call__(self, item, want):
        a = want['activity']
        if a in ('lesson', 'practice'):
            return 'correct'
        assess = a in ('gate', 'short', 'check', 'retention')
        ans, x = item['answer'], self.rng.random()
        wrong = ans + 1 if ans < 99 else ans - 1
        tail = [] if assess else [('end',)]
        if x < self.p_cut:
            return [('interrupt',)], ans, assess
        if x < self.p_cut + self.p_help:
            raw = [('support', self.rng.choice(['hint', 'extra_model', 'someone', 'requested']))]
            return raw + ([('confirm', ans)] + tail if self.rng.random() < 0.7 else [('interrupt',)]), ans, assess
        if x < self.p_cut + self.p_help + self.p_wrong:
            if not assess and self.rng.random() < 0.5:
                return [('confirm', wrong), ('confirm', ans), ('end',)], ans, assess
            return [('confirm', wrong)] + tail, ans, assess
        return [('confirm', ans)] + tail, ans, assess


class Teacher:
    """بين الجلسات: يبطل جلسة منتهية أحيانًا، ويترك محاولة فحص تنتظره، ويؤكد التاريخ المعلَّم."""
    def __init__(self, rng, sc, p):
        self.rng, self.sc, self.p, self.n = rng, sc, p, 0

    def act(self):
        e, rng = self.sc.e, self.rng
        self.n += 1
        if rng.random() < self.p:
            ended = [x for x in e.s['order'] if e.s['sessions'][x]['ended'] and not e.s['sessions'][x]['invalid']]
            if ended:
                e.apply(dict(id='t%d' % self.n, type='invalidate_session', target=rng.choice(ended)))
        for cid, c in list(e.s['checks'].items()):
            if c['state'] in ('held', 'needs_restart'):
                e.apply(dict(id='a%d-%s' % (self.n, cid), type='check_abandoned', check_id=cid, reason='قرار المعلم'))


n0 = len(traces)
for seed in range(240):
    rng = random.Random(seed)
    scope, group, start, decisions = UNITS[seed % 2]
    e = te.Engine(NET, group=group)
    for k, (skill, bypass) in enumerate(decisions):
        e.apply(dict(id='d%d' % k, type='teacher_open', skill=skill, bypass=bypass, reason='قرار الشريحة'))
    cap = rng.choice([None, None, 120, 180, 240, 300, 420])
    secs = rng.choice([30, 45, 60])
    child = RandomChild(rng, rng.choice([0.05, 0.15, 0.3]), rng.choice([0.0, 0.05, 0.1]), rng.choice([0.0, 0.03, 0.08]))
    sc = sch.Scheduler(e, TYPES, ContentSource(ITEMS, allow_same_fact=rng.random() < 0.8), child, group=group,
                       start=start, scope=set(scope), learning=True, records=[], cap=cap,
                       item_seconds=(lambda w, s=secs: s) if cap else None, retention=rng.random() < 0.5,
                       try_from_gate=rng.random() < 0.8, tolerant=rng.random() < 0.8)
    teacher = Teacher(rng, sc, rng.choice([0.0, 0.05, 0.15]))
    sc.search()
    sc.start_session()
    for _ in range(rng.randint(8, 70)):
        if sc.satisfied() and sc.carry is None and not sc.parked:
            break
        teacher.act()
        if rng.random() < 0.06:                             # يوم جلسة أسبق: تنبيه، ثم تأكيد الوالد أحيانًا
            sc.day = max(0, sc.day - rng.randint(1, 3)) - 1
        sc.follow_learning()
        last = sc.e.s['order'][-1]
        if sc.e.s['sessions'][last]['clock'] and rng.random() < 0.6:
            sc.e.apply(dict(id='c%s' % last, type='date_confirmed', target=last))
counts['مسارات تعلّم عشوائية'] = len(traces) - n0

# ---------------------------------------------------------------- 4. التشخيص بسقف وقت
n0 = len(traces)
for seed in range(160):
    rng = random.Random(50000 + seed)
    name, know, start, group = old.PROFILES[seed % len(old.PROFILES)]
    random.seed(seed)
    child = old.Child(know)
    answer = lambda item, want, c=child: {True: 'correct', False: 'wrong', None: 'help'}[c.item(item['skill'],
                                                                                                want['type'])]
    e = te.Engine(NET, group=group, regate=rng.random() < 0.7)
    secs = rng.choice([20, 30, 45, 60])
    sc = sch.Scheduler(e, TYPES, engine_sim.abstract_source, answer, group=group, start=start,
                       tolerant=rng.random() < 0.8, cap=rng.choice([60, 120, 240, 360]), item_seconds=lambda w, s=secs: s,
                       compat=rng.random() < 0.2)
    sc.run()
counts['تشخيص بسقف وقت'] = len(traces) - n0

hooked = sum(1 for t in traces if t.get('hooked'))
traces = [t for t in traces if t['ops'] and not t.get('hooked')]
ops = Counter(o['op'] for t in traces for o in t['ops'])
tape = Counter(x[0] for t in traces for x in t['tape'])
counts['مستبعد'] = hooked
data = dict(network=[list(NET[0]), {s: list(p) for s, p in NET[1].items()}], tables=tables, traces=traces,
            sources=counts)
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
print('مجدولات مسجّلة: %d (%s). واستُبعد %d بدّل فيه الاختبار دالة من دوال المجدول' % (
    len(traces), '، '.join('%s %d' % kv for kv in counts.items()), hooked))
print('نداءات من الخارج: %d في %d دالة: %s' % (sum(ops.values()), len(ops), '، '.join(
    '%s %d' % kv for kv in sorted(ops.items(), key=lambda kv: -kv[1]))))
print('الشريط: %d نداء لمصدر البنود، %d للطفل، %d لمدة البند. بنود مختلفة: %d' % (
    tape['src'], tape['ans'], tape['sec'], len(tables['items'])))
print('الحجم: %.1f ميغابايت' % (os.path.getsize(OUT) / 1e6))
