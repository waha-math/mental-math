#!/usr/bin/env python3
"""طلب المساعدة في فحص الاحتفاظ ينهي الجولة بلا حكم (ت3 في مراجعة 04e0168، وهو R16-04).

    python3 tests/test_retention_help.py <ملف الخريطة>

الخلل: RetentionRun كانت لا تحسب البند المنتهي بطلب دعم صحيحًا «ويمضي الفحص». فطلب مساعدة ثم أربع إجابات صحيحة
يصدر retention_result بقيمة 4، وهي تبلغ عتبة 4 من 5.

القرار (الأب، 18 نوفمبر): طلب الدعم ينهي الجولة بلا حكم احتفاظ. يُحفظ الطلب، ويُنقل الطفل إلى المساعدة التعليمية،
ثم تُتاح له جولة لاحقة ببنود بديلة. والإغلاق والاستعادة بعد الطلب مباشرة لا يعيدان الجولة المنتهية.
والمساعدة التعليمية، بقراره في اليوم نفسه (الخيار 1): نشاط تثبيت يقرّه المحرك. يُعرض تدريب المهارة وهي مستوفاة، في
الحصة التعليمية للجلسة (7.1)، ولا تُطلب الجولة اللاحقة قبل اكتماله ولا في يومه.

التوقعات كُتبت من القاعدة قبل التشغيل، وما صُحّح منها بعد رؤية الناتج مذكور عند حالته.

المشهد: الصغير في 1-4-1 مع فحوص الاحتفاظ، بالطفل النموذجي في test_phase0 (يعرف المهارة بعد درسها) حتى يبلغ أول فحص
احتفاظ، ثم يطلب المساعدة في بند منه.
بدائل بنود الاحتفاظ من محتوى الشريحة (الدور deferred_check.alternate). والحالة 5 تحجبها عن المصدر لتُختبر الإحالة إلى
البالغ حين لا بدائل.
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
import persist  # noqa: E402

results = []
SKILL = '1-4-1'


def expect(title, got, want):
    ok = got == want
    results.append(ok)
    print('  %s  %s' % ('نجح' if ok else 'أخفق', title))
    if not ok:
        print('        %r، والمتوقع %r' % (got, want))


def without_alternates(sc):
    """محتوى بلا بدائل لبنود الاحتفاظ: المصدر لا يعيد منها شيئًا."""
    inner = sc.source

    def source(skill, w):
        return None if w.get('role') == 'deferred_check.alternate' else inner(skill, w)
    sc.source = source


KID = [None]                                               # الطفل النموذجي في test_phase0: يعرف المهارة بعد أن يرى درسها


def answer(st, how='c'):
    item, w = st.pending
    evs = [('support', 'requested')] if how == 'h' else KID[0].events(item, w)
    for ev in evs:
        st.event(st.seq, ev)


def to_retention(strip_alternates=False, correct_first=0):
    """حتى أول بند في أول فحص احتفاظ، ثم correct_first إجابات صحيحة فيه."""
    e, sc = g['build']('retention')
    KID[0] = g['Kid']()
    if strip_alternates:
        without_alternates(sc)
    st = g['Stepper'](e, sc)
    st.open(sc.g_run(100))
    while st.pending[1]['activity'] != 'retention':
        answer(st)
    for _ in range(correct_first):
        answer(st)
    return e, sc, st


def rest_of_session(e, st, ses, limit=60):
    """ما يُعرض حتى تُختم الجلسة ses: (النشاط، المعرّف). يتوقف عند أول بند من جلسة تالية. الجلسة تُعطى صريحة: طبقة
    الخطوات تفتح الجلسة التالية عند ختم آخر بند، فقراءة الجلسة الجارية بعد إجابة قد تعطي التالية."""
    out = []
    while st.pending is not None and e.s['current'] == ses and len(out) < limit:
        out.append((st.pending[1]['activity'], st.pending[0]['id']))
        answer(st)
    return out


def sessions(e, st, n):
    """يلعب n جلسات من الجلسة المفتوحة الآن: قائمة لكل جلسة بما عُرض فيها."""
    out = []
    for _ in range(n):
        out.append(rest_of_session(e, st, e.s['current']))
    return out


def kinds(shown):
    """الأنشطة بترتيب عرضها، بلا تكرار متتالٍ."""
    out = []
    for a, _i in shown:
        if not out or out[-1] != a:
            out.append(a)
    return out


def facts(e, ses=None):
    """نتائج الاحتفاظ وما سُجّل على جولاته. ses: ما وقع في هذه الجلسة وحدها."""
    return dict(results=[(r['round'], r['correct'], r['label']) for r in e.s['retention']
                         if ses is None or r['session'] == ses],
                notes=[(n['round'], n['what']) for n in e.s['retention_notes']
                       if n['valid'] and (ses is None or n['session'] == ses)])


def day_of(e, what):
    return [n['day'] for n in e.s['retention_notes'] if n['what'] == what]


print('=== طلب المساعدة في فحص الاحتفاظ، بلغة بايثون')
# 1) حالة المراجع: طلب مساعدة في البند الأول
e, sc, st = to_retention()
first = st.pending[0]['id']
ses = e.s['current']
teach_before = e.s['sessions'][ses]['teach']
answer(st, 'h')
after = rest_of_session(e, st, ses)
expect('1. طلب المساعدة في البند الأول ينهي الجولة: لا نتيجة احتفاظ، والطلب محفوظ بجولته وبنده، وما بقي من بنود الجولة لا يُعرض',
       [facts(e, ses)['results'], facts(e, ses)['notes'][0],
        [n['items'] for n in e.s['retention_notes'] if n['what'] == 'help'],
        [a for a, _i in after if a == 'retention'], [x[1] for x in sc.log if x[1].startswith('retention_')][0]],
       [[], (1, 'help'), [[first]], [], 'retention_help'])
# المهارة مستوفاة ودرسها غير نشط: ما يجيز العرض التثبيت الذي أقرّه المحرك، لا الدرس. والجلسة نفسها، وأول ما يُعرض
practice = [i for a, i in after if a == 'practice']
expect('2. ثم التثبيت في الجلسة نفسها وقبل أي شيء آخر: تدريب المهارة كله، بحدثي بدء واكتمال في المحرك، وحصة الجلسة مستهلكة به، '
       'والمهارة باقية مستوفاة ودرسها لم يُستأنف',
       [kinds(after)[:1], len(practice), all(i.startswith(SKILL + '/practice/') for i in practice),
        facts(e, ses)['notes'], [n['items'] for n in e.s['retention_notes'] if n['what'] == 'consolidated'] == [practice],
        e.s['sessions'][ses]['teach'] - teach_before, e.direct(SKILL), ses in e.s['opened'][SKILL]['taught'],
        [x for x in sc.log if x[1].startswith('carry_')]],
       [['practice'], 6, True, [(1, 'help'), (1, 'consolidating'), (1, 'consolidated')], True, 1, 'met', False, []])
rec = [r for r in sc.records if r['item'] == first][-1]
expect('3. سجل البند يحفظ الطلب: منقطع، بلا إجابة، ونوع الدعم requested',
       [rec['status'], rec['values'], rec['support']], ['interrupted', [], ['requested']])

# 2) بعد إجابتين صحيحتين: لا 2 من 5
e, sc, st = to_retention(correct_first=2)
ses = e.s['current']
answer(st, 'h')
rest_of_session(e, st, ses)
expect('4. طلب المساعدة في البند الثالث بعد إجابتين صحيحتين: لا نتيجة (ليست 2 من 5)',
       [facts(e, ses)['results'], facts(e, ses)['notes'][0]], [[], (1, 'help')])

# 3) الجولة اللاحقة: في يوم لاحق. محتوى بلا بدائل: إحالة إلى البالغ، ولا حلقة
e, sc, st = to_retention(strip_alternates=True)
ses = e.s['current']
answer(st, 'h')
same_day = rest_of_session(e, st, ses)
later = sessions(e, st, 4)
expect('5. الجولة لا تُعاد في يوم الطلب، وتُطلب في اليوم التالي. وبلا بدائل في المحتوى: تُحال إلى البالغ بلا نتيجة ولا إخفاق، '
       'ولا يُعرض بند احتفاظ في أربع جلسات بعدها',
       [[a for a, _i in same_day if a == 'retention'], day_of(e, 'referred')[0] - day_of(e, 'help')[0], facts(e),
        [a for x in later for a, _i in x if a == 'retention'], e.retention_next(SKILL),
        [x[1] for x in sc.log if x[1].startswith('retention_')]],
       [[], 1, dict(results=[], notes=[(1, 'help'), (1, 'consolidating'), (1, 'consolidated'), (1, 'referred')]), [], None,
        ['retention_help', 'retention_no_alternate']])
# بعد الإحالة لا شيء ينتظر الطفل، فالتشغيل الأول انتهى (pending فارغ): قرار البالغ يقع بين فتحين للتطبيق، ويُتابَع
# بتشغيل جديد على الحالة نفسها. كتبتُ الحالة أولًا تتابع المولّد المنتهي فلم يُعرض شيء، وكان ذلك خطأ الأداة
ended = st.pending is None
r = e.apply(dict(id='adult-1', type='retention_release', skill=SKILL, reason='يعيدها البالغ ببنودها'))
r_again = e.apply(dict(id='adult-2', type='retention_release', skill=SKILL, reason='مرة ثانية'))
st = g['Stepper'](e, sc)
st.open(sc.g_run(100))
redo = sessions(e, st, 1)[0]
expect('5ب. بعد الإحالة ينتهي التشغيل بلا بند منتظر. وقرار البالغ يعيد الجولة ببنودها الأصلية، ونتيجتها «أداء مؤجل». وقرار ثانٍ '
       'بلا إحالة يُرفض',
       [ended, r['ok'], r_again.get('code'), [i for a, i in redo if a == 'retention'][:1], facts(e)['results']],
       [True, True, 'not_referred', [first], [(1, 5, 'deferred_performance')]])

# 4) ببدائل متاحة (محتوى الشريحة)
e, sc, st = to_retention()
ses = e.s['current']
answer(st, 'h')
rest_of_session(e, st, ses)
nxt = sessions(e, st, 1)[0]
shown = [i for a, i in nxt if a == 'retention']
original = [i['id'] for i in g['ITEMS'] if i['skill'] == SKILL and i['group'] == 'deferred' and i['role'] == 'deferred_check']
alternate = [i['id'] for i in g['ITEMS'] if i['skill'] == SKILL and i['group'] == 'deferred'
             and i['role'] == 'deferred_check.alternate']
expect('6. ببدائل متاحة: في اليوم التالي تُعرض الجولة أول الجلسة ببنود بديلة خمسة ليس فيها بند من بنود الجولة الأصلية، '
       'ونتيجتها «أداء مؤجل»',
       [kinds(nxt)[:1], len(shown), all(i in alternate for i in shown), [i for i in shown if i in original],
        facts(e)['results'], day_of(e, 'help')[0] + 1 == e.s['retention'][0]['day']],
       [['retention'], 5, True, [], [(1, 5, 'deferred_performance')], True])

# 5) الإغلاق والاستعادة بعد الطلب مباشرة
c = g['SCEN']['retention']


def reopen(st):
    snap = json.loads(json.dumps(st.snapshot()))
    e2, sc2, notes = persist.restore(snap, g['NET'], g['TYPES'], g['ContentSource'](g['ITEMS']), None,
                                     item_seconds=c['secs'], records=[])
    st2 = g['Stepper'](e2, sc2)
    st2.open(sc2.g_run(100))
    return e2, sc2, st2


e, sc, st = to_retention()
ses = e.s['current']
answer(st, 'h')
e2, sc2, st2 = reopen(st)
after2 = rest_of_session(e2, st2, ses)
expect('7. إغلاق بعد الطلب مباشرة ثم استعادة: الجولة المنتهية لا تعود ولا تصدر عنها نتيجة، وما يُعرض بعدها ما يُعرض في المتصل، '
       'والتثبيت يكتمل مرة واحدة',
       [facts(e2, ses), [a for a, _i in after2 if a == 'retention'], after2 == after,
        [k['kind'] for k in sc2.saved if k['kind'] == 'retention']],
       [dict(results=[], notes=[(1, 'help'), (1, 'consolidating'), (1, 'consolidated')]), [], True, []])

# 5ب) الإغلاق في أثناء التثبيت، بعد بندين منه
e, sc, st = to_retention()
ses = e.s['current']
answer(st, 'h')
seen2 = [st.pending[0]['id']]
answer(st)
seen2.append(st.pending[0]['id'])
answer(st)
e2, sc2, st2 = reopen(st)
rest2 = rest_of_session(e2, st2, ses)
expect('7ب. إغلاق بعد بندين من التثبيت ثم استعادة: يُكمَل من بنده الثالث في الجلسة نفسها بلا حدث بدء ثانٍ ولا حصة ثانية، ثم يكتمل',
       [[i for a, i in rest2 if a == 'practice'] == practice[2:], seen2 == practice[:2], facts(e2, ses)['notes'],
        e2.s['sessions'][ses]['teach'] - teach_before],
       [True, True, [(1, 'help'), (1, 'consolidating'), (1, 'consolidated')], 1])

# 6) إبطال جلسة الطلب والتثبيت
e, sc, st = to_retention()
ses = e.s['current']
answer(st, 'h')
rest_of_session(e, st, ses)
e.apply(dict(id='inv', type='invalidate_session', target=ses))
expect('8. إبطال جلسة الطلب: الطلب والتثبيت يبقيان في السجل غير صالحين، ومحاولة الجولة تعود 1 ببنودها الأصلية، ولا تثبيت مستحق',
       [e.s['sessions'][ses]['invalid'], [(n['what'], n['valid']) for n in e.s['retention_notes']],
        e.retention_attempt(SKILL), e.consolidation_owed(), e.retention_next(SKILL) is not None],
       [True, [('help', False), ('consolidating', False), ('consolidated', False)], 1, [], True])

# 7) المحرك وحده: التثبيت لا يُقبل بلا طلب، والجولة لا تُقبل قبله
e, sc, st = to_retention()
ses = e.s['current']
no_help = e.preflight(dict(id='x', type='consolidation_started', session=ses, skill=SKILL)).get('code')
answer(st, 'h')                                             # بعدها بدأ التثبيت في الجلسة نفسها
during = [e.preflight(dict(id='x', type='retention_result', session=ses, skill=SKILL, correct=5)).get('code'),
          e.preflight(dict(id='x', type='consolidation_started', session=ses, skill=SKILL)).get('code'),
          e.may_continue('show', ses, SKILL).get('code'), e.may_continue('consolidate', ses, SKILL)['ok']]
rest_of_session(e, st, ses)
nxt_ses = e.s['current']                                    # الجلسة التالية مفتوحة: السؤال فيها، فجلسة التثبيت خُتمت
done = [e.preflight(dict(id='x', type='consolidation_done', session=nxt_ses, skill=SKILL)).get('code'),
        e.preflight(dict(id='x', type='consolidation_started', session=nxt_ses, skill=SKILL)).get('code'),
        e.may_continue('consolidate', nxt_ses, SKILL).get('code')]
# توقعتُ أولًا already_active لبدء ثانٍ في الجلسة نفسها. الحصة تُفحص قبله، وحصة الجلسة واحدة، فالرفض quota_teach.
# وسألتُ عن الاكتمال الثاني في جلسة خُتمت فكان الرفض no_session. صحّحت التوقعين بعد رؤية الناتج
expect('9. في المحرك: لا تثبيت بلا طلب مساعدة. وفي أثنائه لا تُقبل نتيجة الجولة ولا بدء ثانٍ (الحصة مستهلكة)، وعرض الدرس '
       'مرفوض وعرض التثبيت مقبول. وبعد اكتماله لا اكتمال ثانٍ ولا بدء ولا عرض',
       [no_help, during, done],
       ['no_consolidation', ['consolidation_first', 'quota_teach', 'lesson_idle', True],
        ['no_consolidation', 'no_consolidation', 'no_consolidation']])
print('النتيجة: نجح %d من %d' % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
