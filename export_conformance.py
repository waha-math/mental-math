#!/usr/bin/env python3
"""يصدّر لمحرك التطبيق (app/engine.mjs) بياناته ومتجهات مطابقته من المحرك المرجعي واختباراته.

    python3 export_conformance.py <ملف الخريطة>
    node app/test_conformance.mjs

يكتب ملفين:
- app/engine_data.mjs: الشبكة، والمخطط، والحصص، ورموز الرفض ونصوصها، وثوابت الاحتفاظ. محرك التطبيق يقرؤها ولا
  يكرر كتابتها، فلا تنحرف نسخة عن الأخرى.
- app/conformance_vectors.json: كل ما مرّ على المحرك المرجعي حين شُغّلت اختباراته (test_transition_engine.py
  و test_item_layer.py و tests/test_r10.py و tests/test_r11.py): كل حدث أُرسل أو سُئل عنه، وحكم المحرك عليه، وبصمة الحالة بعده.

البصمة: SHA-256 للنص القياسي (مفاتيح مرتبة) للحالة المحفوظة كلها مع الحالات المشتقة. محرك التطبيق يطابق إن أعاد
الحكم نفسه والبصمة نفسها بعد كل حدث.

ما لا يُنقل: حدث فيه عدد كسري (في JSON لا يتميز 1.0 من 1)، وحدث ليس نصًّا قابلًا للحفظ، ونتيجة internal_error
التي تصنعها الاختبارات بتعطيل دالة عمدًا. وحين يعدّل اختبار الحالة مباشرة، تُسجَّل الحالة الجديدة نصًّا فيقرؤها محرك
التطبيق ويكمل منها.
"""
import copy
import hashlib
import io
import json
import os
import runpy
import sys
import contextlib

import transition_engine as te
from transition_engine import Engine

MAP = sys.argv[1]
traces, nets = [], []


def canon(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True)


def digest(e):
    return hashlib.sha256(canon(dict(s=e.s, d=e.derive())).encode('utf-8')).hexdigest()


def net_id(net):
    for k, n in enumerate(nets):
        if n == [list(net[0]), {s: list(p) for s, p in net[1].items()}]:
            return k
    nets.append([list(net[0]), {s: list(p) for s, p in net[1].items()}])
    return len(nets) - 1


def has_float(x):
    if isinstance(x, float):
        return True
    if isinstance(x, dict):
        return any(has_float(v) for v in x.values())
    if isinstance(x, (list, tuple)):
        return any(has_float(v) for v in x)
    return False


def portable(ev):
    try:
        return json.loads(json.dumps(ev, ensure_ascii=False)) == ev and not has_float(ev)
    except (TypeError, ValueError):
        return False


def versions(e):
    return None if e.versions is None else sorted(e.versions)


_init, _apply, _preflight, _restore = Engine.__init__, Engine.apply, Engine.preflight, Engine.restore.__func__


def init(self, net, group='older', regate=True, versions=None):
    _init(self, net, group, regate, versions)
    self._trace = dict(net=net_id(net), group=group, regate=regate, ops=[])
    self._last = digest(self)
    traces.append(self._trace)


def sync(e):
    """إن تغيّرت الحالة خارج apply (اختبار عدّلها مباشرة)، تُسجَّل نصًّا ليقرأها محرك التطبيق."""
    h = digest(e)
    if h != e._last:
        e._trace['ops'].append(dict(op='state', text=e.dump(), h=h))
        e._last = h


def apply(self, ev):
    sync(self)
    sent = copy.deepcopy(ev)
    res = _apply(self, ev)
    h = digest(self)
    if portable(sent) and res.get('code') != 'internal_error':
        self._trace['ops'].append(dict(op='apply', ev=sent, res=copy.deepcopy(res), h=h, versions=versions(self)))
        self._last = h
    else:
        self._last = None                                   # يُسجَّل ما بعده حالةً كاملة
    return res


def preflight(self, ev):
    sync(self)
    sent = copy.deepcopy(ev)
    res = _preflight(self, ev)
    if portable(sent) and res.get('code') != 'internal_error':
        self._trace['ops'].append(dict(op='preflight', ev=sent, res=copy.deepcopy(res), h=self._last,
                                       versions=versions(self)))
    return res


def restore(cls, net, text, content_versions=None):
    e = _restore(cls, net, text, content_versions)
    e._trace['ops'].append(dict(op='restore', text=text, h=digest(e), versions=versions(e)))
    e._last = digest(e)
    return e


Engine.__init__, Engine.apply, Engine.preflight, Engine.restore = init, apply, preflight, classmethod(restore)

# ---------------------------------------------------------------- طبقة البنود
# يُسجَّل لكل نشاط ما طُلب منه وما أعاد وبصمة حالته بعد كل خطوة، ولكل نداء على fold_item و indicators ومصدر البنود
# و drive مدخله ومخرجه. تُسجَّل قبل أن يستورد أي ملف طبقة البنود، ليأخذ الدوال المسجِّلة.
import inspect  # noqa: E402
import item_layer as il  # noqa: E402
import content_source as cs  # noqa: E402

acts, folds, inds, picks, drives = [], {}, [], {}, []


def jsonable(x):
    try:
        return json.loads(json.dumps(x, ensure_ascii=False))
    except (TypeError, ValueError):
        return None


def state_of(a):
    return hashlib.sha256(canon(a.to_dict()).encode('utf-8')).hexdigest()


def act_sync(a):
    h = state_of(a)
    if h != a._last:                                        # الحالة عُدّلت من خارج النشاط (خيارات المقارنة بالقديمة)
        a._trace['ops'].append(dict(op='state', state=a.to_dict()))
        a._last = h


def act_op(a, op, call, **more):
    act_sync(a)
    rec = dict(op=op, **more)
    try:
        out = call()
        rec['out'] = jsonable(out)
    except RuntimeError:
        rec['error'] = True
        a._trace['ops'].append(rec)
        raise
    finally:
        a._last = state_of(a)
        rec['h'] = a._last
    a._trace['ops'].append(rec)
    return out


def patch_activity(cls):
    c_init = cls.__init__
    sig = inspect.signature(c_init)

    def __init__(self, *args, **kw):
        c_init(self, *args, **kw)
        b = sig.bind(self, *args, **kw)
        b.apply_defaults()
        opts = {k: v for k, v in b.arguments.items() if k != 'self'}
        self._attach(dict(cls=cls.__name__, opts=jsonable(opts), ops=[]))
    cls.__init__ = __init__
    for name in ('want', 'feed', 'unavailable', 'events', 'start_event'):
        if name not in cls.__dict__:
            continue
        orig = cls.__dict__[name]

        def wrapper(self, *args, _orig=orig, _name=name):
            return act_op(self, _name, lambda: _orig(self, *args), **(dict(arg=args[0]) if args else {}))
        setattr(cls, name, wrapper)


def attach(self, trace):
    HIDDEN[id(self)] = [trace, state_of(self), self]        # المرجع الأخير يُبقي الكائن، فلا يتكرر معرّفه
    acts.append(trace)


HIDDEN = {}


class Hidden:
    """سجل النشاط خارج __dict__، فلا يدخل حالته المحفوظة."""
    def __init__(self, k):
        self.k = k

    def __get__(self, obj, owner):
        return HIDDEN[id(obj)][self.k]

    def __set__(self, obj, value):
        HIDDEN[id(obj)][self.k] = value


il.Activity._trace, il.Activity._last, il.Activity._attach = Hidden(0), Hidden(1), attach
_to_dict, _from_dict = il.Activity.to_dict, il.Activity.from_dict


def from_dict(d):
    obj = _from_dict(d)
    obj._attach(dict(cls=type(obj).__name__, restore=jsonable(d), ops=[]))
    return obj


il.Activity.from_dict = staticmethod(from_dict)
for c in list(il.CLASSES.values()):
    patch_activity(c)
_unavailable = il.Activity.unavailable
il.Activity.unavailable = lambda self: act_op(self, 'unavailable', lambda: _unavailable(self))

_fold, _indicators, _drive, _pick = il.fold_item, il.indicators, il.drive, cs.ContentSource.__call__


def fold_item(raw, answer, assess):
    key = canon([jsonable([list(e) for e in raw]), jsonable(answer), assess])
    try:
        out = _fold(raw, answer, assess)
        folds[key] = dict(out=copy.deepcopy(out), cls=il.classify(out), ind=il.correct_independent(out))
        return out
    except ValueError:
        folds[key] = dict(error=True)
        raise


def indicators(records):
    out = _indicators(records)
    inds.append(dict(records=jsonable(records), out=jsonable(out)))
    return out


def pick(self, skill, w):
    key = canon([self.allow_same_fact, skill, jsonable(w)])
    try:
        it = _pick(self, skill, w)
        picks[key] = dict(id=it['id'] if it else None, same=bool(it and it.get('reshown_same_fact')))
        return it
    except AssertionError:
        picks[key] = dict(error=True)
        raise


def drive(act, source, answer, records=None, pause=None):
    rec = dict(start=act.to_dict(), steps=[], pauses=[])
    step = {}

    def src(skill, w):
        item = source(skill, w)
        step.clear()
        step.update(w=jsonable(w), item=jsonable(item))
        if item is None:
            rec['steps'].append(dict(step))
        return item

    def ans(item, w):
        got = answer(item, w)
        step['got'] = got if isinstance(got, str) else jsonable([[list(e) for e in got[0]], got[1], got[2]])
        rec['steps'].append(dict(step))
        return got

    def stop(w):
        r = bool(pause(w))
        rec['pauses'].append(r)
        return r
    mine = []
    out = _drive(act, src, ans, mine, stop if pause else None)
    if records is not None:
        records.extend(mine)
    rec.update(end=act.to_dict(), records=jsonable(mine), paused=bool(pause),
               events=jsonable(act.events()) if act.done else None)
    if all(s['item'] is not None or 'got' not in s for s in rec['steps']) and jsonable(rec) is not None:
        drives.append(rec)
    return out


il.fold_item, il.indicators, il.drive, cs.ContentSource.__call__ = fold_item, indicators, drive, pick

for script in ('test_transition_engine.py', 'test_item_layer.py', 'tests/test_r10.py', 'tests/test_r11.py'):
    sys.argv = [script, MAP]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            runpy.run_path(script, run_name='__main__')
        except SystemExit as x:                             # tests/test_r10.py و test_r11.py ينتهيان برمز خروجهما
            assert x.code == 0, out.getvalue()[-600:]
    last = out.getvalue().rstrip().split('\n')[-1]
    assert last.startswith('نجحت الاختبارات كلها') or last in ('النتيجة: نجح 20 من 20', 'النتيجة: نجح 10 من 10'), \
        out.getvalue()[-300:]

traces = [t for t in traces if t['ops']]

# اختبارات المرجع لا تمر بكل حالة في الأنشطة، فتُضاف مسارات عشوائية ببذرة ثابتة: نتائج بنود عشوائية، وبنود غير
# موجودة، وحفظ واستئناف في المنتصف. المرجع هو الحَكَم فيها: ما يفعله يُسجَّل، ومحرك التطبيق يطابقه.
import random  # noqa: E402

rng = random.Random(20261113)
TYPE_SETS = (['ف3'], ['ف1'], ['ف1', 'ف2', 'ف3'], ['ف2', 'ف4'], ['ف1', 'ف2'], ['ف4', 'ف1', 'ف3'])
OUTCOMES = ['correct'] * 12 + ['wrong'] * 4 + ['interrupted'] * 3 + ['supported', 'help']


def fresh():
    t = list(rng.choice(TYPE_SETS))
    k = rng.randrange(6)
    if k == 0:
        return il.GateRun('s', t, tolerant=rng.random() < .7, attempt=rng.choice([1, 2]),
                          event=rng.choice(['gate_result', 'gate_result', 'recheck_result']))
    if k == 1:
        return il.ShortCheckRun('s', t, stop_early=rng.random() < .7)
    if k == 2:
        tt = [rng.choice(t), rng.choice(t)] if rng.random() < .5 else None
        return il.OpeningRun('s', t, try_types=tt, try_errors_count=rng.random() < .2, typed=rng.random() < .7)
    if k == 3:
        return il.EvidenceRun('s', t, proven=[x for x in t if rng.random() < .25], round=rng.choice([1, 2]))
    if k == 4:
        return il.CheckRun('s', 'k%d' % rng.randrange(99), 1, attempt=rng.choice('ABC'))
    return il.RetentionRun('s', rng.choice([1, 2, 3]))


for _ in range(3000):
    a = fresh()
    easy = rng.random() < .5                                # نصفها بأغلبية صحيحة، ليبلغ النشاط آخره
    while a.want() is not None:
        r = rng.random()
        if r < .04:
            try:
                a.unavailable()
            except RuntimeError:
                pass
        elif r < .10:
            a = il.Activity.from_dict(a.to_dict())
        else:
            a.feed('correct' if easy and rng.random() < .8 else rng.choice(OUTCOMES))
    a.events()
    if isinstance(a, il.CheckRun):
        a.start_event()

ALPHABET = [('confirm', 5), ('confirm', 5), ('confirm', 3), ('support', 'hint'), ('support', 'requested'),
            ('support', 'someone'), ('support', 'extra_model'), ('interrupt',), ('end',), ('support', 'x'), ('other',)]
pool = []
for _ in range(4000):
    raw = [rng.choice(ALPHABET) for _ in range(rng.randrange(0, 6))]
    try:
        pool.append(il.fold_item(raw, 5, rng.random() < .5))
    except ValueError:
        pass
for _ in range(300):
    il.indicators([rng.choice(pool) for _ in range(rng.randrange(0, 12))])
os.makedirs('app', exist_ok=True)


def rule(r):
    if r is str:
        return 'str'
    if r is bool:
        return 'bool'
    if r is int:
        return 'int'
    return ['enum'] + list(r) if isinstance(r, tuple) else 'strlist'


ids, pre = te.load_network(MAP)
data = dict(
    network=dict(ids=ids, pre=pre),
    schema={name: {f: rule(r) for f, r in spec.items()} for name, spec in te.SCHEMA.items()},
    reasons=te.REASONS, quota=te.QUOTA, search_cap=te.SEARCH_CAP,
    retention=dict(gaps=list(te.RETENTION_GAPS), items=te.RETENTION_ITEMS, ok=te.RETENTION_OK),
    events=[t[0] for t in te.TABLE])
open('app/engine_data.mjs', 'w', encoding='utf-8').write(
    '// مولَّد من transition_engine.py بالأمر: python3 export_conformance.py <الخريطة>. لا يُعدَّل باليد.\n'
    'export const DATA = %s;\n' % json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True))
json.dump(dict(nets=nets, traces=traces), open('app/conformance_vectors.json', 'w', encoding='utf-8'),
          ensure_ascii=False, separators=(',', ':'))
acts = [a for a in acts if a['ops']]
json.dump(dict(folds=[dict(json.loads(k) and dict(inp=json.loads(k)), **v) for k, v in folds.items()],
               indicators=inds, picks=[dict(inp=json.loads(k), **v) for k, v in picks.items()],
               activities=acts, drives=drives),
          open('app/item_vectors.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
n = {}
for t in traces:
    for o in t['ops']:
        n[o['op']] = n.get(o['op'], 0) + 1
kinds = {}
for t in traces:
    for o in t['ops']:
        if o['op'] == 'apply' and isinstance(o['ev'], dict):
            k = (o['ev'].get('type') if isinstance(o['ev'].get('type'), str) else '?', o['res']['ok'])
            kinds[k] = kinds.get(k, 0) + 1
print('متجهات المطابقة: %d محركًا، %d حدثًا مرسلًا، %d سؤالًا قبل العرض، %d استعادة من نص، %d حالة عُدّلت مباشرة'
      % (len(traces), n.get('apply', 0), n.get('preflight', 0), n.get('restore', 0), n.get('state', 0)))
print('أنواع الأحداث المغطاة: %d من %d، مقبولة ومرفوضة: %s'
      % (len({k[0] for k in kinds if k[0] in te.SCHEMA}), len(te.SCHEMA),
         'كلها' if all((t, True) in kinds and (t, False) in kinds for t in te.SCHEMA) else
         'ينقص ' + '، '.join(sorted(t for t in te.SCHEMA if (t, True) not in kinds or (t, False) not in kinds))))
print('الحجم: %.1f ميغابايت' % (os.path.getsize('app/conformance_vectors.json') / 1e6))
by = {}
for a in acts:
    by[a['cls']] = by.get(a['cls'], 0) + 1
print('متجهات طبقة البنود: %d بندًا خامًا، %d حساب مؤشرات، %d طلب بند من المحتوى، %d نشاطًا (%s)، %d تشغيلًا كاملًا'
      % (len(folds), len(inds), len(picks), len(acts), '، '.join('%s %d' % kv for kv in sorted(by.items())), len(drives)))
print('الحجم: %.1f ميغابايت' % (os.path.getsize('app/item_vectors.json') / 1e6))
