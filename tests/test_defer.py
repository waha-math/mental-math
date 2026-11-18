#!/usr/bin/env python3
"""تأخير بند التقييم الذي يكرر حقيقة ما عُرض قبله (3.5، قرار الأب في 18 نوفمبر 2026).

    python3 tests/test_defer.py <ملف الخريطة>

القاعدة: في البوابة والتحقق القصير وفحص الاستقلال وفحص الاحتفاظ، البند الذي يكرر حقيقة البند الذي عُرض قبله لا يُعرض
الآن ولا يُستبدل: تُعرض البنود التي تليه في مرحلته، ثم يُعرض هو عند أقرب موضع لا تجاور فيه حقيقتُه حقيقةَ بند
الموضع الذي قبله ولا ما بعده، ولا تجاور حقيقةُ بديله عند الانقطاع ما بعده. تبقى هوية البنود وخاناتها. قاعدة التوقف تُطبَّق على ترتيب العرض الفعلي، فقد يتغير ما يُعرض وسبب الانتهاء (القسمان 3 و4). كان النص هنا: البنود نفسها والحكم نفسه. وإن لم يوجد
موضع (آخر مرحلته، أو كل موضع يجاور) عُرض موسومًا fact_just_seen.

1. حالات tests/defer_cases.json بمصدر مصنوع، على طبقة البنود مباشرة. تُشغَّل هي نفسها في tests/test_defer.mjs. المتوقع
   فيها مكتوب من القاعدة قبل التشغيل.
2. على المجدول وطبقة الخطوات والحفظ بمحتوى الشريحة: يُحقن «آخر بند عُرض» قبل أول بند في بوابة 1-4-2 (إدخال مصنوع).
   المسار الذي يقع فيه هذا الدخول فعلًا، التحقق القصير ثم فحص الاستقلال، في متجهات المجدول بتصادم مفروض
   (export_scheduler.py، القسم 5)، وتعيده مطابقة المجدول في اللغتين. بنود المشهد مثبتة بأعدادها. يُقارن الترتيب
   المتصل بالمتوقع من القاعدة، ثم يُغلق التطبيق والبند المؤجَّل مطلوب لم يُعرض ويُستعاد، ويُقارن الترتيب ونتيجة البوابة.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MAP = sys.argv[1]
src = open(os.path.join(HERE, 'test_phase0.py'), encoding='utf-8').read()
g = {'__file__': os.path.join(HERE, 'test_phase0.py'), '__name__': 'phase0_helpers'}
sys.argv = [g['__file__'], MAP]
exec(compile(src[:src.index("\nprint('=== ")], 'test_phase0.py', 'exec'), g)
from item_layer import Activity, GateRun, ShortCheckRun, CheckRun, RetentionRun, drive_steps  # noqa: E402

results = []


def expect(title, got, want):
    ok = got == want
    results.append(ok)
    print('  %s  %s' % ('نجح' if ok else 'أخفق', title))
    if not ok:
        print('        %r، والمتوقع %r' % (got, want))


def key_of(w):
    a = w['activity']
    if a == 'gate':
        if w['alternate']:
            return 'alt:%s:%d' % (w['type'], w['alt_index'])
        return 'gate:%d' % w['pos'] if w['role'] == 'gate' else 'comp:%s:%d' % (w['type'], w['pos'])
    if a == 'short':
        return 'short:%d' % w['pos']
    if a == 'check':
        return ('checkalt:%d' if w['alternate'] else 'check:%d') % w['slot']
    return 'ret:%d' % w['pos']


def make(c):
    if c['act'] == 'gate':
        return GateRun('S', c['types'])
    if c['act'] == 'short':
        return ShortCheckRun('S', c['types'])
    if c['act'] == 'check':
        return CheckRun('S', 'S/check/1', 1)
    return RetentionRun('S', 1)


def run_case(c):
    facts = c['facts']

    def source(skill, w):
        k = key_of(w)
        return dict(id=k, fact=[facts[k]]) if k in facts else None
    act, shown, marked, recs = make(c), [], [], []
    prev = lambda: ('p', [c['prev']])                       # noqa: E731
    gen = drive_steps(act, source, recs, prev=prev)
    try:
        item, w = next(gen)
        while True:
            o = c.get('by_id', {}).get(item['id']) or (c['script'][len(shown)] if len(shown) < len(c['script']) else 'c')
            shown.append(item['id'])
            if w.get('fact_just_seen'):
                marked.append(item['id'])
            got = ([('interrupt',)] if o == 'i' else [('support', 'requested'), ('interrupt',)] if o == 'h'
                   else [('confirm', 1 if o == 'c' else 2)], 1, True)
            if c.get('roundtrip') == len(shown):            # يُحفظ النشاط بعد هذا البند ويُنشأ من لقطته
                try:
                    gen.send(got)
                except StopIteration:
                    break
                act = Activity.from_dict(json.loads(json.dumps(act.to_dict())))
                gen = drive_steps(act, source, recs)
                item, w = next(gen)
                continue
            item, w = gen.send(got)
    except StopIteration:
        pass
    out = dict(shown=shown, marked=marked, result=act.result, defer=getattr(act, 'defer', None))
    if 'errors' in c:
        out['errors'] = act.errors
    if 'answers' in c:
        out['answers'] = {k: act.answers[k] for k in c['answers']}
    if 'correct' in c:
        out['correct'] = act.correct
    out['records'] = [r['item'] for r in recs]
    out['ahead'] = {r['item']: r['ahead_of'] for r in recs if r.get('ahead_of')}
    if 'weak' in c:                                         # ت2: سجلات «أداء بعد تعرض مباشر»
        out['weak'] = [r['item'] for r in recs if r.get('after_exposure')]
    return out


print('=== تأخير بند التقييم، بلغة بايثون')
CASES = json.load(open(os.path.join(HERE, 'defer_cases.json'), encoding='utf-8'))['cases']
for c in CASES:
    want = {k: c[k] for k in ('shown', 'marked', 'result', 'defer', 'errors', 'answers', 'correct', 'ahead', 'weak')
            if k in c}
    want['records'] = c['shown']                            # سجل لكل بند معروض، بترتيب العرض
    expect(c['name'], run_case(c), want)

# ت2 على النشاط مباشرة: نتيجة exposed (إجابة صحيحة عن حقيقة عُرضت للتو) في فحص الاستقلال وفحص الاحتفاظ
for c in json.load(open(os.path.join(HERE, 'defer_cases.json'), encoding='utf-8'))['feeds']:
    act = make(c)
    for o in c['feeds']:
        act.feed(o)
    w = act.want()
    got = dict(result=act.result, slot=getattr(act, 'slot', None), total_cuts=getattr(act, 'total_cuts', None),
               correct=act.correct, hold=getattr(act, 'hold', None), role=w['role'] if w else None,
               events=[e['type'] for e in act.events()] if act.done else [], done=act.done)
    expect(c['name'], {k: got[k] for k in c['want']}, c['want'])


# 3) هل يغيّر التأخير الحكم؟ (ت1 في مراجعة 04e0168)
# قاعدة التوقف تُطبَّق على ترتيب العرض الفعلي، فقد يغيّر التأخير ما يصل إليه الطفل وسبب انتهاء النشاط (الحالتان ث1 وث2).
# هنا يُقاس النطاق: لكل نشاط وتخطيط حقائق، كل توزيع نتائج على البنود بمعرّفاتها (صحيح، خطأ، طلب دعم؛ بلا انقطاع
# ولا بدائل)، ويُقارن حكم الترتيب الأصلي بحكم الترتيب بعد تأخير أول بند. التوزيع يُبنى بالتفريع: ما عُرض في الترتيب
# الأصلي ثابت، وما لم يُعرض فيه وعُرض بعد التأخير يُفرَّع على النتائج الثلاث.
# الفرضية المكتوبة قبل التشغيل: الاجتياز لا ينقلب، أي يجتاز الترتيبان معًا أو لا يجتاز أيٌّ منهما. وما عداه قد يتبدل.
RAW = {'c': [('confirm', 1)], 'w': [('confirm', 2)], 'h': [('support', 'requested'), ('interrupt',)]}


def verdict(act):
    if isinstance(act, RetentionRun):           # بعد ت3 طلب المساعدة ينهي الجولة بلا عدّ: الحكم help لا عدد الصحيح قبله
        return 'done:%d' % act.correct if act.result == 'done' else act.result
    if isinstance(act, GateRun) and act.result == 'fail':       # أنواع الأخطاء تحدد علاج التعثّر في المحرك
        return 'fail[%s]' % '+'.join(sorted(act.errors))
    return {True: 'pass', False: 'fail'}.get(act.result, act.result)


def outcomes_of(c, prior, fixed):
    """كل الأحكام الممكنة للنشاط حين يسبقه بند حقيقته prior، والنتائج في fixed ثابتة بمعرّف البند. يعيد قائمة
    (الحكم، التوزيع بعد إكماله)."""
    out, stack = [], [(dict(fixed), [])]
    while stack:
        prof, path = stack.pop()
        act = make(c)
        gen = drive_steps(act, lambda skill, w: (dict(id=key_of(w), fact=[c['facts'][key_of(w)]])
                                                  if key_of(w) in c['facts'] else None), [], prev=lambda: ('p', [prior]))
        branched = False
        try:
            item, w = next(gen)
            while True:
                if item['id'] not in prof:
                    for o in 'cwh':
                        stack.append((dict(prof, **{item['id']: o}), path))
                    branched = True
                    break
                item, w = gen.send((RAW[prof[item['id']]], 1, True))
        except StopIteration:
            pass
        if not branched:
            out.append((verdict(act), prof))
    return out


LAYOUTS = [
    ('بوابة بنوعين، حقائق مختلفة', dict(act='gate', types=['ف1', 'ف3'], facts=dict(
        {'gate:%d' % k: 'ABCDEFG'[k] for k in range(7)},
        **{'comp:%s:%d' % (t, k): 'XY'[k] for t in ('ف1', 'ف3') for k in range(2)}))),
    ('بوابة بنوعين، الثالث بحقيقة الأول', dict(act='gate', types=['ف1', 'ف3'], facts=dict(
        {'gate:%d' % k: 'ABACDEF'[k] for k in range(7)},
        **{'comp:%s:%d' % (t, k): 'XY'[k] for t in ('ف1', 'ف3') for k in range(2)}))),
    ('بوابة بثلاثة أنواع، الثالث بحقيقة الأول', dict(act='gate', types=['ف2', 'ف3', 'ف4'], facts=dict(
        {'gate:%d' % k: 'ABACDEFGH'[k] for k in range(9)},
        **{'comp:%s:%d' % (t, k): 'XY'[k] for t in ('ف2', 'ف3', 'ف4') for k in range(2)}))),
    ('تحقق قصير', dict(act='short', types=['ف1', 'ف3'], facts={'short:%d' % k: 'ABC'[k] for k in range(3)})),
    ('فحص استقلال، حقائق مختلفة', dict(act='check', facts={'check:%d' % k: 'ABCDEFGHIJ'[k - 1] for k in range(1, 11)})),
    ('فحص استقلال، الثالثة بحقيقة الأولى', dict(act='check', facts={'check:%d' % k: 'ABACDEFGHI'[k - 1] for k in range(1, 11)})),
    ('فحص احتفاظ', dict(act='retention', facts={'ret:%d' % k: 'ABCDE'[k] for k in range(5)})),
]
from collections import Counter  # noqa: E402
flips_all = Counter()
for title, c in LAYOUTS:
    table, n = Counter(), 0
    for v0, prof in outcomes_of(c, 'Z', {}):
        for v1, _full in outcomes_of(c, 'A', prof):
            n += 1
            table[(v0, v1)] += 1
    changed = {k: v for k, v in table.items() if k[0] != k[1]}
    flips_all.update({(title, k): v for k, v in changed.items()})
    print('        %s: %d توزيعًا، تغيّر الحكم في %d: %s' % (title, n, sum(changed.values()), '، '.join(
        '%s ← %s (%d)' % (a, b, v) for (a, b), v in sorted(changed.items())) or 'لا شيء'))
    expect('ن. %s: الاجتياز لا ينقلب بالتأخير' % title,
           sorted(k for k in changed if 'pass' in k), [])

# 2) على المجدول وطبقة الخطوات والحفظ
SCENE = {'1-4-2/gate/01': dict(numbers={'n': 7}, answer=3, fact=[3, 7]),
         '1-4-2/gate/02': dict(numbers={'n': 4}, answer=6, fact=[4, 6]),
         '1-4-2/gate/03': dict(numbers={'n': 8}, answer=2, fact=[2, 8]),
         '1-4-2/gate/18': dict(numbers={'n': 5}, answer=5, fact=[5, 5]),
         '1-4-2/gate/19': dict(numbers={'n': 9}, answer=1, fact=[1, 9]),
         # بقية بنود البوابة مثبتة بأعدادها في الحزمة 4: المشهد البوابة كلها، وتغيّر عدد gate/04 في الحزمة 5 أدخل فيه تأخيرًا
         '1-4-2/gate/04': dict(numbers={'n': 1}, answer=9, fact=[1, 9]),
         '1-4-2/gate/05': dict(numbers={'n': 5}, answer=5, fact=[5, 5]),
         '1-4-2/gate/06': dict(numbers={'n': 9, 'ctx': 'ctx_bus'}, answer=1, fact=[1, 9]),
         '1-4-2/gate/07': dict(numbers={'n': 6, 'ctx': 'ctx_balloons'}, answer=4, fact=[4, 6]),
         '1-4-2/gate/08': dict(numbers={'n': 2}, answer=8, fact=[2, 8]),
         '1-4-2/gate/09': dict(numbers={'n': 3}, answer=7, fact=[3, 7])}
ORDER = ['1-4-2/gate/02', '1-4-2/gate/01'] + ['1-4-2/gate/%02d' % k for k in range(3, 10)]
PLAIN = ['1-4-2/gate/%02d' % k for k in range(1, 10)]


def wire(sc, inject):
    inner, done = sc.source, []

    def source(skill, w):
        it = inner(skill, w)
        if it is not None and it['id'] in SCENE:
            it = dict(it, **SCENE[it['id']])
        if inject and not done and not w.get('peek') and it is not None and it['id'] == '1-4-2/gate/01':
            done.append(1)                                  # الحقن: آخر بند عُرض للمهارة من نشاط آخر، بحقيقة gate/01
            sc.last = dict(session=sc.cur, skill='1-4-2', activity='lesson', item='1-4-2/lesson/x', fact=[3, 7],
                           counts=True)
        return it
    sc.source = source


def scene(inject, close_at=None):
    e, sc = g['build']('young')
    wire(sc, inject)
    st = g['Stepper'](e, sc)
    st.open(sc.g_run(20))
    shown, n = [], 0
    while st.pending is not None and n < 400:
        item, w = st.pending
        if close_at is not None and item['id'] == close_at:
            e, sc, _notes = g['reopen']('young', st.snapshot())
            wire(sc, False)
            st = g['Stepper'](e, sc)
            st.open(sc.g_run(20))
            close_at = None
            continue
        n += 1
        if item['id'].startswith('1-4-2/gate/'):
            shown.append((item['id'], w.get('fact_just_seen')))
        if w['activity'] in ('lesson', 'practice'):
            evs = [('end',)]
        else:
            evs = [('confirm', item['answer'])] + ([] if w['activity'] in ('gate', 'short', 'check', 'retention') else [('end',)])
        for ev in evs:
            st.event(st.seq, ev)
        if len(shown) == 9 and shown[-1][0] == item['id']:
            break
    recs = [r['item'] for r in sc.records if r['skill'] == '1-4-2' and r['activity'] == 'gate']
    return [i for i, _m in shown], [m for _i, m in shown if m], recs, e.derive().get('1-4-2')


plain = scene(False)
expect('م1. بلا حقن: بوابة 1-4-2 بترتيب المحتوى، بلا وسم', list(plain[:3]), [PLAIN, [], PLAIN])
cont = scene(True)
expect('م2. بالحقن: يُبدأ بالبند الثاني ثم الأول، بلا وسم، وسجل لكل بند بترتيب عرضه', list(cont[:3]), [ORDER, [], ORDER])
expect('م3. حالة المهارة بعد البوابة واحدة بالتأخير وبدونه، وهي الإعفاء', [cont[3], plain[3]], ['exempt', 'exempt'])
again = scene(True, close_at='1-4-2/gate/01')
expect('م4. إغلاق والبند المؤجَّل مطلوب لم يُعرض، ثم استعادة: الترتيب والسجلات وحالة المهارة كالمتصل', list(again), list(cont))

# وسوم الطلب تبقى في السجل حين تختم الاستعادةُ البند لا الجلسة: البند عُرض ثم أُغلق التطبيق. الأول عُرض قبل بند أُخّر
# (ahead_of)، والثاني لا موضع يُؤخَّر إليه (كل بنود البوابة بحقيقته) فعُرض موسومًا (fact_just_seen)
def settled(pins, target):
    pins = dict(pins)                                       # نسخة: pins قد تكون SCENE نفسها، وكان clear يفرغها معها فيجري
    keep = dict(SCENE)                                      # المشهد بلا تثبيت، ونجح قبل الحزمة 5 لأن عدد gate/01 فيها وافق
    SCENE.clear()
    SCENE.update(pins)
    try:
        e, sc = g['build']('young')
        wire(sc, True)
        st = g['Stepper'](e, sc)
        st.open(sc.g_run(20))
        n = 0
        while st.pending is not None and st.pending[0]['id'] != target and n < 400:
            item, w = st.pending
            n += 1
            for ev in ([('end',)] if w['activity'] in ('lesson', 'practice') else [('confirm', item['answer'])] + (
                    [] if w['activity'] in ('gate', 'short', 'check', 'retention') else [('end',)])):
                st.event(st.seq, ev)
        st.show(st.seq)
        e, sc, _notes = g['reopen']('young', st.snapshot())
        r = [x for x in sc.records if x['item'] == target][-1]
        return {k: r.get(k) for k in ('unsettled', 'fact_just_seen', 'ahead_of')}
    finally:
        SCENE.clear()
        SCENE.update(keep)


expect('م5. بند عُرض قبل بند أُخّر، ثم إغلاق واستعادة تختمه: سجله يحمل ما أُخّر',
       settled(SCENE, '1-4-2/gate/02'), dict(unsettled=True, fact_just_seen=None, ahead_of=['1-4-2/gate/01']))
SAME = {'1-4-2/gate/%02d' % k: dict(numbers={'n': 7}, answer=3, fact=[3, 7]) for k in range(1, 10)}
expect('م6. بند لا موضع يُؤخَّر إليه عُرض موسومًا، ثم إغلاق واستعادة تختمه: سجله يحمل الوسم',
       settled(SAME, '1-4-2/gate/01'), dict(unsettled=True, fact_just_seen='1-4-2/lesson/x', ahead_of=None))

# 4) أثر تغيّر الحكم على المهارة وما بعدها (ت1): المشهد ث1 وث2 على المجدول بمحتوى الشريحة. الطفل يطلب الدعم في
# gate/01 ويخطئ في gate/02 و gate/03، بمعرّف البند. بلا حقن تنتهي البوابة بطلب الدعم، وبالحقن يُؤخَّر gate/01 إلى ما
# بعد gate/04 (gate/03 بحقيقته) فتنتهي بالإخفاق بعد خطأين.
# المتوقع من القاعدة (transition_engine: gate_result): الإخفاق دليل تعثّر، فحالة المهارة stumbled. وطلب الدعم بلا
# دليل، فلا حالة لها. ما يُعرض بعد البوابة مقيس لا مشتق، ويُطبع.
SCENE_T1 = {'1-4-2/gate/01': dict(numbers={'n': 7}, answer=3, fact=[3, 7]),
            '1-4-2/gate/02': dict(numbers={'n': 4}, answer=6, fact=[4, 6]),
            '1-4-2/gate/03': dict(numbers={'n': 7}, answer=3, fact=[3, 7]),
            '1-4-2/gate/04': dict(numbers={'n': 9}, answer=1, fact=[1, 9]),
            '1-4-2/gate/05': dict(numbers={'n': 5}, answer=5, fact=[5, 5]),
            '1-4-2/gate/18': dict(numbers={'n': 8}, answer=2, fact=[2, 8]),
            '1-4-2/gate/19': dict(numbers={'n': 4}, answer=6, fact=[4, 6])}


def scene_t1(inject):
    SCENE.clear()
    SCENE.update(SCENE_T1)
    e, sc = g['build']('young')
    wire(sc, inject)
    st = g['Stepper'](e, sc)
    st.open(sc.g_run(20))
    shown, after, n = [], None, 0
    while st.pending is not None and n < 400:
        item, w = st.pending
        n += 1
        if item['id'].startswith('1-4-2/gate/'):
            shown.append(item['id'])
        elif shown:
            after = (item['id'].rsplit('/', 1)[0], w['activity'])
            break
        if item['id'] == '1-4-2/gate/01':
            evs = [('support', 'requested')]
        elif item['id'] in ('1-4-2/gate/02', '1-4-2/gate/03'):
            evs = [('confirm', item['answer'] + 1)]
        elif w['activity'] in ('lesson', 'practice'):
            evs = [('end',)]
        else:
            evs = [('confirm', item['answer'])] + ([] if w['activity'] in ('gate', 'short', 'check', 'retention') else [('end',)])
        for ev in evs:
            st.event(st.seq, ev)
    att = [a['result'] for a in e.s['attempts'] if a['skill'] == '1-4-2' and a['what'] == 'gate']
    treat = [x.get('treatment') for x in e.s['evidence'] if x['skill'] == '1-4-2'] if isinstance(e.s.get('evidence'), list) else None
    return dict(shown=shown, attempts=att, status=e.derive().get('1-4-2'), after=after, treatment=treat)


keep = dict(SCENE)
t_plain, t_defer = scene_t1(False), scene_t1(True)
SCENE.clear()
SCENE.update(keep)
print('        بلا تأخير: %r' % (t_plain,))
print('        بالتأخير:  %r' % (t_defer,))
expect('ث3. على المجدول بلا حقن: يُعرض gate/01 وحده، ومحاولة البوابة «طلب دعم»، ولا حالة للمهارة',
       [t_plain['shown'], t_plain['attempts'], t_plain['status']], [['1-4-2/gate/01'], ['help'], None])
expect('ث4. بالحقن: يُعرض gate/02 ثم gate/03، ومحاولة البوابة «إخفاق»، وحالة المهارة تعثّر',
       [t_defer['shown'], t_defer['attempts'], t_defer['status']],
       [['1-4-2/gate/02', '1-4-2/gate/03'], ['fail'], 'stumbled'])
expect('ث5. ما بعد البوابة يختلف (مقيس، كُتب بعد رؤية الناتج): بعد طلب الدعم افتتاح الدرس ببنوده الثابتة، وبعد الإخفاق '
       'افتتاحه ببنود «جرّب أولًا»، وعلاج التعثّر regular',
       [list(t_plain['after']), list(t_defer['after']), t_plain['treatment'], t_defer['treatment']],
       [['1-4-2/opening', 'opening'], ['1-4-2/tryfirst', 'opening'], [], ['regular']])

# 5) ت2 على المجدول: «أداء بعد تعرض مباشر» في بوابة 1-4-2 بمحتوى الشريحة. بنود البوابة التسعة مثبتة بحيث يجاور كل موضع
# حقيقة أولها (3 و7)، فأولها بعد الحقن لا موضع يُؤخَّر إليه ويُعرض موسومًا. والطفل يجيب صحيحًا عن كل بند.
# المتوقع من القاعدة: إجابته عن الأول لا تُحتسب. يُطلب بديل نوعه (gate/18، مثبت بحقيقة أخرى)، ثم تمضي البوابة ببنودها
# المستقلة وتُجتاز، فالمهارة معفاة بها لا به. وبمحتوى حُجبت بدائله: تُعلَّق البوابة بلا نتيجة، ولا تعثّر
P2 = {'1-4-2/gate/%02d' % (k + 1): dict(numbers={'n': n}, answer=10 - n, fact=sorted((n, 10 - n)))
      for k, n in enumerate([7, 4, 7, 8, 7, 9, 7, 5, 7])}
P2.update({'1-4-2/gate/18': dict(numbers={'n': 9}, answer=1, fact=[1, 9])})


def scene_t2(no_alts):
    keep = dict(SCENE)
    SCENE.clear()
    SCENE.update(P2)
    try:
        e, sc = g['build']('young')
        wire(sc, True)
        if no_alts:
            inner = sc.source
            sc.source = lambda skill, w: None if w.get('activity') == 'gate' and w.get('alternate') else inner(skill, w)
        st = g['Stepper'](e, sc)
        st.open(sc.g_run(20))
        shown, n = [], 0

        def tries():
            return [a['result'] for a in e.s['attempts'] if a['skill'] == '1-4-2' and a['what'] == 'gate']
        while st.pending is not None and n < 400 and not tries():
            item, w = st.pending
            n += 1
            if item['id'].startswith('1-4-2/gate/'):
                shown.append((item['id'], bool(w.get('fact_just_seen'))))
            for ev in ([('end',)] if w['activity'] in ('lesson', 'practice') else [('confirm', item['answer'])] + (
                    [] if w['activity'] in ('gate', 'short', 'check', 'retention') else [('end',)])):
                st.event(st.seq, ev)
        return dict(shown=[i for i, _m in shown], marked=[i for i, m in shown if m],
                    weak=[r['item'] for r in sc.records if r.get('after_exposure')], attempts=tries(),
                    status=e.derive().get('1-4-2'),
                    stumbles=len([x for x in e.s['evidence'] if x['skill'] == '1-4-2' and x['kind'] == 'stumble']),
                    independent=sc.indicators()['independent']['num'] - len([r for r in sc.records
                                                                             if r['status'] == 'complete' and r['first']
                                                                             and not r['support_before']]))
    finally:
        SCENE.clear()
        SCENE.update(keep)


G18 = '1-4-2/gate/18'
expect('ع11 (ت2). على المجدول: الأول موسوم وإجابته الصحيحة «أداء بعد تعرض مباشر» لا تدخل عدّ الصحيح المستقل. يُطلب بديل نوعه، '
       'وتُجتاز البوابة بالبنود المستقلة، فالمهارة معفاة',
       scene_t2(False),
       dict(shown=['1-4-2/gate/01', G18] + ['1-4-2/gate/%02d' % k for k in range(2, 10)], marked=['1-4-2/gate/01'],
            weak=['1-4-2/gate/01'], attempts=['pass'], status='exempt', stumbles=0, independent=-1))
expect('ع12 (ت2). والبدائل محجوبة: البوابة تُعلَّق بلا نتيجة بعد بندها الأول. لا إعفاء ولا تعثّر: نقص البدائل ليس إخفاقًا',
       scene_t2(True),
       dict(shown=['1-4-2/gate/01'], marked=['1-4-2/gate/01'], weak=['1-4-2/gate/01'], attempts=['interrupted'],
            status=None, stumbles=0, independent=-1))

print('النتيجة: نجح %d من %d' % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
