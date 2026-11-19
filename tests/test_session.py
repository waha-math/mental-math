#!/usr/bin/env python3
"""جلسة واحدة للواجهة (Scheduler.g_session): تكرارها يساوي g_run.

    python3 tests/test_session.py <ملف الخريطة>

الواجهة تعقد جلسة واحدة عند كل «ابدأ»، وتُغلق بين الجلسات. g_run يعقد الجلسات كلها في مولّد واحد، فلا يصلح لها.
النتائج المتوقعة مكتوبة من القاعدة قبل التشغيل: الحالة الدائمة كاملة (final في test_phase0) تطابق تشغيل g_run
بالطفل نفسه، وعدد الجلسات المعقودة عدد جلساته، والنداء بعد آخر جلسة يعيد False ولا يغيّر شيئًا.
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
from stepper import Stepper  # noqa: E402

SCEN, Kid, build, reopen, play, final, dump = (g[k] for k in ('SCEN', 'Kid', 'build', 'reopen', 'play', 'final', 'dump'))
results = []


def check(title, bad):
    results.append(not bad)
    print('  %s  %s' % ('نجح' if not bad else 'أخفق', title))
    for b in bad[:4]:
        print('        ' + b)


def one(e, sc, kid, cap, stop_at=None):
    """جلسة واحدة. تعيد (هل عُقدت، عدد ما أُجيب، الطبقة). stop_at: يتوقف قبل الطلب بهذا الرقم داخل الجلسة."""
    st = Stepper(e, sc)
    st.open(sc.g_session(cap))
    n = play(st, kid, stop_at)
    return (st.result if st.finished else None), n, st


def case(name, wrong, help, label):
    c = SCEN[name]
    e0, sc0 = build(name)
    s0 = Stepper(e0, sc0)
    s0.open(sc0.g_run(c['sessions']))
    total = play(s0, Kid(wrong, help))
    base = dump(final(e0, sc0))
    bad = []

    # أ) في الذاكرة: جلسة بعد جلسة حتى False
    e, sc = build(name)
    kid, held = Kid(wrong, help), 0
    while True:
        r, _, _ = one(e, sc, kid, c['sessions'])
        if r is not True:
            break
        held += 1
        if sc.cur is not None:
            bad.append('الجلسة %s بقيت مفتوحة بعد انتهاء مولّدها' % sc.cur)
    if r is not False:
        bad.append('النداء الأخير أعاد %r لا False' % (r,))
    if held != sc0.sessions:
        bad.append('عُقدت %d جلسة، وفي g_run %d' % (held, sc0.sessions))
    if dump(final(e, sc)) != base:
        bad.append('أ) الحالة النهائية تخالف g_run')
    before = dump(final(e, sc))
    r2, n2, _ = one(e, sc, kid, c['sessions'])
    if r2 is not False or n2 or dump(final(e, sc)) != before:
        bad.append('نداء ثانٍ بعد النهاية غيّر شيئًا أو عرض بندًا')

    # ب) إغلاق بين كل جلستين: لقطة ثم استعادة ثم الجلسة التالية
    e, sc = build(name)
    kid = Kid(wrong, help)
    while True:
        r, _, st = one(e, sc, kid, c['sessions'])
        if r is not True:
            break
        e, sc, _ = reopen(name, st.snapshot())
    if dump(final(e, sc)) != base:
        bad.append('ب) مع إغلاق بين الجلسات: الحالة النهائية تخالف g_run')

    # ج) إغلاق عند كل طلب بند في المسار كله، ثم g_session تكمل الجلسة نفسها
    diff = []
    for k0 in range(total):
        e, sc = build(name)
        kid, n, k = Kid(wrong, help), 0, k0
        while True:
            st = Stepper(e, sc)
            st.open(sc.g_session(c['sessions']))
            n = play(st, kid, k, n)
            if st.pending is not None:                       # الإغلاق هنا
                cur = sc.cur
                e, sc, _ = reopen(name, st.snapshot())
                if sc.cur != cur:
                    diff.append((k0, 'الجلسة بعد الاستعادة %s وكانت %s' % (sc.cur, cur)))
                k = None
                continue
            if st.result is not True:
                break
        if dump(final(e, sc)) != base:
            diff.append((k0, 'الحالة النهائية'))
    if diff:
        bad.append('ج) %d من %d موضع إغلاق تخالف. أولها: %r' % (len(diff), total, diff[:3]))
    check('%s: %d جلسة و%d طلب بند' % (label, sc0.sessions, total), bad)


print('=== جلسة واحدة للواجهة (g_session)، المرجع')
for name, wrong, help, label in [
        ('young', (), (), 'الصغير في 1-4'),
        ('young', ('1-4-1/evidence/01', '1-4-1/checkA/03', '1-4-1/checkA/05'), ('1-4-2/evidence/01',),
         'الصغير، بأخطاء وطلب تلميح'),
        ('older', (), (), 'الكبيران في 3-5'),
        ('older', ('3-5-1/checkA/01', '3-5-1/checkA/03', '3-5-2/evidence/01'), (), 'الكبيران، بأخطاء'),
        ('retention', (), (), 'الصغير في 1-4-1 مع فحوص الاحتفاظ')]:
    case(name, wrong, help, label)
print('نجحت الاختبارات كلها: %d' % len(results) if all(results) else 'أخفق %d من %d' % (results.count(False), len(results)))
sys.exit(0 if all(results) else 1)
