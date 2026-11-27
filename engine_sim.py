#!/usr/bin/env python3
"""محاكاة التشخيص فوق المحرك والمجدول وطبقة البنود، ومقارنتها بالمحاكاة القديمة.

    python3 engine_sim.py <ملف الخريطة> [عدد التشغيلات]

1. المطابقة: لكل حالة من الحالات الثماني، تشغيلات بالبذرة نفسها في المحاكاة القديمة (placement_sim.py) وفي
   المجدول بوضع compat، الذي يعيد خيارات المحاكاة القديمة. يُقارن كل تشغيل بنظيره: حالة كل مهارة، والبنود
   بفئاتها، وعدد الجلسات، وجلسة البدء وما جرى فيها، والدروس الكاملة. أي فرق يُطبع.
2. المواصفة: المجدول بقواعد طبقة البنود والمحتوى، مقابل القديمة بالبذور نفسها، بمقاييس المحاكاة القديمة.

الطفل وحالاته الثماني من placement_sim.py نفسه، فلا يختلف النموذج بين الطرفين. وفي كل تشغيل للمجدول
تُقارن حالات المحرك بمرجع مستقل يقرأ سجل الأحداث وحده، ويُعدّ كل ما رفضه المحرك من اقتراحات المجدول.
"""
import random
import re
import sys
from collections import Counter

import placement_sim as old                                 # يقرأ ملف الخريطة من sys.argv[1]
from transition_engine import Engine, load_network
from scheduler import Scheduler, DIAG

_gate = old.Placement.gate


def _counted_gate(self, s, *a, **k):
    """وجده النقل إلى المحرك: المحاكاة القديمة تعطي بوابة ثانية لمهارة انتهت بوابتها بطلب دعم ثم أخطأ تحققها
    القصير، بلا فتح درسها، والإعادة في 6.1 بعد فتح الدرس. يُعدّ ذلك هنا ولا يتغير سلوكها."""
    if self.gate_n[s] >= 1 and s not in self.opened:
        self.second_no_lesson = getattr(self, 'second_no_lesson', 0) + 1
    return _gate(self, s, *a, **k)


old.Placement.gate = _counted_gate

NET = load_network(sys.argv[1])
IDS, PRE = NET
TYPES = {}
for sid, _t, _m, _r, ev, _a in old.ROW.findall(old.SRC):
    if sid in PRE and sid not in TYPES:
        TYPES[sid] = re.findall(r'ف\d', ev)
KIDS = {s: [c for c in IDS if s in PRE[c]] for s in IDS}
RUNS = int(sys.argv[2]) if len(sys.argv) > 2 else 400


def oracle_mismatch(e):
    """المرجع المستقل نفسه في اختبار المحرك 15: الأدلة من الأحداث المقبولة، والانتظار بانتشار أمامي."""
    proofs, dead = [], set()
    for x in e.s['log']:
        t = x['type']
        if t == 'gate_result' and x['result'] in ('pass', 'fail'):
            proofs.append((x['skill'], x['result'], x['session']))
        elif t == 'lesson_opening_result' and x['outcome'] == 'full_error':
            proofs.append((x['skill'], 'fail', x['session']))
        elif t == 'understanding_proved':
            proofs.append((x['skill'], 'und', x['session']))
        elif t == 'independence_result' and x['result'] == 'pass':
            proofs.append((x['skill'], 'ind', x['session']))
        elif t == 'recheck_result' and x['ok']:
            proofs.append((x['skill'], 'pass', x['session']))
        elif t == 'invalidate_session':
            dead.add(x['target'])
    state = {}
    for skill in IDS:
        st, und, ind = None, False, False
        for s, what, ses in proofs:
            if s != skill or ses in dead:
                continue
            if what == 'pass':
                st = 'exempt'
            elif what == 'fail':
                st, und, ind = 'stumbled', False, False
            elif what == 'und':
                und = True
            else:
                ind = True
            if und and ind:
                st = 'met'
        if st:
            state[skill] = st
    waiting, front = set(), [s for s in state if state[s] == 'stumbled']
    while front:
        x = front.pop()
        for c in KIDS[x]:
            if c not in state and c not in waiting:
                waiting.add(c)
                front.append(c)
    st, bad = e.derive(), 0
    for s in IDS:
        if (st[s] == 'waiting') != (s in waiting):
            bad += 1
        elif state.get(s) != (st[s] if st[s] in ('exempt', 'stumbled', 'met') else None):
            bad += 1
    return bad


def abstract_source(skill, want):
    if want['activity'] in ('lesson', 'practice'):
        return None                                         # الطفل في المحاكاة لا يتعلّم
    return dict(want, skill=skill)


def run_new(know, start, group, seed, compat, tolerant=True, regate=True, **kw):
    random.seed(seed)
    child = old.Child(know, **kw)
    # بوابة الجاهزية لمتطلب خارجي (قراءة الساعة): الطفل المحاكى يعرفه. المحاكاة تقيس المنهج، والمتطلب الخارجي خارجه
    answer = lambda item, want: 'correct' if want['activity'] == 'ready' else \
        {True: 'correct', False: 'wrong', None: 'help'}[child.item(item['skill'], want['type'])]
    e = Engine(NET, group=group, regate=regate)
    sc = Scheduler(e, TYPES, abstract_source, answer, group=group, start=start, compat=compat, tolerant=tolerant)
    sc.run()
    return sc


def run_old(know, start, group, seed, tolerant=True, regate=True, **kw):
    random.seed(seed)
    pl = old.Placement(old.Child(know, **kw), group, tolerant, regate)
    pl.run(start)
    return pl


def sig_old(pl):
    st = pl.st()
    return dict(states=tuple(st[s] for s in IDS), n=dict(+pl.n), sessions=pl.sessions, start_at=pl.start_at,
                items_before=pl.items_before, lessons=tuple(sorted(pl.lesson)))


def sig_new(sc):
    st = sc.e.derive()
    lessons = tuple(sorted(s for s, o in sc.e.s['opened'].items() if o['phase'] in ('full', 'due')))
    return dict(states=tuple(st[s] for s in IDS), n=dict(+sc.n), sessions=sc.sessions, start_at=sc.start_at,
                items_before=sc.items_before, lessons=lessons)


def record(kind, obj, know):
    """مقاييس التشغيل الواحد، بتعريفات المحاكاة القديمة."""
    if kind == 'old':
        st, n, log, sessions = obj.st(), obj.n, obj.log, obj.sessions
        lessons = set(obj.lesson)
        w, what = obj.log_start if hasattr(obj, 'log_start') else (None, None)
        bad = obj.viol + obj.mismatch()
        start_at, before = obj.start_at, obj.items_before
    else:
        e = obj.e
        st, n, log, sessions = e.derive(), obj.n, obj.log, obj.sessions
        lessons = {s for s, o in e.s['opened'].items() if o['phase'] in ('full', 'due')}
        bad = len(obj.refused) + oracle_mismatch(e) + obj.stalled
        start_at, before = obj.start_at, obj.items_before
    first = [x[0] for x in log if x[1] == 'lesson' and know.get(x[2]) != 'full']
    return dict(start_at=start_at, before=before, sessions=sessions, diag=sum(n[c] for c in DIAG),
                first=first[0] if first else None,
                unneeded=sum(1 for s in lessons if know.get(s) == 'full'),
                known_stum=sum(1 for s in IDS if know.get(s) == 'full' and st[s] == 'stumbled'),
                known_wait=sum(1 for s in IDS if know.get(s) == 'full' and st[s] == 'waiting'),
                unk_exempt=sum(1 for s in IDS if s not in know and st[s] == 'exempt'),
                bad=bad)


def q(v, f):
    v = sorted(v)
    return v[min(len(v) - 1, int(f * len(v)))] if v else '-'


def summary(rs):
    n = float(len(rs))
    fs = [r['first'] for r in rs if r['first'] is not None]
    return ('%d/%d | %d/%d | %s/%s | %d/%d | %d/%d | %.2f %4.1f%% | %.2f | %.2f | %.3f | %d' % (
        q([r['start_at'] for r in rs], .5), max(r['start_at'] for r in rs), q([r['before'] for r in rs], .5),
        q([r['before'] for r in rs], .95), q(fs, .5), q(fs, .95), q([r['sessions'] for r in rs], .5),
        q([r['sessions'] for r in rs], .95), q([r['diag'] for r in rs], .5), q([r['diag'] for r in rs], .95),
        sum(r['unneeded'] for r in rs) / n, 100 * sum(1 for r in rs if r['unneeded']) / n,
        sum(r['known_stum'] for r in rs) / n, sum(r['known_wait'] for r in rs) / n,
        sum(r['unk_exempt'] for r in rs) / n, sum(r['bad'] for r in rs)))


HEAD = ('جلسة البدء وسيط/أقصى | بنود قبلها وسيط/م95 | أول درس كامل لازم وسيط/م95 | جلسات حتى الاكتمال وسيط/م95 | '
        'بنود تشخيصية وسيط/م95 | دروس زائدة متوسط ونسبة | يعرفها ومتعثّر فيها | يعرفها وتنتظر | لا يعرفها وأُعفي | '
        'مخالفات')

CONFIGS = [
    ('الأساس', {}),
    ('دقة 90% في ما يعرفه', dict(ak=0.90)),
    ('طلب دعم 2% و20%', dict(help_k=0.02, help_u=0.20)),
]

if __name__ == '__main__':
    print('=== 1. المطابقة: المحاكاة القديمة والمجدول بوضع compat، تشغيلًا بتشغيل وبالبذرة نفسها')
    total = same = 0
    diffs = Counter()
    for label, kw in CONFIGS:
        why = Counter()
        for name, know, start, group in old.PROFILES:
            for r in range(RUNS):
                seed = 1000003 * (1 + old.PROFILES.index((name, know, start, group))) + r
                pl = run_old(know, start, group, seed, **kw)
                a = sig_old(pl)
                b = sig_new(run_new(know, start, group, seed, True, **kw))
                total += 1
                why[(getattr(pl, 'second_no_lesson', 0) > 0, a == b)] += 1
                if a == b:
                    same += 1
                else:
                    for k in a:
                        if a[k] != b[k]:
                            diffs[(label, name[:1], k)] += 1
        print('  %s: تطابق %d من %d تشغيلًا حتى الآن' % (label, same, total), flush=True)
        n = why[(True, True)] + why[(True, False)]
        print('    في %d تشغيلًا من هذا الإعداد أعطت القديمة بوابة ثانية بلا فتح الدرس، والمحرك يرفضها: اختلفت '
              'نتيجته في %d منها. وتشغيلات مختلفة بلا هذا السبب: %d' % (n, why[(True, False)], why[(False, False)]),
              flush=True)
    for (label, prof, k), v in sorted(diffs.items()):
        print('  فرق: %s، الحالة %s، الحقل %s، في %d تشغيلًا' % (label, prof, k, v))

    print('\n=== 2. المواصفة: المجدول بقواعد طبقة البنود، مقابل القديمة بالبذور نفسها (%d تشغيلًا)' % RUNS)
    print('    ' + HEAD)
    for label, kw in CONFIGS:
        print('\n  ' + label)
        for name, know, start, group in old.PROFILES:
            ro, rn = [], []
            for r in range(RUNS):
                seed = 2000003 * (1 + old.PROFILES.index((name, know, start, group))) + r
                ro.append(record('old', run_old(know, start, group, seed, **kw), know))
                rn.append(record('new', run_new(know, start, group, seed, False, **kw), know))
            print('    %s  قديمة   %s' % (name[:1], summary(ro)))
            print('    %s  مواصفة  %s' % (name[:1], summary(rn)))
