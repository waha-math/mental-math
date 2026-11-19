#!/usr/bin/env python3
"""هوية المحتوى وربط المحاولة بها (ك1 في مراجعة 04e0168).

    python3 tests/test_content_identity.py <ملف الخريطة>

الخلل: تغيّرت أعداد 22 بندًا وأجوبتها بين التزامين ورقم إصدار الملف باقٍ 2، والمصدر يختار البند بموضعه من البنك
المحمّل، فمحاولة بدأت ببنك تُستأنف بآخر بصمت. المطلوب: لكل حزمة رقم لا يُعاد وبصمة، ولكل بند بصمة تعريفه، والمحاولة
مربوطة بحزمتها. عند تغيّر المحتوى والنشاط جارٍ: يُستأنف التعريف القديم نفسه إن أُتيحت حزمته، وإلا تُطلب إعادة بدء
صريحة تحفظ ما وقع.

المشهد من مسار الاستخدام: الصغير في بوابة 1-4-2، أجاب عن بندين وعُرض الثالث، ثم أُغلق التطبيق. يصدر محتوى جديد
تغيّر فيه جواب البند الرابع gate/04. ثم يُفتح التطبيق.
"""
import copy
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
from scheduler import Scheduler  # noqa: E402
from transition_engine import Engine  # noqa: E402

results = []


def expect(title, got, want):
    ok = got == want
    results.append(ok)
    print('  %s  %s' % ('نجح' if ok else 'أخفق', title))
    if not ok:
        print('        %r، والمتوقع %r' % (got, want))


def raises(f, kind):
    try:
        f()
    except kind as x:
        return x
    return None


print('=== هوية المحتوى، بلغة بايثون')
A = cs.load_pack(os.path.join(ROOT, 'slice-content.json'))
book = json.load(open(os.path.join(ROOT, 'content-ledger.json'), encoding='utf-8'))['packs']
IDA = cs.identity(A)

# 1) الهوية نفسها
expect('1. آخر مدخل في سجل الإصدارات هو هوية الملف، والأرقام تتزايد والبصمات لا تتكرر',
       [dict(version=book[-1]['version'], digest=book[-1]['digest']) == IDA,
        [x['version'] for x in book] == sorted({x['version'] for x in book}),
        len({x['digest'] for x in book}) == len(book)], [True, True, True])
TARGET = '1-4-2/gate/04'


def changed_pack(pack):
    """محتوى جديد: جواب TARGET وأعداده غير ما كانت. بصمته وبصمة الحزمة ورقمها كما يكتبها المولّد."""
    b = copy.deepcopy(pack)
    it = next(i for i in b['items'] if i['id'] == TARGET)
    it['answer'] = it['answer'] % 9 + 1
    it['numbers'] = dict(it['numbers'], n=10 - it['answer'])
    it['fact'] = sorted([it['answer'], 10 - it['answer']])
    it['v'] = cs.item_digest(it)
    b['digest'] = cs.pack_digest(b)
    b['version'] = cs.next_version(book, b['digest'])
    return b


B = changed_pack(A)
IDB = cs.identity(B)
old = next(i for i in A['items'] if i['id'] == TARGET)
new = next(i for i in B['items'] if i['id'] == TARGET)
expect('2. تغيّر جواب بند: بصمته غير ما كانت، وبصمة الحزمة غير ما كانت، والرقم هو التالي',
       [old['v'] != new['v'], IDA['digest'] != IDB['digest'], IDB['version']], [True, True, IDA['version'] + 1])
tampered = copy.deepcopy(A)
next(i for i in tampered['items'] if i['id'] == TARGET)['answer'] += 1
path = os.path.join(ROOT, 'app', '.tampered-pack.json')
json.dump(tampered, open(path, 'w', encoding='utf-8'), ensure_ascii=False)
err = raises(lambda: cs.load_pack(path), ValueError)
os.remove(path)
expect('3. حزمة عُدّل فيها جواب بند ولم تتغير بصمته: تُرفض عند التحميل', err is not None and TARGET in str(err), True)
expect('4. الرقم لا يُعاد: بصمة آخر مدخل رقمها هو، وبصمة جديدة الرقم التالي، وبصمة سبقت وليست الأخيرة خطأ',
       [cs.next_version(book, IDA['digest']), cs.next_version(book, 'x'),
        raises(lambda: cs.next_version(book + [dict(version=99, digest='y')], IDA['digest']), ValueError) is not None],
       [IDA['version'], IDA['version'] + 1, True])


# 2) المشهد
def source(pack):
    return cs.ContentSource(pack['items'], content=cs.identity(pack))


def build(pack):
    c = g['SCEN']['young']
    e = Engine(g['NET'], group=c['group'])
    for k, (skill, bypass) in enumerate(c['decisions']):
        e.apply(dict(id='d%d' % k, type='teacher_open', skill=skill, bypass=bypass, reason='قرار الشريحة في 10.2'))
    sc = Scheduler(e, g['TYPES'], source(pack), None, group=c['group'], scope=set(c['scope']), learning=True,
                   cap=c['cap'], item_seconds=c['secs'], records=[], retention=False, content=cs.identity(pack))
    return e, sc


def answer(st):
    item, w = st.pending
    for ev in ([('end',)] if w['activity'] in ('lesson', 'practice') else [('confirm', item['answer'])] + (
            [] if w['activity'] in ('gate', 'short', 'check', 'retention', 'describe') else [('end',)])):
        st.event(st.seq, ev)


def closed_in_gate():
    e, sc = build(A)
    st = g['Stepper'](e, sc)
    st.open(sc.g_run(20))
    while st.pending[0]['id'] != '1-4-2/gate/03':
        answer(st)
    st.show(st.seq)
    return json.loads(json.dumps(st.snapshot())), len(sc.records)


def reopen(rec, pack, **more):
    c = g['SCEN']['young']
    return persist.restore(json.loads(json.dumps(rec)), g['NET'], g['TYPES'], source(pack), None,
                           item_seconds=c['secs'], records=[], content=cs.identity(pack), **more)


def gate_items(e, sc, limit=12):
    """ما يُعرض من بوابة 1-4-2 بعد الفتح: (المعرّف، الجواب، البصمة)."""
    st = g['Stepper'](e, sc)
    st.open(sc.g_run(20))
    out = []
    while st.pending is not None and st.pending[0]['id'].startswith('1-4-2/gate/') and len(out) < limit:
        it = st.pending[0]
        out.append((it['id'], it['answer'], it['v']))
        answer(st)
    return out, st


rec, n_before = closed_in_gate()
expect('5. اللقطة تحمل هوية الحزمة التي بدأت بها المحاولة، والبند المعروض يحمل بصمة تعريفه',
       [rec['scheduler']['opts']['content'], rec['scheduler']['opts']['content_version'],
        rec['current']['journal']['v']],
       [IDA, IDA['version'], next(i['v'] for i in A['items'] if i['id'] == '1-4-2/gate/03')])

e, sc, notes = reopen(rec, A)
expect('6. المحتوى لم يتغير: لا ملاحظة عن المحتوى، والمحاولة على حزمتها',
       [[n for n in notes if n[0].startswith('content')], sc.content], [[], IDA])

# المحتوى تغيّر، والحزمة القديمة متاحة: يُستأنف التعريف القديم نفسه
e, sc, notes = reopen(rec, B, packs={IDA['digest']: source(A)})
shown, st = gate_items(e, sc)
got = dict((i, (a, v)) for i, a, v in shown)
expect('7. المحتوى تغيّر والحزمة القديمة متاحة: البوابة تُكمَل، و%s يُعرض بجوابه وبصمته القديمين، والمحاولة باقية على حزمتها'
       % TARGET, [got.get(TARGET), sc.content, persist.snapshot(e, sc, st.current())['scheduler']['opts']['content'],
                  [n for n in notes if n[0].startswith('content')]],
       [(old['answer'], old['v']), IDA, IDA, []])

# المحتوى تغيّر، والحزمة القديمة غير متاحة: رفض صريح، ولا يتغير شيء
mine = []
x = raises(lambda: persist.restore(json.loads(json.dumps(rec)), g['NET'], g['TYPES'], source(B), None,
                                   item_seconds=g['SCEN']['young']['secs'], records=mine, content=IDB),
           persist.ContentChanged)
expect('8. المحتوى تغيّر والحزمة القديمة غير متاحة: يُرفض الاستئناف باسمه، ويُذكر النشاط الجاري، ولا يُمس سجل المستدعي',
       [x is not None and [x.bound, x.offered, x.pending], mine], [[IDA, IDB, [('gate', '1-4-2')]], []])

# إعادة بدء صريحة
e, sc, notes = reopen(rec, B, restart=True)
last = sc.records[-1]
expect('9. إعادة بدء صريحة: ما وقع في البند المعروض يبقى سجلًا مستبعدًا بسببه، وما قبله من السجلات باقٍ، والبوابة تُسقط بمدخل',
       [len(sc.records), last['item'], last.get('void'), last.get('unsettled'),
        [n for n in notes if n[0] in ('void_item', 'content_restart', 'content_changed')],
        [list(x) for x in sc.log if x[1] == 'carry_dropped:content_changed'] != []],
       [n_before + 1, '1-4-2/gate/03', 'content_changed', True,
        [('void_item', '1-4-2', '1-4-2/gate/03', 'content_changed'), ('content_restart', 'gate', '1-4-2'),
         ('content_changed', IDA['version'], IDB['version'])], True])
snap = persist.snapshot(e, sc)
shown, st = gate_items(e, sc)
got = dict((i, (a, v)) for i, a, v in shown)
expect('10. بعدها البوابة تبدأ من الحزمة الجديدة: %s بجوابه وبصمته الجديدين، والمحاولة مربوطة بالجديدة' % TARGET,
       [got.get(TARGET), sc.content, snap['scheduler']['opts']['content']], [(new['answer'], new['v']), IDB, IDB])
e2, sc2, notes2 = reopen(snap, B)
expect('11. اللقطة بعد إعادة البدء تُستعاد بالحزمة الجديدة بلا ملاحظة ولا إسقاط ثانٍ',
       [[n for n in notes2 if n[0].startswith('content') or n[0] == 'void_item'], len(sc2.records)],
       [[], n_before + 1])

# لا نشاط جارٍ: تُربط المحاولة بالحزمة المتاحة
e, sc = build(A)
fresh = json.loads(json.dumps(persist.snapshot(e, sc)))
e, sc, notes = reopen(fresh, B)
expect('12. المحتوى تغيّر ولا نشاط جارٍ: تُربط المحاولة بالحزمة المتاحة، بملاحظة',
       [sc.content, sc.content_version, [n for n in notes if n[0].startswith('content')]],
       [IDB, IDB['version'], [('content_upgraded', IDA['version'], IDB['version'])]])
print('النتيجة: نجح %d من %d' % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
