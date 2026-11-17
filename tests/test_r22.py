#!/usr/bin/env python3
"""المراجعة 22: التتابع بين أنشطة المهارة في الجلسة نفسها (R22-01).

    python3 tests/test_r22.py <ملف الخريطة>            # يعيد تشغيل الشريط المحفوظ tests/r22_tape.json
    python3 tests/test_r22.py <ملف الخريطة> --write    # يولّد الشريط من جديد (بعد تغيير مقصود في المسار)

المشهد من المراجع: إعداد young، 20 جلسة، random.Random(79)، واحتمال الإجابة الصحيحة 0.6 لكل بند مجاب، والخاطئة
الجواب + 1، وبنود العرض تنتهي بـend. الشريط يحفظ لكل بند معروض معرّفه وأحداثه، فيُعاد في بايثون وJavaScript بلا عشوائية.

القاعدة: الحقيقة نفسها لا تُعرض في بندين متتاليين (3.5)، ولو كانا من نشاطين. في الجلسة 10 تنتهي بوابة 1-4-2 بخطأ ثانٍ
في gate/03 (8 + ▢ = 10، الحقيقة 2 و8). نوعا الخطأ ف3 ثم ف3، فبندا «جرّب أولًا» من ف3: tryfirst/03 (▢ + 8 = 10، الحقيقة
2 و8) ثم tryfirst/04. المتوقع: يُبدأ بالآخر tryfirst/04 (4 و6)، ثم tryfirst/03.
بنود المشهد الخمسة مثبتة في الاختبار بأعدادها عند 03d2e0d (SCENE)، فلا يتغير المشهد بتغيّر أعداد المحتوى.
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MAP, WRITE = sys.argv[1], '--write' in sys.argv
src = open(os.path.join(HERE, 'test_phase0.py'), encoding='utf-8').read()
g = {'__file__': os.path.join(HERE, 'test_phase0.py'), '__name__': 'phase0_helpers'}
sys.argv = [g['__file__'], MAP]
exec(compile(src[:src.index("\nprint('=== ")], 'test_phase0.py', 'exec'), g)
TAPE = os.path.join(HERE, 'r22_tape.json')
# المشهد لا يعتمد على أعداد المحتوى الحالي: بنوده الخمسة مثبتة هنا بأعدادها عند 03d2e0d. المولّد قد يغيّر أعداد
# المحتوى (وقد غيّر tryfirst/03 بعد أن صار فحص التتابع يستكشف هذا الفرع)، والاختبار يبقى على علاج التشغيل نفسه
SCENE = {'1-4-2/gate/01': dict(numbers={'n': 7}, answer=3, fact=[3, 7]),
         '1-4-2/gate/02': dict(numbers={'n': 4}, answer=6, fact=[4, 6]),
         '1-4-2/gate/03': dict(numbers={'n': 8}, answer=2, fact=[2, 8]),
         '1-4-2/tryfirst/03': dict(numbers={'n': 8}, answer=2, fact=[2, 8]),
         '1-4-2/tryfirst/04': dict(numbers={'n': 6}, answer=4, fact=[4, 6])}
DISPLAY = ('lesson', 'practice')
ASSESS = ('gate', 'short', 'check', 'retention')


def fact(it):
    n = it['numbers']
    if 'a' in n:
        return [n['a'], n['b']]
    v = n.get('n', n.get('e'))
    return sorted((v, 10 - v))


def pinned(sc):
    inner = sc.source

    def source(skill, w):                                   # بنود المشهد كما كانت في محتوى 03d2e0d، أيًّا كان المحتوى الآن
        it = inner(skill, w)
        return dict(it, **SCENE[it['id']]) if it is not None and it['id'] in SCENE else it
    sc.source = source


def run(tape=None, close_at=None):
    """يشغّل المشهد. بلا شريط: بالعشوائية، ويعيد الشريط. بشريط: يعيد أحداثه ويتحقق أن البنود هي نفسها.
    close_at: يُغلق التطبيق والبند بهذا المعرّف مطلوب لم يُعرض، ثم تُستعاد اللقطة ويُكمَل الشريط."""
    e, sc = g['build']('young')
    pinned(sc)
    st = g['Stepper'](e, sc)
    st.open(sc.g_run(20))
    rng, out, k = random.Random(79), [], 0
    while st.pending is not None:
        if close_at is not None and st.pending[0]['id'] == close_at:
            e, sc, _notes = g['reopen']('young', st.snapshot())
            pinned(sc)
            st = g['Stepper'](e, sc)
            st.open(sc.g_run(20))
            close_at = None
            continue
        item, w = st.pending
        if tape is None:
            if w['activity'] in DISPLAY:
                evs = [['end']]
            else:
                ans = item['answer'] if rng.random() < 0.6 else item['answer'] + 1
                evs = [['confirm', ans]] + ([] if w['activity'] in ASSESS else [['end']])
        else:
            if k >= len(tape) or tape[k]['item'] != item['id']:
                return out, 'البند رقم %d: %s، وفي الشريط %s' % (k, item['id'], tape[k]['item'] if k < len(tape) else 'لا شيء')
            evs = tape[k]['events']
        out.append(dict(session=e.s['current'], skill=item['skill'], activity=w['activity'], item=item['id'],
                        fact=fact(item), events=evs, just_seen=w.get('fact_just_seen')))
        for ev in evs:
            st.event(st.seq, tuple(ev))
        k += 1
    if tape is not None and k != len(tape):
        return out, 'انتهى التشغيل عند %d والشريط %d' % (k, len(tape))
    return out, None


results = []


def expect(title, got, want):
    ok = got == want
    results.append(ok)
    print('  %s  %s' % ('نجح' if ok else 'أخفق', title))
    if not ok:
        print('        %r، والمتوقع %r' % (got, want))


if WRITE:
    out, _ = run()
    json.dump([dict(item=x['item'], events=x['events']) for x in out], open(TAPE, 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))
    print('كُتب الشريط: %d بندًا' % len(out))
tape = json.load(open(TAPE, encoding='utf-8'))
out, err = run(tape)
print('=== المراجعة 22، بلغة بايثون')
expect('1. الشريط يُعاد كله: البنود المعروضة هي بنود الشريط', [err, len(out)], [None, len(tape)])
s10 = [x['item'] for x in out if x['session'] == 'S10' and x['skill'] == '1-4-2'][:5]
expect('2. الجلسة 10: بعد gate/03 يُبدأ «جرّب أولًا» بالبند الآخر من نوعه، لا بالذي يكرر الحقيقة',
       s10, ['1-4-2/gate/01', '1-4-2/gate/02', '1-4-2/gate/03', '1-4-2/tryfirst/04', '1-4-2/tryfirst/03'])
same = [(a['item'], b['item']) for a, b in zip(out, out[1:])
        if a['session'] == b['session'] and a['skill'] == b['skill'] and a['item'] != b['item']
        and a['fact'] == b['fact'] and b['activity'] not in DISPLAY and not b['just_seen']]
expect('3. في المسار كله: لا بندان متتاليان بالحقيقة نفسها للمهارة نفسها في الجلسة نفسها، خارج دخول بنود العرض '
       'التعليمي وما وُسم', same, [])
again, err2 = run(tape, close_at='1-4-2/tryfirst/04')
expect('9. إغلاق وبند «جرّب أولًا» الأول مطلوب لم يُعرض، ثم استعادة: الشريط يُكمَل بالبنود نفسها',
       [err2, [x['item'] for x in again] == [x['item'] for x in out]], [None, True])

# علاج كل نشاط عند دخوله ببند يكرر حقيقة آخر ما عُرض من نشاط آخر، على طبقة البنود مباشرة
sys.path.insert(0, os.path.dirname(HERE))
from item_layer import OpeningRun, EvidenceRun, GateRun, drive_steps  # noqa: E402

o = OpeningRun('1-4-2', ['ف2', 'ف3', 'ف4'], try_types=['ف3', 'ف3'], typed=True)
steps = [o.want()['type_index'], o.repeated('a'), o.want()['type_index'], o.repeated('b'), o.want()['role'], o.try_out]
expect('4. افتتاح بنوعَي خطأ من نوع واحد: يُبدأ بالبند الآخر، وإن كرر هو أيضًا لم يُعرض ونتيجته void وتأتي الموجَّهة',
       steps, [0, True, 1, True, 'opening.try', ['void']])
o.feed('correct')
expect('5. بند «جرّب أولًا» بنتيجة void لا يتخطى الشرح ولو صح الآخر', [o.stage, o.done], ['guided', False])
o = OpeningRun('1-4-2', ['ف2', 'ف3', 'ف4'], typed=True)
expect('6. افتتاح بالبندين الثابتين: لا بند آخر، فلا يُعرض ونتيجته void', [o.repeated('a'), o.try_out, o.pos], [True, ['void'], 1])
v = EvidenceRun('1-4-2', ['ف2', 'ف3', 'ف4'])
r1, w1 = v.repeated('x'), v.want()
r2 = v.repeated('alt')
v.unavailable() if v.want()['alternate'] == 2 else None
expect('7. دليل الفهم: يُطلب بديل النوع لموضعه، وإن كرر البديل الحقيقة انتهت الجولة بلا حكم',
       [r1, w1['role'], w1['replaces'], r2, v.result], [True, 'evidence.alternate', 'x', True, 'no_alternate'])
gate = GateRun('1-4-2', ['ف2', 'ف3', 'ف4'])
recs = []
gen = drive_steps(gate, lambda s, w: dict(id='g1', fact=[2, 8]), recs, prev=lambda: ('p9', [2, 8]))
item, w = next(gen)
try:
    gen.send(([('confirm', 1)], 2, True))
except StopIteration:
    pass
expect('8. نشاط تقييم بلا علاج: البند يُعرض موسومًا في الطلب وفي سجله بالبند الذي سبقه',
       [gate.repeated('g1'), w.get('fact_just_seen'), recs[0].get('fact_just_seen')], [False, 'p9', 'p9'])
print('النتيجة: نجح %d من %d' % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
