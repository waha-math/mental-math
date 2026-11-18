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


def pinned(sc, scene=None):
    inner, scene = sc.source, scene or SCENE

    def source(skill, w):                                   # بنود المشهد كما كانت في محتوى 03d2e0d، أيًّا كان المحتوى الآن
        it = inner(skill, w)
        return dict(it, **scene[it['id']]) if it is not None and it['id'] in scene else it
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
                        fact=fact(item), events=evs, just_seen=w.get('fact_just_seen'), last=sc.last))
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
    json.dump([dict(item=x['item'], events=x['events'], last=x['last']) for x in out], open(TAPE, 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))
    print('كُتب الشريط: %d بندًا' % len(out))
tape = json.load(open(TAPE, encoding='utf-8'))
out, err = run(tape)
print('=== المراجعة 22، بلغة بايثون')
expect('1. الشريط يُعاد كله: البنود المعروضة هي بنود الشريط', [err, len(out)], [None, len(tape)])
# R23-02: آخر بند عُرض (last) عند كل بند من الشريط، كما كتبه المرجع في الشريط. يُقارَن في اللغتين، فاختلاف قيمته بينهما
# يظهر عند البند الذي اختلف فيه، ولو لم يغيّر قرارًا
off = [k for k, (x, t) in enumerate(zip(out, tape)) if x['last'] != t['last']]
expect('1ب. آخر بند عُرض عند كل بند يطابق ما في الشريط (%d بندًا، منها %d لها آخر بند)'
       % (len(tape), sum(1 for t in tape if t['last'])), off[:3], [])
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

# R23-01: الاستعادة تختم البند الجاري وتتقدم به، فيجب أن يتحدث معها آخر بند عُرض، بقواعد التعرّض نفسها. البند
# tryfirst/04 (4 و6) يُعرض بعد gate/03 (2 و8)، ثم يُغلق التطبيق والبند جارٍ، وتُستعاد اللقطة. ما يلي يجب أن يكون ما
# يلي في التشغيل المتصل حين يُختم البند بالأحداث نفسها ثم انقطاع
def after_first_try(events, close, today=None):
    e, sc = g['build']('young')
    pinned(sc)
    st = g['Stepper'](e, sc)
    st.open(sc.g_run(20))
    k = 0
    while st.pending[0]['id'] != '1-4-2/tryfirst/04':
        for ev in tape[k]['events']:
            st.event(st.seq, tuple(ev))
        k += 1
    if events is None:
        st.show(st.seq)
    for ev in events or ():
        st.event(st.seq, ev)
    if close:
        e, sc, _notes = g['reopen']('young', st.snapshot(), today=today)
        if today is not None:                                # يوم جديد: الاستعادة تختم الجلسة، فلا «آخر بند» لها
            again = g['persist'].snapshot(e, sc)
            e2, sc2, _n2 = g['reopen']('young', again, today=today)
            return [sc.cur, sc.last, g['persist'].snapshot(e2, sc2) == again]
        pinned(sc)
        st = g['Stepper'](e, sc)
        st.open(sc.g_run(20))
    else:
        st.event(st.seq, ('end',))                           # في التشغيل المتصل ينتهي بند التعليم بـend بعد إجابة مؤكدة
    item, w = st.pending
    return [item['id'][6:], w['reshown'], (sc.last or {}).get('item', '')[6:], (sc.last or {}).get('counts')]


want = ['tryfirst/03', 0, 'tryfirst/04', True]
expect('10. إجابة مؤكدة صحيحة ثم إغلاق قبل end واستعادة: البند التالي وآخر بند عُرض كما لو أُنهي البند بلا إغلاق',
       [after_first_try([('confirm', 4)], True), after_first_try([('confirm', 4)], False)], [want, want])
# لا مقابل متصلًا للحالتين التاليتين: بند التعليم لا ينتهي في التشغيل المتصل بلا إجابة مؤكدة. المتوقع من القاعدة:
# طلب الدعم تعرّض، فآخر بند عُرض هو tryfirst/04 ويُحتسب، والتالي tryfirst/03 (حقيقته غير 4 و6).
expect('11. طلب دعم ثم إغلاق واستعادة: البند يُحتسب تعرّضًا، والتالي البند الآخر',
       after_first_try([('support', 'hint')], True), want)
# العرض وحده انقطاع لم تُقبل قبله إجابة ولم يُقدَّم فيه دعم: الاستثناء الضيق. يُعاد البند نفسه موسومًا، ولا يُحتسب تعرّضًا
expect('12. العرض وحده ثم إغلاق واستعادة: يُعاد البند نفسه موسومًا، وآخر بند عُرض هو لكنه لا يُحتسب تعرّضًا',
       after_first_try(None, True), ['tryfirst/04', 1, 'tryfirst/04', False])

expect('13. إجابة مؤكدة ثم إغلاق واستعادة في يوم جديد: الجلسة تُختم ولا «آخر بند» لها، وحفظ المستعاد واستعادته لا يغيّره',
       after_first_try([('confirm', 4)], True, today=10 ** 6), [None, None, True])

# المسار 319 من متجهات المجدول (try_from_gate=False): بعد البوابة يأتي الافتتاح بالبندين الثابتين. إن كرر أولهما
# حقيقة آخر بند في البوابة فلا بند آخر يحل محله: لا يُعرض، ولا يُتخذ منه قرار اختصار. المشهد: البذرة 1 بالطفل
# العشوائي نفسه، وبند opening/01 يُعطى حقيقة آخر بند في البوابة حين يليها في الجلسة نفسها، ليقع التصادم. الشريط
# tests/r22_tape_fixed.json يُعاد في اللغتين
TAPE2 = os.path.join(HERE, 'r22_tape_fixed.json')


def run_fixed(tape2=None):
    e, sc = g['build']('young')
    sc.try_from_gate = False
    inner = sc.source

    def source(skill, w):
        it, x = inner(skill, w), sc.last
        if (it is not None and it['id'].endswith('/opening/01') and x and x['activity'] == 'gate'
                and x['skill'] == it['skill'] and x['session'] == sc.cur and x['counts']):
            return dict(it, fact=list(x['fact']))
        return it
    sc.source = source
    st = g['Stepper'](e, sc)
    st.open(sc.g_run(20))
    rng, out = random.Random(1), []
    while st.pending is not None:
        item, w = st.pending
        k = len(out)
        if tape2 is None:
            if w['activity'] in DISPLAY:
                evs = [['end']]
            else:
                ans = item['answer'] if rng.random() < 0.6 else item['answer'] + 1
                evs = [['confirm', ans]] + ([] if w['activity'] in ASSESS else [['end']])
        elif k >= len(tape2) or tape2[k]['item'] != item['id']:
            return out, sc, 'البند رقم %d: %s، وفي الشريط %s' % (k, item['id'], tape2[k]['item'] if k < len(tape2) else 'لا شيء')
        else:
            evs = tape2[k]['events']
        out.append(dict(item=item['id'], events=evs))
        for ev in evs:
            st.event(st.seq, tuple(ev))
    return out, sc, None


if WRITE:
    json.dump(run_fixed()[0], open(TAPE2, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
tape2 = json.load(open(TAPE2, encoding='utf-8'))
out2, sc2, err2 = run_fixed(tape2)
ids = [x['item'] for x in out2]
at = ids.index('1-4-2/gate/04')
expect('14. بعد البوابة والبندان الثابتان (المسار 319): الأول يكرر حقيقة آخر بند فيها فلا يُعرض ولا سجل له، ويُعرض الثاني',
       [err2, len(out2) == len(tape2), ids[at:at + 3], len([r for r in sc2.records if r['item'] == '1-4-2/opening/01'])],
       [None, True, ['1-4-2/gate/04', '1-4-2/opening/02', '1-4-2/opening/03'], 0])

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
expect('8. نشاط تقييم ولا موضع يُؤخَّر إليه البند (كل بنوده بالحقيقة نفسها): يُعرض موسومًا في الطلب وفي سجله بالبند الذي سبقه',
       [gate.repeated('g1'), w.get('fact_just_seen'), recs[0].get('fact_just_seen')], [False, 'p9', 'p9'])
print('النتيجة: نجح %d من %d' % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
