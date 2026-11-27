"""حالة المراجع على الشجرة المعطاة: طلب مساعدة في أول بند من فحص الاحتفاظ ثم إجابات صحيحة."""
import json, os, sys
ROOT, MAP = sys.argv[1], sys.argv[2]
sys.path.insert(0, ROOT)
HERE = os.path.join(ROOT, 'tests')
src = open(os.path.join(HERE, 'test_phase0.py'), encoding='utf-8').read()
g = {'__file__': os.path.join(HERE, 'test_phase0.py'), '__name__': 'h'}
sys.argv = [g['__file__'], MAP]
exec(compile(src[:src.index("\nprint('=== ")], 'test_phase0.py', 'exec'), g)
e, sc = g['build']('retention')
kid = g['Kid']()
st = g['Stepper'](e, sc)
st.open(sc.g_run(100))
while st.pending[1]['activity'] != 'retention':
    for ev in kid.events(*st.pending):
        st.event(st.seq, ev)
ses, first = e.s['current'], st.pending[0]['id']
st.event(st.seq, ('support', 'requested'))
shown = []
while st.pending is not None and e.s['current'] == ses:
    shown.append((st.pending[1]['activity'], st.pending[0]['id']))
    for ev in kid.events(*st.pending):
        st.event(st.seq, ev)
print('طلب المساعدة في البند', first, 'في الجلسة', ses)
print('ما عُرض بعده في الجلسة:', [a for a, _ in shown])
print('نتائج الاحتفاظ في المحرك:', [(r['round'], r['correct'], r['of'], r['label'], r['consolidate']) for r in e.s['retention']])
print('ما سُجّل على الجولة غير النتيجة:', [(n['what']) for n in e.s.get('retention_notes', [])])
