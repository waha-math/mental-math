#!/usr/bin/env python3
"""سجل البند: رابطته بجلسته وحزمته، وما وقع فيه بقيمه (ك2 في مراجعة 04e0168، وهو P0-04).

    python3 tests/test_record_audit.py <ملف الخريطة>

الخلل: سجل البند كان يحفظ هل الإجابة الأولى صحيحة، لا ما هي، ولا يحمل جلسته ولا إصدار محتواه. فإن أُبطلت جلسة
بعد اكتمالها بقيت بنودها في المؤشرات، ولا سبيل إلى استبعادها.

المشهد من مسار الاستخدام: على ملف طفل، الجلسة الأولى لعبها أخوه الأكبر خطأً: أجاب صحيحًا إلا في بنده الثاني.
اكتملت، ومضت بعدها ثلاث جلسات لصاحب الملف، طلب فيها المساعدة في أول بند تقييم لقيه. ثم أبطل البالغ الجلسة الأولى.
المطلوب: تُصحَّح المؤشرات، ويبقى التاريخ قابلًا للمراجعة.

إعدادي الأول للمشهد كان خطأ: جعلتُ جلسة الأخ الثانيةَ وطلبَ المساعدة في أولها، فانتهت بوابتها ببند واحد منقطع ولم
يبقَ ما يُختبر. الخطأ في الإعداد لا في الكود، وصُحّح قبل أي تعديل على الكود.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MAP = sys.argv[1]
src = open(os.path.join(HERE, 'test_phase0.py'), encoding='utf-8').read()
g = {'__file__': os.path.join(HERE, 'test_phase0.py'), '__name__': 'phase0_helpers'}
sys.argv = [g['__file__'], MAP]
exec(compile(src[:src.index("\nprint('=== ")], 'test_phase0.py', 'exec'), g)
import content_source as cs  # noqa: E402
import persist  # noqa: E402
from item_layer import indicators, left_out  # noqa: E402
from scheduler import Scheduler  # noqa: E402
from transition_engine import Engine  # noqa: E402

results = []


def expect(title, got, want):
    ok = got == want
    results.append(ok)
    print('  %s  %s' % ('نجح' if ok else 'أخفق', title))
    if not ok:
        print('        %r، والمتوقع %r' % (got, want))


print('=== سجل البند وإبطال جلسة، بلغة بايثون')
A = cs.load_pack(os.path.join(ROOT, 'slice-content.json'))
IDA = cs.identity(A)
ASSESS = ('gate', 'short', 'check', 'retention')


def play(sessions=4):
    """يلعب حتى تُختم `sessions` جلسات. الأولى للأخ: يخطئ في بنده الثاني وحده. وصاحب الملف يطلب المساعدة في أول بند
    تقييم يلقاه بعد جلسة أخيه."""
    c = g['SCEN']['young']
    e = Engine(g['NET'], group=c['group'])
    for k, (skill, bypass) in enumerate(c['decisions']):
        e.apply(dict(id='d%d' % k, type='teacher_open', skill=skill, bypass=bypass, reason='قرار الشريحة في 10.2'))
    sc = Scheduler(e, g['TYPES'], cs.ContentSource(A['items'], content=IDA), None, group=c['group'],
                   scope=set(c['scope']), learning=True, cap=c['cap'], item_seconds=c['secs'], records=[],
                   retention=False, content=IDA)
    tick = [1000]

    def clock():
        tick[0] += 1
        return tick[0]
    st = g['Stepper'](e, sc, clock=clock)
    st.open(sc.g_run(20))
    asked, k = False, 0
    while st.pending is not None and sum(1 for s in e.s['order'] if e.s['sessions'][s]['ended']) < sessions:
        item, w = st.pending
        sibling = len(e.s['order']) == 1
        k += 1
        if w['activity'] in ('lesson', 'practice'):
            evs = [('end',)]
        elif len(e.s['order']) >= 2 and w['activity'] in ASSESS and not asked:
            evs, asked = [('support', 'requested')], True
        else:
            evs = [('confirm', item['answer'] + (1 if sibling and k == 2 else 0))] + (
                [] if w['activity'] in ASSESS else [('end',)])
        for ev in evs:
            st.event(st.seq, ev)
    return e, sc, st


e, sc, st = play()
T = e.s['order'][0]
mine = [r for r in sc.records if r['session'] == T]
others = [r for r in sc.records if r['session'] != T]
expect('1. كل سجل يحمل معرّفًا لا يتكرر، وجلسته، وإصدار حزمته، والجواب الذي صُحّح به، وقيم إجاباته، ووقته',
       [len({r['id'] for r in sc.records}) == len(sc.records), [r['id'] for r in sc.records[:3]],
        all(r['session'] in e.s['order'] for r in sc.records), {r['pack'] for r in sc.records},
        all('key' in r and 'values' in r and 'support' in r and 'v' in r and r.get('at') for r in sc.records),
        len(mine) > 3 and len(others) > 3],
       [True, ['i0', 'i1', 'i2'], True, {IDA['version']}, True, True])
helped = [r for r in others if r['support']]
expect('2. ما وقع محفوظ بقيمه: في جلسة الأخ إجابة البند الثاني الجواب زائد واحد والباقي الجواب نفسه، وطلب صاحب الملف المساعدة بنوعه وبلا إجابة',
       [[r['values'][0] - r['key'] for r in mine], [r['first'] for r in mine][:3],
        [(r['support'], r['values'], r['session'] != T) for r in helped]],
       [[0, 1] + [0] * (len(mine) - 2), [True, False, True], [(['requested'], [], True)]])
by_id = {i['id']: i for i in A['items']}
expect('3. بصمة البند في سجله هي بصمة تعريفه في الحزمة، والجواب المحفوظ جوابه فيها',
       all(r['v'] == by_id[r['item']]['v'] and r['key'] == by_id[r['item']]['answer'] for r in sc.records), True)

before, n_records = sc.indicators(), len(sc.records)
snap_before = json.dumps(sc.records, sort_keys=True, ensure_ascii=False)
r = e.apply(dict(id='inv-1', type='invalidate_session', target=T))
after = sc.indicators()
done_T = [x for x in mine if not x.get('void') and x['status'] == 'complete']
# المتوقع من القاعدة: مقام «الإجابة الأولى» ينقص بعدد بنود الجلسة المكتملة، وبسطه بعدد ما صحّت إجابته الأولى منها
expect('4. إبطال الجلسة بعد اكتمالها: مؤشر الإجابة الأولى ينقص مقامه بعدد بنودها المكتملة وبسطه بما صحّ منها، والمؤشرات هي مؤشرات بقية السجلات',
       [r['ok'], len(done_T) > 0, before['first_answer']['den'] - after['first_answer']['den'],
        before['first_answer']['num'] - after['first_answer']['num'], after == indicators(others), after != before],
       [True, True, len(done_T), sum(1 for x in done_T if x['first']), True, True])
expect('5. التاريخ باقٍ للمراجعة: السجلات كلها كما هي بقيمها، والمستبعد معدود بسببه',
       [len(sc.records), json.dumps(sc.records, sort_keys=True, ensure_ascii=False) == snap_before, sc.left_out()],
       [n_records, True, dict(void=0, session=len(mine), unlinked=0)])
r2 = e.apply(dict(id='inv-2', type='invalidate_session', target=T))
expect('6. إعادة الإبطال تُرفض ولا تضاعف الأثر', [r2['ok'], sc.indicators() == after], [False, True])
c = g['SCEN']['young']
e2, sc2, notes = persist.restore(json.loads(json.dumps(st.snapshot())), g['NET'], g['TYPES'],
                                 cs.ContentSource(A['items'], content=IDA), None, item_seconds=c['secs'], records=[],
                                 content=IDA)
expect('7. بعد حفظ واستعادة: المؤشرات والمستبعد كما هما، والسجلات المنتهية بقيمها',
       [sc2.indicators() == after, sc2.left_out()['session'], sc2.records[:n_records] == sc.records[:n_records]],
       [True, len(mine), True])
bare = [{k: v for k, v in x.items() if k != 'session'} for x in sc.records]
expect('8. سجلات بلا معرّف جلسة لا تُنسب تخمينًا: تبقى في المؤشرات، ويُذكر عددها',
       [indicators(bare, {T}) == before, left_out(bare, {T})], [True, dict(void=0, session=0, unlinked=n_records)])
print('النتيجة: نجح %d من %d' % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
