#!/usr/bin/env python3
"""تأخير بند التقييم الذي يكرر حقيقة ما عُرض قبله (3.5، قرار الأب في 18 نوفمبر 2026).

    python3 tests/test_defer.py <ملف الخريطة>

القاعدة: في البوابة والتحقق القصير وفحص الاستقلال وفحص الاحتفاظ، البند الذي يكرر حقيقة البند الذي عُرض قبله لا يُعرض
الآن ولا يُستبدل: تُعرض البنود التي تليه في مرحلته، ثم يُعرض هو عند أقرب موضع لا تجاور فيه حقيقتُه حقيقةَ بند
الموضع الذي قبله ولا ما بعده، ولا تجاور حقيقةُ بديله عند الانقطاع ما بعده. البنود نفسها والحكم نفسه. وإن لم يوجد
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
            o = c['script'][len(shown)] if len(shown) < len(c['script']) else 'c'
            shown.append(item['id'])
            if w.get('fact_just_seen'):
                marked.append(item['id'])
            got = ([('interrupt',)] if o == 'i' else [('confirm', 1 if o == 'c' else 2)], 1, True)
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
    return out


print('=== تأخير بند التقييم، بلغة بايثون')
CASES = json.load(open(os.path.join(HERE, 'defer_cases.json'), encoding='utf-8'))['cases']
for c in CASES:
    want = {k: c[k] for k in ('shown', 'marked', 'result', 'defer', 'errors', 'answers', 'correct') if k in c}
    want['records'] = c['shown']                            # سجل لكل بند معروض، بترتيب العرض
    expect(c['name'], run_case(c), want)

# 2) على المجدول وطبقة الخطوات والحفظ
SCENE = {'1-4-2/gate/01': dict(numbers={'n': 7}, answer=3, fact=[3, 7]),
         '1-4-2/gate/02': dict(numbers={'n': 4}, answer=6, fact=[4, 6]),
         '1-4-2/gate/03': dict(numbers={'n': 8}, answer=2, fact=[2, 8]),
         '1-4-2/gate/18': dict(numbers={'n': 5}, answer=5, fact=[5, 5]),
         '1-4-2/gate/19': dict(numbers={'n': 9}, answer=1, fact=[1, 9])}
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
print('النتيجة: نجح %d من %d' % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
