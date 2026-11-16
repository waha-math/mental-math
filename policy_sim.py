#!/usr/bin/env python3
"""سياسة التشخيص في 6.2 بالمحرك والمجدول وطبقة البنود: تجارب placement_sim.py نفسها ومقاييسها، بوضع المواصفة.

    python3 policy_sim.py <ملف الخريطة> [عدد التكرارات]

التجارب هي تجارب المحاكاة القديمة: بوابة لا تخطئ، والأساس، والبوابة الصارمة، وبلا إعادة البوابة، ودقة 90%،
وتخمين 50%، وطلب الدعم، وقرار المعلم بالتأجيل وبديله الذي يُسقط التحقق القصير. الطفل وحالاته الثماني من
placement_sim.py نفسه. المقاييس بتعريفاتها هناك، وتُطبع بالصيغة نفسها. الفرق في من يقرر: هنا المجدول بوضع
المواصفة، وأنشطة طبقة البنود، والمحرك يقبل أو يرفض. ومنها أرقام 6.2 و11.1 في الخريطة منذ النسخة 2.7.

المخالفات أربعة أعمدة: حالة تخالف المرجع المستقل (oracle_mismatch في engine_sim.py)، واقتراح رفضه المحرك
أو جلسة لم يُعرض فيها بند، وجلسة فيها نشاطان تعليميان، ومهارة ببوابات أكثر من اثنتين في دورتها.
"""
import multiprocessing
import random
import sys

import placement_sim as old                                 # يقرأ ملف الخريطة من sys.argv[1]
from transition_engine import Engine, STUMBLE
from scheduler import Scheduler, DIAG
from engine_sim import NET, TYPES, abstract_source, oracle_mismatch
from collections import Counter

IDS = list(NET[0])
RUNS = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else old.RUNS

EXPERIMENTS = [
    ('بوابة لا تخطئ (تغطية وعبء فقط)', dict(runs=1, ak=1.0, au=0.0, au_u=0.0)),
    ('الأساس', {}),
    ('بوابة صارمة للمقارنة', dict(tolerant=False)),
    ('بلا إعادة البوابة للمقارنة، وقاعدة اختصار الدرس كما هي', dict(regate=False)),
    ('طفل أقل دقة في ما يعرفه', dict(ak=0.90)),
    ('تخمين أسهل: 0.50 في ما لا يعرفه وفي الفهم', dict(au=0.50, au_u=0.50)),
    ('مع طلب الدعم: 2% من بنود ما يعرفه و20% من غيرها', dict(help_k=0.02, help_u=0.20)),
    ('قرار المعلم: تأجيل تدريس مهارات المرحلتين 1 و2 (27 مهارة) مع بقاء التحقق القصير، للحالتين أ وهـ',
     dict(teacher=True, only='أه')),
    ('بديل للمقارنة: القرار نفسه ويُسقط التحقق القصير أيضًا، للحالتين أ وهـ', dict(teacher=True, trust=True,
                                                                                only='أه')),
]
# القاعدة المعتمدة بقرار الأب (ك4): «جرّب أولًا» من نوعي الخطأ في بوابة المهارة إن أخفقت لها بوابة. وهذه القاعدة
# السابقة للقرار، للمقارنة وحدها، ببذور الأساس نفسها، فالفرق من القاعدة وحدها
ALTERNATIVES = [
    ('الأساس بالقاعدة السابقة للقرار: بندا «جرّب أولًا» الثابتان دائمًا (للمقارنة في ك4)',
     dict(try_from_gate=False), 1),
]


def one(know, start, group, seed, tolerant=True, regate=True, teacher=False, trust=False, try_from_gate=True, **kw):
    random.seed(seed)
    child = old.Child(know, **kw)
    answer = lambda item, want: {True: 'correct', False: 'wrong', None: 'help'}[child.item(item['skill'], want['type'])]
    e = Engine(NET, group=group, regate=regate)
    deferred = sorted(old.STAGES_12, key=IDS.index) if teacher else []
    if deferred:
        r = e.apply(dict(id='defer', type='teacher_defer', skills=deferred, reason='تأجيل تدريس المرحلتين 1 و2'))
        assert r['ok'], r
    sc = Scheduler(e, TYPES, abstract_source, answer, group=group, start=start, tolerant=tolerant,
                   no_short=deferred if trust else (), try_from_gate=try_from_gate)
    w, what = sc.run()
    return sc, w, what


def job(args):
    """حالة واحدة في تجربة واحدة: كل تكراراتها، ثم سطور التقرير بصيغة المحاكاة القديمة."""
    ei, pi, runs = args
    label, opts, seed_ei = (EXPERIMENTS[ei] + (ei,)) if ei < len(EXPERIMENTS) else ALTERNATIVES[ei - len(EXPERIMENTS)]
    opts = dict(opts)
    opts.pop('runs', None)
    opts.pop('only', None)
    name, know, start, group = old.PROFILES[pi]
    needs = [s for s in IDS if know.get(s) != 'full']
    calc_only = [s for s in IDS if know.get(s) == 'calc']
    S = Counter()
    sess0, items0, sess_all, items_all, first_needed = [], [], [], [], []
    cat, what0 = Counter(), Counter()
    for r in range(runs):
        sc, w, what = one(know, start, group, 3000017 * (1 + 10 * seed_ei + pi) + r, **opts)
        e = sc.e
        st = e.derive()
        helped = {a['skill'] for a in e.s['attempts'] if a['result'] == 'help' and a['what'] in ('gate', 'lesson')}
        S['ref'] += oracle_mismatch(e)
        S['viol'] += len(sc.refused) + sc.stalled
        S['teach2'] += sum(1 for v in e.s['sessions'].values() if v['teach'] > 1)
        S['gate3'] += sum(1 for s in IDS if e.valid_gates(s) > 2)
        sess0.append(sc.start_at)
        items0.append(sc.items_before)
        sess_all.append(sc.sessions)
        items_all.append(sum(sc.n[c] for c in DIAG))
        cat.update(sc.n)
        S['gates'] += sc.gates_run
        if what == 'none':
            what0['لا شيء يُدرَّس'] += 1
        elif what == 'use':
            what0['نشاط «استعمل»: لم تُحسم مهارة تُفتح'] += 1
        elif what == 'skip':
            what0['درس اختُصر لمهارة يعرفها' if know.get(w) == 'full' else 'درس اختُصر لمهارة لا يعرفها'] += 1
        elif know.get(w) == 'full':
            what0['درس لا يحتاجه'] += 1
        elif all(know.get(p) == 'full' or (know.get(p) == 'calc' and know.get(w) == 'calc') for p in NET[1][w]):
            what0['درس مناسب'] += 1
        else:
            what0['درس أعلى من مستواه'] += 1
        fn = [x[0] for x in sc.log if x[1] == 'lesson' and know.get(x[2]) != 'full']
        if fn:
            first_needed.append(fn[0])
        lessons = {s for s, o in e.s['opened'].items() if o['phase'] in ('full', 'due')}
        unneeded = sum(1 for s in lessons if know.get(s) == 'full')
        S['unneeded'] += unneeded
        S['unneeded_any'] += int(unneeded > 0)
        S['known_wait'] += sum(1 for s in IDS if know.get(s) == 'full' and st[s] == 'waiting')
        S['known_stum'] += sum(1 for s in IDS if know.get(s) == 'full' and st[s] == 'stumbled')
        S['held'] += sum(1 for s in IDS if (st[s] == 'stumbled' or (s in helped and st[s] in (None, 'deferred')))
                         and s not in e.s['opened'])
        S['unk_exempt'] += sum(1 for s in IDS if s not in know and st[s] == 'exempt')
        S['unk_def'] += sum(1 for s in IDS if know.get(s) != 'full' and st[s] == 'deferred')
        treat = {}
        for x in e.valid_evidence(kind=STUMBLE):
            treat[x['skill']] = x.get('treatment')
        S['co_exempt'] += sum(1 for s in calc_only if st[s] == 'exempt')
        S['co_struct'] += sum(1 for s in calc_only if st[s] == 'stumbled' and treat.get(s) == 'structure')
        S['co_regular'] += sum(1 for s in calc_only if st[s] == 'stumbled' and treat.get(s) == 'regular')
        S['co_other'] += sum(1 for s in calc_only if st[s] not in ('exempt', 'stumbled'))
        S['none_left'] += sum(1 for s in IDS if st[s] is None and s not in helped)
    n = float(runs)
    q, pct = old.q, old.pct
    out = ['  %s  (مهارات تحتاج تعليمًا: %d)' % (name, len(needs))]
    out.append('     قبل أول نشاط تعلّم: الجلسة %d في الوسيط، %d في المئين 95، %d أقصى | بنود تشخيصية قبله: %d وسيط، '
               '%d مئين 95' % (q(sess0, .5), q(sess0, .95), max(sess0), q(items0, .5), q(items0, .95)))
    out.append('     ما جرى في جلسة البدء: ' + '، '.join('%s %s' % (k, pct(v, n)) for k, v in what0.most_common()))
    if first_needed:
        out.append('     أول درس كامل لمهارة يحتاجها: الجلسة %d وسيط، %d مئين 95 (وقع في %s من التكرارات)'
                   % (q(first_needed, .5), q(first_needed, .95), pct(len(first_needed), n)))
    out.append('     حتى اكتمال التشخيص: %d جلسة وسيط، %d مئين 95 | بنود تشخيصية: %d وسيط، %d مئين 95 | '
               'متوسطها: بوابات %.0f (في %.1f بوابة)، تعويض %.1f، «جرّب أولًا» %.1f، تحقق قصير %.0f'
               % (q(sess_all, .5), q(sess_all, .95), q(items_all, .5), q(items_all, .95),
                  cat['gate'] / n, S['gates'] / n, cat['comp'] / n, cat['try'] / n, cat['short'] / n))
    out.append('     دروس كاملة لمهارات يعرفها: %.2f في المتوسط، ووقع واحد على الأقل في %s من التكرارات | '
               'يعرفها وبقيت «متعثّر فيها» %.2f | يعرفها وتنتظر عند النهاية %.2f'
               % (S['unneeded'] / n, pct(S['unneeded_any'], n), S['known_stum'] / n, S['known_wait'] / n))
    out.append('     لا يعرفها وأُعفي %.3f | تحتاج تعليمًا وبقيت مؤجَّلة %.3f | تحتاج درسًا ودرسها ينتظر متطلبًا لم '
               'يُتعلَّم %.1f | بلا حالة %d' % (S['unk_exempt'] / n, S['unk_def'] / n, S['held'] / n, S['none_left']))
    out.append('     مخالفات: حالة تخالف المرجع المستقل %d | اقتراح رفضه المحرك أو جلسة بلا بند %d | جلسة فيها '
               'نشاطان تعليميان %d | مهارة ببوابات أكثر من 2: %d' % (S['ref'], S['viol'], S['teach2'], S['gate3']))
    if calc_only:
        out.append('     مهارات «يحسب ولا يفسّر» (%d): أُعفي %.1f | درس البنية %.1f | المسار العادي %.1f | مؤجَّلة أو '
                   'تنتظر %.1f' % (len(calc_only), S['co_exempt'] / n, S['co_struct'] / n, S['co_regular'] / n,
                                  S['co_other'] / n))
    return ei, '\n'.join(out), sum(S[k] for k in ('ref', 'viol', 'teach2', 'gate3'))


if __name__ == '__main__':
    jobs = []
    alt = '--alt' in sys.argv                      # البدائل وحدها، في مخرجات منفصلة
    table = ([(len(EXPERIMENTS) + k, a[0], a[1]) for k, a in enumerate(ALTERNATIVES)] if alt
             else [(ei, label, opts) for ei, (label, opts) in enumerate(EXPERIMENTS)])
    for ei, label, opts in table:
        for pi, (name, know, start, group) in enumerate(old.PROFILES):
            if opts.get('only') and name[0] not in opts['only']:
                continue
            jobs.append((ei, pi, opts.get('runs', RUNS)))
    print('سياسة التشخيص بالمحرك والمجدول بوضع المواصفة: تجارب placement_sim.py بمقاييسها، %d تكرار لكل حالة'
          % RUNS, flush=True)
    last, bad = None, 0
    with multiprocessing.Pool(2) as pool:
        for ei, text, b in pool.imap(job, jobs):
            if ei != last:
                label, opts = next((lb, op) for e2, lb, op in table if e2 == ei)
                c0 = old.Child({}, **{k: v for k, v in opts.items() if k in ('ak', 'au', 'au_u', 'help_k', 'help_u')})
                print('\n=== %s' % label)
                print('    دقة ما يعرفه %.2f | ما لا يعرفه %.2f | فهم من يحسب ولا يفسّر %.2f | بوابة %s | إعادة البوابة: '
                      '%s | طلب دعم %.2f/%.2f | تكرارات %d'
                      % (c0.ak, c0.au, c0.au_u, 'صارمة' if opts.get('tolerant') is False else 'متسامحة',
                         'لا' if opts.get('regate') is False else 'نعم', c0.help_k, c0.help_u, opts.get('runs', RUNS)))
                last = ei
            print(text, flush=True)
            bad += b
    print('\nمجموع المخالفات في كل التجارب: %d' % bad)
