#!/usr/bin/env python3
"""اختبارات محرك انتقال الحالات. التشغيل: python3 test_transition_engine.py <ملف الخريطة>

كل اختبار يستدعي Engine.apply مباشرة، بلا مجدول وبلا واجهة. القيم المتوقعة مكتوبة هنا صراحة.
الاختبار 15 يقارن حالات المحرك بمرجع مستقل (oracle) يقرأ سجل الأحداث المقبولة وحده.
الاختبارات 16 إلى 22 تعيد إنتاج الحالات السبع التي وجدها المراجع في الجولة الثامنة.
الاختبارات 23 إلى 30 لما أُضيف بعدها: السؤال قبل العرض، وتوقيت فحص الاستقلال وحصته، وتنبيه التاريخ،
واستئناف الفحص في جلسة لاحقة وتعليقه للمراجعة، ومعالجة التعثّر من البوابة، وحفظ الدليل ببنوده، وفحوص الاحتفاظ.
"""
import copy
from collections import Counter
import itertools
import random
import sys

from transition_engine import Engine, load_network, QUOTA, SEARCH_CAP

NET = load_network(sys.argv[1])
IDS, PRE = NET
KIDS = {s: [c for c in IDS if s in PRE[c]] for s in IDS}
_n = itertools.count(1)
results = []


def check(name, cond):
    results.append(bool(cond))
    print('  %s  %d. %s' % ('نجح' if cond else 'أخفق', len(results), name))


def ev(e, type_, **kw):
    kw.update(id='e%d' % next(_n), type=type_)
    return e.apply(kw)


def start(e, sid, kind, day=None):
    """يوم الجلسة: اليوم التالي لآخر جلسة في حالة المحرك، ما لم يُعطَ."""
    if day is None:
        day = max([x['day'] for x in e.s['sessions'].values()], default=-1) + 1
    return ev(e, 'session_start', session=sid, kind=kind, day=day)


def end(e, sid):
    return ev(e, 'session_end', session=sid)


def refused(e, type_, code, missing=None, **kw):
    """الطلب مرفوض بالرمز المتوقع والمتطلب الناقص، والحالة المحفوظة لم تتغير بحرف."""
    before = e.dump()
    r = ev(e, type_, **kw)
    return (not r['ok']) and r['code'] == code and r.get('missing') == missing and e.dump() == before


# ---------------------------------------------------------------- مرجع مستقل
def oracle(log):
    """يقرأ الأحداث المقبولة وحدها. يجمع الأدلة بجلساتها، يُسقط أدلة الجلسات المبطلة، ثم يحسب
    الحالة المباشرة لكل مهارة والانتظار بانتشار أمامي. لا يستعمل دوال المحرك ولا قائمة أدلته."""
    proofs, dead = [], set()
    for x in log:
        t = x['type']
        if t == 'gate_result' and x['result'] in ('pass', 'fail'):
            proofs.append((x['skill'], x['result'], x['session']))
        elif t == 'lesson_opening_result' and x['outcome'] == 'full_error':
            proofs.append((x['skill'], 'fail', x['session']))
        elif t == 'understanding_proved':
            proofs.append((x['skill'], 'und', x['session']))
        elif t == 'independence_result' and x['result'] == 'pass':
            proofs.append((x['skill'], 'ind', x['session']))
        elif t == 'recheck_result' and x['ok']:
            proofs.append((x['skill'], 'pass', x['session']))
        elif t == 'invalidate_session':
            dead.add(x['target'])
    state = {}
    for skill in IDS:
        st, und, ind = None, False, False
        for s, what, ses in proofs:
            if s != skill or ses in dead:
                continue
            if what == 'pass':
                st = 'exempt'
            elif what == 'fail':
                st, und, ind = 'stumbled', False, False
            elif what == 'und':
                und = True
            else:
                ind = True
            if und and ind:
                st = 'met'
        if st:
            state[skill] = st
    waiting, front = set(), [s for s in state if state[s] == 'stumbled']
    while front:
        x = front.pop()
        for c in KIDS[x]:
            if c not in state and c not in waiting:
                waiting.add(c)
                front.append(c)
    return state, waiting


def differs(e):
    state, waiting = oracle(e.s['log'])
    st, bad = e.derive(), 0
    for s in IDS:
        if (st[s] == 'waiting') != (s in waiting):
            bad += 1
        elif state.get(s) != (st[s] if st[s] in ('exempt', 'stumbled', 'met') else None):
            bad += 1
    return bad


print('=== اختبارات محرك انتقال الحالات (%d مهارة في الإصدار 1)' % len(IDS))

# 1) التعثّر بعد التأجيل ينقل المؤجَّلات إلى الانتظار
e = Engine(NET)
start(e, 'S1', 'search')
ev(e, 'gate_result', session='S1', skill='2-6-3', result='pass')
was = [s for s in IDS if e.derive()[s] == 'deferred']
r = ev(e, 'gate_result', session='S1', skill='1-1-1', result='fail', errors=['ف3', 'ف3'])
st = e.derive()
check('اجتياز 2-6-3 ثم إخفاق بوابة 1-1-1: المؤجَّلات %d، بقي منها مؤجَّلًا %d، و1-1-2 انتقلت من «مؤجَّلة» إلى «تنتظر»'
      % (len(was), sum(1 for s in was if st[s] == 'deferred')),
      len(was) == 17 and not any(st[s] == 'deferred' for s in was) and r['changed']['1-1-2'] == ['deferred', 'waiting']
      and st['2-6-3'] == 'exempt' and e.blockers('1-1-2') == ['1-1-1'] and differs(e) == 0)

# 2) طلب الدعم في البوابة الأولى: لا دليل، ولا انتظار
e = Engine(NET)
start(e, 'S1', 'search')
r = ev(e, 'gate_result', session='S1', skill='1-1-1', result='help')
check('طلب دعم في بوابة 1-1-1: لا دليل كُتب، ولا مهارة تغيّرت حالتها، والمحاولة محفوظة بعلّتها',
      r['ok'] and r['changed'] == {} and e.s['evidence'] == [] and e.s['attempts'][-1]['result'] == 'help')

# 3) طلب الدعم في البوابة بعد فتح الدرس: يمضي الدرس، ولا تعثّر ولا تعليق
e = Engine(NET)
start(e, 'S1', 'start')
ev(e, 'open_lesson', session='S1', skill='1-1-1')
ev(e, 'lesson_opening_result', session='S1', skill='1-1-1', outcome='skip')
end(e, 'S1')
start(e, 'S2', 'follow')
r = ev(e, 'gate_result', session='S2', skill='1-1-1', result='help')
st = e.derive()
check('طلب دعم في بوابة 1-1-1 بعد اختصار درسها: الدرس يمضي كاملًا، لا دليل تعثّر، والمنتظرات %d'
      % sum(1 for v in st.values() if v == 'waiting'),
      r['ok'] and st['1-1-1'] is None and 'waiting' not in st.values() and e.s['evidence'] == []
      and e.s['opened']['1-1-1']['phase'] == 'full' and e.s['sessions']['S2']['teach'] == 1)

# 4) طلب الدعم لا يستثني من الانتظار
e = Engine(NET)
start(e, 'S1', 'search')
ev(e, 'gate_result', session='S1', skill='1-1-2', result='help')
ev(e, 'gate_result', session='S1', skill='1-1-1', result='fail', errors=['ف3', 'ف1'])
st = e.derive()
check('1-1-2 انتهت بوابتها بطلب دعم ثم تعثّر 1-1-1: تصير «تنتظر» ومانعها 1-1-1',
      st['1-1-2'] == 'waiting' and e.blockers('1-1-2') == ['1-1-1'] and differs(e) == 0)

# 5) الرفض الفعلي: استدعاء التنفيذ مباشرة على مهارة ممنوعة
end(e, 'S1')
start(e, 'S2', 'search')
a = refused(e, 'gate_result', 'blocked', '1-1-1', session='S2', skill='1-1-2', result='pass')
end(e, 'S2')
start(e, 'S3', 'start')
b = refused(e, 'short_check_result', 'blocked', '1-1-1', session='S3', skill='1-2-1', ok=True)
c = refused(e, 'open_lesson', 'prerequisite', '1-1-1', session='S3', skill='1-1-2')
d = refused(e, 'gate_result', 'quota_gate', None, session='S3', skill='1-1-1', result='pass')
check('طلبات مباشرة على مهارة ممنوعة: بوابة وتحقق قصير وفتح درس تُرفض بسببها ومتطلبها الناقص، '
      'وبوابة في جلسة البدء تُرفض. لم يُكتب شيء في أي منها', a and b and c and d)

# 6) حصة تعليمية واحدة، وبوابة واحدة بعد البدء
e = Engine(NET)
start(e, 'S1', 'start')
ev(e, 'open_lesson', session='S1', skill='1-1-1')
a = refused(e, 'open_lesson', 'quota_teach', None, session='S1', skill='1-1-2')
ev(e, 'lesson_opening_result', session='S1', skill='1-1-1', outcome='skip')
b = refused(e, 'gate_result', 'quota_gate', None, session='S1', skill='1-1-1', result='pass')
end(e, 'S1')
start(e, 'S2', 'follow')
r = ev(e, 'gate_result', session='S2', skill='1-1-1', result='fail', errors=['ف1', 'ف1'])
c = refused(e, 'open_lesson', 'quota_teach', None, session='S2', skill='1-1-2')
d = refused(e, 'gate_result', 'quota_gate', None, session='S2', skill='3-8-1', result='pass')
check('درسان في جلسة البدء: الثاني يُرفض. إعادة بوابة تُخفق فيمضي درسها وتُستهلك الحصة، ففتح درس آخر '
      'وبوابة ثانية في الجلسة نفسها يُرفضان', a and b and c and d and r['ok']
      and e.s['opened']['1-1-1']['phase'] == 'full')

# 7) قاعدة اختصار الدرس لا تتغير بخيار الإعادة
out = []
for rg in (True, False):
    e = Engine(NET, regate=rg)
    start(e, 'S1', 'search')
    ev(e, 'gate_result', session='S1', skill='1-1-1', result='fail', errors=['ف3', 'ف3'])
    end(e, 'S1')
    start(e, 'S2', 'start')
    ev(e, 'open_lesson', session='S2', skill='1-1-1')
    ev(e, 'lesson_opening_result', session='S2', skill='1-1-1', outcome='skip')
    end(e, 'S2')
    start(e, 'S3', 'follow')
    r = ev(e, 'gate_result', session='S3', skill='1-1-1', result='pass')
    out.append((e.s['opened']['1-1-1']['phase'], list(e.s['queue']) if not r['ok'] else ['done'],
                r['ok'] or r['code']))
check('الاختصار نفسه في الحالتين. مع الإعادة تُقبل البوابة: %s. بلا إعادة تُرفض: %s' % (out[0][2], out[1][2]),
      out == [('skipped', ['done'], True), ('skipped', [], 'regate_not_allowed')])

# 8) دالة الأهلية في سبع حالات مفروضة
s = '3-5-1'
P = sorted(PRE[s], key=IDS.index)                           # 3-2-3 ثم 3-3-2
e = Engine(NET)
got = [e.eligible(s)]
start(e, 'S1', 'start')
for p in P:
    ev(e, 'short_check_result', session='S1', skill=p, ok=True)
got += [e.eligible(s, 'start'), e.eligible(s, 'follow')]
end(e, 'S1')
start(e, 'S2', 'follow')
ev(e, 'gate_result', session='S2', skill=P[0], result='fail', errors=['ف3', 'ف3'])
got.append(e.eligible(s, 'start'))
end(e, 'S2')
ev(e, 'teacher_open', skill=P[0], bypass=PRE[P[0]], reason='لتعليم المتطلب في الاختبار')
start(e, 'S3', 'follow')
ev(e, 'open_lesson', session='S3', skill=P[0])
ev(e, 'lesson_opening_result', session='S3', skill=P[0], outcome='full_error')
ev(e, 'understanding_proved', session='S3', skill=P[0])
end(e, 'S3')
start(e, 'S4', 'follow')
ev(e, 'check_started', session='S4', skill=P[0], check_id='k8', content_version=1)
ev(e, 'independence_result', session='S4', skill=P[0], check_id='k8', result='pass')
ev(e, 'gate_result', session='S4', skill=P[1], result='pass')
got.append(e.eligible(s))
end(e, 'S4')
ev(e, 'invalidate_session', target='S3')
got.append(e.eligible(s))
ev(e, 'teacher_open', skill=s, bypass=P, reason='قرار المعلم في الاختبار')
got.append(e.eligible(s))
check('أهلية فتح درس 3-5-1: %s' % ' '.join('نعم' if g['ok'] else 'لا' for g in got),
      [g['ok'] for g in got] == [False, True, False, False, True, False, True]
      and got[0]['missing'] == P[0] and got[3]['missing'] == P[0] and got[5]['missing'] == P[0])

# 9) الإبطال يستهدف أدلة الجلسة: يبقى الفتح مع دليل مستقل، ويُعلَّق عند زوال المسوّغ الوحيد
e = Engine(NET)
start(e, 'S1', 'search')
ev(e, 'gate_result', session='S1', skill='1-1-1', result='fail', errors=['ف3', 'ف3'])
end(e, 'S1')
start(e, 'S2', 'start')
ev(e, 'open_lesson', session='S2', skill='1-1-1')
ev(e, 'lesson_opening_result', session='S2', skill='1-1-1', outcome='full_error')
ev(e, 'understanding_proved', session='S2', skill='1-1-1')             # دليل فهم أول
end(e, 'S2')
start(e, 'S3', 'follow')
ev(e, 'resume_lesson', session='S3', skill='1-1-1')
ev(e, 'understanding_proved', session='S3', skill='1-1-1')             # دليل فهم ثانٍ في جلسة أخرى
end(e, 'S3')
start(e, 'S4', 'follow')
ev(e, 'check_started', session='S4', skill='1-1-1', check_id='k9', content_version=1)
ev(e, 'independence_result', session='S4', skill='1-1-1', check_id='k9', result='pass')
end(e, 'S4')
start(e, 'S5', 'follow')
ev(e, 'open_lesson', session='S5', skill='1-1-2')                       # يُفتح لأن متطلبه مستوفى
ev(e, 'lesson_opening_result', session='S5', skill='1-1-2', outcome='full_error')
end(e, 'S5')
r1 = ev(e, 'invalidate_session', target='S2')
a = r1['suspended'] == [] and e.derive()['1-1-1'] == 'met'
r2 = ev(e, 'invalidate_session', target='S3')
b = r2['suspended'] == ['1-1-2'] and e.s['suspended']['1-1-2']['missing'] == '1-1-1'
kept = (e.s['opened']['1-1-2']['phase'] == 'full' and len(e.s['evidence']) == 6
        and sum(1 for x in e.s['evidence'] if not x['valid']) == 3
        and e.s['history'][-1]['what'] == 'access_suspended')
start(e, 'S6', 'follow')
c = refused(e, 'understanding_proved', 'suspended', '1-1-1', session='S6', skill='1-1-2')
d = refused(e, 'invalidate_session', 'bad_target', None, target='S2')
check('لفهم 1-1-1 دليلان في جلستين. إبطال الأولى: 1-1-2 تبقى مفتوحة. إبطال الثانية: تُعلَّق ومتطلبها الناقص '
      '1-1-1، وما أُنجز وسجل الأدلة باقيان، والنشاط عليها يُرفض', a and b and kept and c and d and differs(e) == 0)

# 10) المسوّغ قد يكون قرار معلم ساريًا، وإعادة التحقق تستأنف المعلَّق
e = Engine(NET)
start(e, 'S1', 'search')
ev(e, 'gate_result', session='S1', skill='1-1-1', result='pass')
end(e, 'S1')
start(e, 'S2', 'start')
ev(e, 'open_lesson', session='S2', skill='1-1-2')
end(e, 'S2')
e.apply(dict(id='decision-1', type='teacher_open', skill='1-1-2', bypass=['1-1-1'], reason='يعرفها من المدرسة'))
r1 = ev(e, 'invalidate_session', target='S1')
r2 = ev(e, 'teacher_revoke', decision='decision-1')
start(e, 'S3', 'follow')
x = refused(e, 'recheck_result', 'no_recheck', None, session='S3', skill='1-2-1', ok=True)
r3 = ev(e, 'recheck_result', session='S3', skill='1-1-1', ok=True)
check('إبطال جلسة الدليل مع قرار معلم سارٍ: 1-1-2 تبقى مفتوحة. إلغاء القرار: تُعلَّق. إعادة تحقق ناجحة من '
      '1-1-1: تُستأنف', r1['suspended'] == [] and r2['suspended'] == ['1-1-2'] and x and r3['suspended'] == []
      and e.s['history'][-1]['what'] == 'access_resumed')

# 11) قرار المعلم: المتجاوَز كاملًا، والإذن لا ينتقل
e = Engine(NET)
a = refused(e, 'teacher_open', 'bad_decision', '3-2-3', skill='3-5-1', bypass=['3-3-2'], reason='سبب')
b = refused(e, 'teacher_open', 'bad_event', None, skill='3-5-1', bypass=['3-2-3', '3-3-2'], reason='')
ev(e, 'teacher_open', skill='3-5-1', bypass=['3-2-3', '3-3-2'], reason='سبب مكتوب')
dep = e.eligible('3-5-3')
check('قرار فتح 3-5-1 يُرفض إن نقص متطلب متجاوَز أو السبب. وبعد قبوله لا تُفتح 3-5-3 به: ناقصها %s'
      % dep['missing'], a and b and e.eligible('3-5-1')['ok'] and not dep['ok'] and dep['missing'] == '3-5-1')

# 12) ترتيب الجلسات وحصصها
e = Engine(NET, group='young')
a = refused(e, 'session_start', 'session_order', None, session='F0', kind='follow', day=0)
start(e, 'S1', 'search')
b = refused(e, 'session_start', 'session_open', None, session='S2', kind='search', day=1)
ev(e, 'gate_result', session='S1', skill='1-1-1', result='pass')
c = refused(e, 'gate_result', 'quota_gate', None, session='S1', skill='1-1-2', result='pass')
end(e, 'S1')
for i in range(2, SEARCH_CAP + 1):
    start(e, 'S%d' % i, 'search')
    end(e, 'S%d' % i)
d = refused(e, 'session_start', 'session_order', None, session='S9', kind='search', day=9)
start(e, 'B', 'start')
end(e, 'B')
f = refused(e, 'session_start', 'session_order', None, session='B2', kind='start', day=9)
g = refused(e, 'gate_result', 'no_session', None, session='B', skill='1-1-2', result='pass')
check('متابعة قبل البدء، وجلسة فوق جلسة مفتوحة، وبوابة ثانية لابن السادسة في جلسة بحث، وجلسة بحث خامسة، '
      'وجلسة بدء ثانية، ونشاط في جلسة مختومة: كلها تُرفض', a and b and c and d and f and g)

# 13) إعادة إرسال الحدث نفسه لا تكرر أثره
e = Engine(NET)
start(e, 'S1', 'search')
one = dict(id='dup-1', type='gate_result', session='S1', skill='2-6-3', result='pass')
r1 = e.apply(one)
snap = e.dump()
r2 = e.apply(dict(one))
r3 = e.apply(dict(one))
check('الحدث نفسه ثلاث مرات: دليل واحد، وبوابة واحدة في عدّاد الجلسة، والحالة المحفوظة لم تتغير',
      r1['ok'] and r2.get('duplicate') and r3.get('duplicate') and e.dump() == snap
      and len(e.s['evidence']) == 1 and e.s['sessions']['S1']['gate'] == 1 and e.s['gates']['2-6-3'] == 1)

# 14) الاستئناف: الحفظ في منتصف الجلسة، والقراءة، وإعادة تشغيل السجل
e = Engine(NET)
start(e, 'S1', 'start')
ev(e, 'open_lesson', session='S1', skill='1-1-1')
ev(e, 'lesson_opening_result', session='S1', skill='1-1-1', outcome='full_help')
ev(e, 'understanding_proved', session='S1', skill='1-1-1')
end(e, 'S1')
start(e, 'S2', 'follow')
ev(e, 'check_started', session='S2', skill='1-1-1', check_id='k14', content_version=3)
ev(e, 'gate_result', session='S2', skill='3-8-1', result='pass')
text = e.dump()
back = Engine.restore(NET, text, content_versions=[3])
again = Engine.replay(NET, e.s['log'])
a = back.dump() == text and again.dump() == text and back.derive() == e.derive()
b = refused(back, 'gate_result', 'quota_gate', None, session='S2', skill='2-2-1', result='pass')
r = ev(back, 'independence_result', session='S2', skill='1-1-1', check_id='k14', result='pass')
check('حفظ في منتصف جلسة ثم قراءة: الحالة والحصص ومحاولة الفحص المعلَّقة كما كانت، وإعادة تشغيل السجل تعطي '
      'النص نفسه، والمحاولة تُتمّ بعد القراءة', a and b and r['ok'] and back.derive()['1-1-1'] == 'met'
      and back.s['checks']['k14']['state'] == 'closed')


# 15) أحداث عشوائية، صالحة وناقصة ومتعارضة، مقابل المرجع المستقل
def random_event(e, tag, sent):
    cur = e.s['current'] or 'none'
    opened = list(e.s['opened'])
    skill = random.choice(opened) if opened and random.random() < 0.5 else random.choice(
        IDS[:20] if random.random() < 0.7 else IDS)
    t = random.choice(['gate_result'] * 5 + ['short_check_result'] * 2 + ['open_lesson'] * 4
                      + ['lesson_opening_result'] * 3 + ['understanding_proved'] * 3 + ['resume_lesson'] * 2
                      + ['check_started'] * 2 + ['independence_result'] * 3 + ['session_start'] * 3
                      + ['session_end'] * 2 + ['teacher_open', 'teacher_revoke', 'teacher_defer',
                                               'recheck_result', 'invalidate_session', 'check_abandoned',
                                               'date_confirmed', 'check_resumed', 'check_held'])
    x = dict(id=tag, type=t)
    if t == 'session_start':
        last = max([v['day'] for v in e.s['sessions'].values()], default=0)
        x.update(session='S' + tag, kind=random.choice(['search', 'start', 'follow']),
                 day=max(0, last + random.choice([0, 1, 1, 1, 2, 2, 40, -2])))
    elif t == 'session_end':
        x.update(session=cur)
    elif t == 'gate_result':
        x.update(session=cur, skill=skill, result=random.choice(['pass', 'pass', 'fail', 'help', 'interrupted']),
                 errors=['ف3', 'ف1'])
    elif t in ('short_check_result', 'recheck_result'):
        x.update(session=cur, skill=skill, ok=random.random() < 0.7)
    elif t in ('open_lesson', 'resume_lesson', 'understanding_proved'):
        x.update(session=cur, skill=skill)
    elif t == 'lesson_opening_result':
        x.update(session=cur, skill=skill, outcome=random.choice(['skip', 'full_error', 'full_help']))
    elif t == 'check_started':
        x.update(session=cur, skill=skill, check_id='c' + tag, content_version=1)
    elif t == 'independence_result':
        cid = random.choice(list(e.s['checks'])) if e.s['checks'] else 'none'
        own = e.s['checks'][cid]['skill'] if cid != 'none' and random.random() < 0.8 else skill
        x.update(session=cur, skill=own, check_id=cid, result=random.choice(['pass', 'pass', 'fail', 'help']))
    elif t in ('check_resumed', 'check_held'):
        cid = random.choice(list(e.s['checks'])) if e.s['checks'] else 'none'
        own = e.s['checks'][cid]['skill'] if cid != 'none' and random.random() < 0.8 else skill
        x.update(session=cur, skill=own, check_id=cid)
        if t == 'check_held':
            x.update(reason=random.choice(['interruptions', 'no_alternate', 'no_items']))
    elif t == 'check_abandoned':
        x.update(check_id=random.choice(list(e.s['checks'])) if e.s['checks'] else 'none', reason='اختبار')
    elif t == 'teacher_open':
        st = e.derive()
        x.update(skill=skill, bypass=[p for p in PRE[skill] if st[p] not in ('exempt', 'met')], reason='اختبار')
    elif t == 'teacher_defer':
        x.update(skills=[skill], reason='اختبار')
    elif t == 'teacher_revoke':
        ds = [d['id'] for d in e.s['decisions']]
        x.update(decision=random.choice(ds) if ds else 'none')
    else:
        x.update(target=random.choice(e.s['order']) if e.s['order'] else 'none')
    return x


def random_check_event(e, tag):
    """مسار موجَّه نحو الفحص: جلسة جديدة، استئناف درس مفتوح، ثبوت فهم، بدء فحص، نتيجته. ليبلغ الاختبار
    العشوائي شروط التوقيت والحصة كثيرًا، لا نادرًا. يبقى فيه ما يُرفض."""
    cur = e.s['current']
    x = dict(id=tag)
    if cur is None:
        last = max([v['day'] for v in e.s['sessions'].values()], default=0)
        kinds = [v['kind'] for v in e.s['sessions'].values()]
        kind = 'follow' if 'start' in kinds else random.choice(['search', 'start', 'start'])
        x.update(type='session_start', session='S' + tag, kind=kind,
                 day=max(0, last + random.choice([0, 1, 1, 1, 2, 2, 40, -2])))
        return x
    if e.s['sessions'][cur]['clock'] and random.random() < 0.5:
        x.update(type='date_confirmed', target=cur)
        return x
    opened = list(e.s['opened'])
    if not opened or random.random() < 0.12:
        x.update(type='session_end', session=cur)
        return x
    skill = random.choice(opened)
    pend = [k for k, c in e.s['checks'].items() if c['skill'] == skill and c['state'] in ('pending', 'held')]
    r = random.random()
    if pend and e.s['checks'][pend[0]]['state'] == 'held' and r < 0.5:
        x.update(type='check_abandoned', check_id=pend[0], reason='اختبار')
    elif pend and e.s['checks'][pend[0]]['active'] != cur and r < 0.5:
        x.update(type='check_resumed', session=cur, skill=skill, check_id=pend[0])
    elif pend and r < 0.08:
        x.update(type='check_held', session=cur, skill=skill, check_id=pend[0],
                 reason=random.choice(['interruptions', 'no_alternate', 'no_items']))
    elif pend and r < 0.6:
        x.update(type='independence_result', session=cur, skill=skill, check_id=pend[0],
                 result=random.choice(['pass', 'fail', 'fail', 'help']))
    elif r < 0.3:
        x.update(type='resume_lesson', session=cur, skill=skill)
    elif r < 0.55:
        x.update(type='understanding_proved', session=cur, skill=skill)
    elif r < 0.9:
        x.update(type='check_started', session=cur, skill=skill, check_id='c' + tag, content_version=1)
    else:
        x.update(type='session_end', session=cur)
    return x


random.seed(11)
bad = dict(state=0, rejected_wrote=0, malformed_in=0, conflict_in=0, quota=0, gates=0, replay=0)
accepted = rejected = 0
kinds = Counter()
for run in range(60):
    e = Engine(NET, group=random.choice(['older', 'young']), regate=random.random() < 0.7)
    sent = []
    for step in range(400):
        x = random_event(e, 'r%d-%d' % (run, step), sent) if random.random() < 0.5 else \
            random_check_event(e, 'r%d-%d' % (run, step))
        kind = random.random()
        if kind < 0.05 and len(x) > 2:                      # حدث ناقص أو بقيمة غير مسموحة
            f = random.choice([k for k in x if k not in ('id', 'type')])
            if random.random() < 0.5:
                del x[f]
            else:
                x[f] = random.choice([None, 7, 'banana', [1], {}]) if f != 'reason' else 5
        elif kind < 0.10 and sent:                          # إعادة إرسال، بالمحتوى نفسه أو بغيره
            x = copy.deepcopy(random.choice(sent))
            if random.random() < 0.5:
                x['note'] = 'محتوى آخر'
        before = e.dump()
        r = e.apply(x)
        if r['ok'] and not r.get('duplicate'):
            accepted += 1
            kinds[x['type']] += 1
            sent.append(copy.deepcopy(x))
            bad['state'] += differs(e)
        else:
            rejected += 1
            bad['rejected_wrote'] += int(e.dump() != before)
    for ses in e.s['sessions'].values():
        q = QUOTA[ses['kind']]
        g = q['gate'][e.s['group']] if isinstance(q['gate'], dict) else q['gate']
        bad['quota'] += int(ses['gate'] > g or ses['short'] > q['short'] or ses['teach'] > q['teach'])
    bad['gates'] += sum(1 for s in IDS if e.valid_gates(s) > 2)
    bad['replay'] += int(Engine.replay(NET, e.s['log'], e.s['group'], e.s['regate']).dump() != e.dump())
    for x in e.s['log']:                                    # لا حدث ناقص ولا متعارض دخل السجل
        bad['malformed_in'] += int(e._schema(x) is not None)
    bad['conflict_in'] += len(e.s['log']) - len({x['id'] for x in e.s['log']})
check('60 تشغيلًا عشوائيًا: %d حدثًا مقبولًا (منها %d بدء فحص و%d استئناف فحص و%d تعليق فحص و%d نتيجة فحص و%d '
      'تأكيد تاريخ) و%d مرفوضًا أو مكررًا. حالة تخالف المرجع %d، مرفوض كتب شيئًا %d، '
      'ناقص دخل السجل %d، معرّف مكرر في السجل %d، جلسة تجاوزت حصتها %d، مهارة ببوابات أكثر من 2 في دورتها %d، '
      'إعادة تشغيل السجل تخالف الحالة %d' % (accepted, kinds['check_started'], kinds['check_resumed'],
                                           kinds['check_held'], kinds['independence_result'],
                                           kinds['date_confirmed'], rejected, bad['state'], bad['rejected_wrote'],
                                           bad['malformed_in'], bad['conflict_in'], bad['quota'], bad['gates'],
                                           bad['replay']),
      sum(bad.values()) == 0 and accepted > 1000 and rejected > 1000 and kinds['check_started'] > 50
      and kinds['independence_result'] > 50 and kinds['date_confirmed'] > 20 and kinds['check_resumed'] > 20
      and kinds['check_held'] > 8)

# 16) المراجعة الثامنة، 1: حدث ناقص أو بقيمة غير مسموحة لا يغيّر شيئًا، والتطبيق ذرّي عند الاستثناء
e = Engine(NET)
start(e, 'S1', 'search')
a = refused(e, 'gate_result', 'bad_event', None, session='S1', skill='2-6-3')
b = refused(e, 'gate_result', 'bad_event', None, session='S1', skill='2-6-3', result='banana')
c = refused(e, 'short_check_result', 'bad_event', None, session='S1', skill='2-6-3', ok='yes')
d = refused(e, 'gate_result', 'bad_event', None, session='S1', skill='2-6-3', result='pass', extra=1)
f = refused(e, 'no_such_event', 'bad_event', None, session='S1')
seq0 = e.s['seq']
real = e.do_gate_result


def broken(x):
    real(x)                                                 # يكتب الدليل والعدّاد، ثم يتعطل
    raise RuntimeError('عطل مفتعل')


e.do_gate_result = broken
g = refused(e, 'gate_result', 'internal_error', None, session='S1', skill='2-6-3', result='pass')
del e.do_gate_result
r = ev(e, 'gate_result', session='S1', skill='2-6-3', result='pass')
check('بوابة بلا حقل النتيجة، وبنتيجة «banana»، وحقل بنوع خاطئ، وحقل زائد، وحدث مجهول: تُرفض قبل أي تغيير. '
      'واستثناء في منتصف التنفيذ يعيد الحالة كما كانت، ثم يُقبل الحدث السليم',
      a and b and c and d and f and g and e.s['seq'] == seq0 + 1 and r['ok'] and len(e.s['evidence']) == 1)

# 17) المراجعة الثامنة، 2: نتيجة الفحص لمحاولة بدأت فعلًا، حالتها تسمح، وإصدارها متاح
e = Engine(NET, versions=[3])
start(e, 'S1', 'start')
ev(e, 'open_lesson', session='S1', skill='1-1-1')
ev(e, 'lesson_opening_result', session='S1', skill='1-1-1', outcome='full_help')
ev(e, 'understanding_proved', session='S1', skill='1-1-1')
end(e, 'S1')
start(e, 'S2', 'follow')
a = refused(e, 'independence_result', 'no_check', None, session='S2', skill='1-1-1', check_id='k1', result='pass')
b = refused(e, 'check_started', 'version_unavailable', None, session='S2', skill='1-1-1', check_id='k1',
            content_version=9)
ev(e, 'check_started', session='S2', skill='1-1-1', check_id='k1', content_version=3)
c = refused(e, 'check_started', 'check_pending', None, session='S2', skill='1-1-1', check_id='k2', content_version=3)
c = c and refused(e, 'independence_result', 'no_check', None, session='S2', skill='1-1-1', check_id='k-other',
                  result='pass')
old = Engine.restore(NET, e.dump(), content_versions=[1])
d = (old.s['checks']['k1']['state'] == 'needs_restart'
     and refused(old, 'independence_result', 'check_state', None, session='S2', skill='1-1-1', check_id='k1',
                 result='pass') and old.derive()['1-1-1'] is None
     and refused(old, 'check_started', 'check_pending', None, session='S2', skill='1-1-1', check_id='k3',
                 content_version=1))
ev(old, 'check_abandoned', check_id='k1', reason='إصدار التعريفات غير متاح بعد الاستعادة')
end(old, 'S2')
start(old, 'S3', 'follow')
ev(old, 'check_started', session='S3', skill='1-1-1', check_id='k3', content_version=1)
r = ev(old, 'independence_result', session='S3', skill='1-1-1', check_id='k3', result='pass')
f = refused(old, 'independence_result', 'check_state', None, session='S3', skill='1-1-1', check_id='k3',
            result='pass')
check('نجاح بلا محاولة مبدوءة يُرفض. محاولة بإصدار مفقود بعد الاستعادة تحتاج إعادة بدء ونتيجتها تُرفض، ولا تُبدأ '
      'أخرى قبل تركها صراحة. بعد الترك والبدء الجديد تُقبل النتيجة مرة واحدة',
      a and b and c and d and r['ok'] and f and old.derive()['1-1-1'] == 'met'
      and [old.s['checks'][k]['state'] for k in ('k1', 'k3')] == ['abandoned', 'closed'])

# 18) المراجعة الثامنة، 3: تعديل المدخل بعد قبوله، أو النتيجة بعد استلامها، لا يغيّر المحرك
e = Engine(NET)
start(e, 'S1', 'search')
mine = dict(id='m1', type='gate_result', session='S1', skill='2-6-3', result='pass', errors=['ف3'])
r = e.apply(mine)
snap = e.dump()
mine['result'] = 'fail'                                     # تعديل كائن المدخل
mine['errors'].append('ف1')
r['changed']['2-6-3'] = ['غير', 'صحيح']                     # تعديل النتيجة المعادة
r['changed'].clear()
again = e.apply(dict(id='m1', type='gate_result', session='S1', skill='2-6-3', result='pass', errors=['ف3']))
check('عُدّل كائن الحدث بعد قبوله، وعُدّلت النتيجة المعادة: السجل والنتيجة المحفوظة لم يتغيرا، وإعادة تشغيل '
      'السجل تعطي الحالة نفسها', e.dump() == snap and e.s['log'][-1]['result'] == 'pass'
      and e.s['log'][-1]['errors'] == ['ف3'] and again.get('duplicate') and again['changed'].get('2-6-3')
      == [None, 'exempt'] and Engine.replay(NET, e.s['log']).dump() == snap)

# 19) المراجعة الثامنة، 4: فهم سبق آخر تعثّر لا يفي بشرط الفحص
e = Engine(NET)
start(e, 'S1', 'start')
ev(e, 'open_lesson', session='S1', skill='1-1-1')
ev(e, 'understanding_proved', session='S1', skill='1-1-1')
ev(e, 'lesson_opening_result', session='S1', skill='1-1-1', outcome='full_error')
a = refused(e, 'check_started', 'understanding_first', None, session='S1', skill='1-1-1', check_id='k1',
            content_version=1)
b = e.progress('1-1-1') == ('stumbled', False, False) and len(e.valid_evidence('1-1-1', 'understood')) == 1
ev(e, 'understanding_proved', session='S1', skill='1-1-1')
end(e, 'S1')
start(e, 'S2', 'follow')
r = ev(e, 'check_started', session='S2', skill='1-1-1', check_id='k1', content_version=1)
check('فهم ثم تعثّر في بنود الافتتاح: بدء الفحص يُرفض والدليل القديم باقٍ في السجل. بعد دليل فهم جديد يُقبل في يوم لاحق',
      a and b and r['ok'])

# 20) المراجعة الثامنة، 5: الدرس الذي ينتظر حصة، والدرس غير النشط، لا يقبلان نشاطًا قبل استئناف صريح
e = Engine(NET)
start(e, 'S1', 'start')
ev(e, 'open_lesson', session='S1', skill='1-1-1')
ev(e, 'lesson_opening_result', session='S1', skill='1-1-1', outcome='skip')
end(e, 'S1')
start(e, 'S2', 'follow')
ev(e, 'gate_result', session='S2', skill='1-1-1', result='pass')
ev(e, 'open_lesson', session='S2', skill='1-1-2')
ev(e, 'lesson_opening_result', session='S2', skill='1-1-2', outcome='skip')
end(e, 'S2')
ev(e, 'teacher_open', skill='3-8-1', bypass=PRE['3-8-1'], reason='درس آخر للاختبار')
start(e, 'S3', 'follow')
ev(e, 'open_lesson', session='S3', skill='3-8-1')                       # استُهلكت حصة الجلسة
ev(e, 'lesson_opening_result', session='S3', skill='3-8-1', outcome='full_help')
ev(e, 'gate_result', session='S3', skill='1-1-2', result='fail', errors=['ف1', 'ف1'])
a = e.s['opened']['1-1-2']['phase'] == 'due' and refused(e, 'understanding_proved', 'lesson_idle', None,
                                                         session='S3', skill='1-1-2')
end(e, 'S3')
start(e, 'S4', 'follow')
b = refused(e, 'understanding_proved', 'lesson_idle', None, session='S4', skill='1-1-2')
c = refused(e, 'understanding_proved', 'lesson_idle', None, session='S4', skill='3-8-1')
r = ev(e, 'resume_lesson', session='S4', skill='1-1-2')
d = refused(e, 'resume_lesson', 'quota_teach', None, session='S4', skill='3-8-1')
u = ev(e, 'understanding_proved', session='S4', skill='1-1-2')
check('بوابة تُخفق والحصة مستهلكة: الدرس «ينتظر حصة» ويرفض ثبوت الفهم في الجلسة نفسها وفي التالية. الاستئناف '
      'الصريح يستهلك حصة الجلسة، فيُقبل النشاط، ويُرفض استئناف درس ثانٍ فيها',
      a and b and c and r['ok'] and d and u['ok'] and e.s['opened']['1-1-2']['phase'] == 'full'
      and e.s['sessions']['S4']['teach'] == 1)


# 21) المراجعة الثامنة، 6: بعد إبطال أدلة أنهت دورة التحقق يبقى طريق لإعادة بنائها بلا درس
def cycle(last):
    e = Engine(NET)
    start(e, 'S1', 'search')
    ev(e, 'gate_result', session='S1', skill='1-1-1', result='fail', errors=['ف3', 'ف3'])
    end(e, 'S1')
    start(e, 'S2', 'start')
    ev(e, 'open_lesson', session='S2', skill='1-1-1')
    ev(e, 'lesson_opening_result', session='S2', skill='1-1-1', outcome='skip')
    end(e, 'S2')
    start(e, 'S3', 'follow')
    ev(e, 'gate_result', session='S3', skill='1-1-1', result=last, errors=['ف3', 'ف3'])
    end(e, 'S3')
    return e


e = cycle('fail')
start(e, 'S4', 'follow')
a = refused(e, 'gate_result', 'gate_limit', None, session='S4', skill='1-1-1', result='pass')
e = cycle('pass')
ev(e, 'invalidate_session', target='S1')
ev(e, 'invalidate_session', target='S3')
start(e, 'S4', 'follow')
b = e.derive()['1-1-1'] is None and e.valid_gates('1-1-1') == 0 and e.s['gates']['1-1-1'] == 2
r1 = ev(e, 'recheck_result', session='S4', skill='1-1-1', ok=True)
c = r1['ok'] and e.derive()['1-1-1'] == 'exempt' and e.s['opened']['1-1-1']['phase'] == 'skipped'
e = cycle('pass')
ev(e, 'invalidate_session', target='S1')
ev(e, 'invalidate_session', target='S3')
start(e, 'S4', 'follow')
r2 = ev(e, 'gate_result', session='S4', skill='1-1-1', result='pass')
d = r2['ok'] and e.derive()['1-1-1'] == 'exempt' and e.valid_gates('1-1-1') == 1 and e.s['gates']['1-1-1'] == 3 \
    and len([x for x in e.s['attempts'] if x['what'] == 'gate']) == 3
check('بوابتان بلا إبطال: الثالثة تُرفض. بعد إبطال جلستي البوابتين: المهارة بلا دليل، والتاريخ فيه البوابتان، '
      'وتُقبل إعادة التحقق فتعود مجتازة بلا درس، وتُقبل كذلك بوابة جديدة في الدورة الجديدة', a and b and c and d)

# 22) المراجعة الثامنة، 7: المعرّف نفسه بمحتوى مختلف يُرفض
e = Engine(NET)
start(e, 'S1', 'search')
one = dict(id='same', type='gate_result', session='S1', skill='2-6-3', result='pass')
e.apply(one)
snap = e.dump()
r_same = e.apply(dict(one))
r_diff = e.apply(dict(one, result='fail'))
back = Engine.restore(NET, snap)
r_back = back.apply(dict(one, skill='1-1-1'))
check('المعرّف نفسه بالمحتوى نفسه: إعادة إرسال بلا أثر. وبمحتوى مختلف: event_id_conflict والحالة كما هي، '
      'وكذلك بعد الاستعادة', r_same.get('duplicate') and not r_diff['ok'] and r_diff['code'] == 'event_id_conflict'
      and e.dump() == snap and not r_back['ok'] and r_back['code'] == 'event_id_conflict' and back.dump() == snap)

# 23) السؤال قبل العرض لا يكتب شيئًا، وحكمه حكم الإرسال نفسه
random.seed(23)
bad = Counter()
asked = 0
for run in range(30):
    e = Engine(NET, group=random.choice(['older', 'young']), regate=random.random() < 0.7)
    for step in range(300):
        tag = 'p%d-%d' % (run, step)
        x = random_event(e, tag, []) if random.random() < 0.8 else random_check_event(e, tag)
        before = e.dump()
        v = e.preflight(copy.deepcopy(x))
        bad['كتب شيئًا'] += int(e.dump() != before)
        r = e.apply(x)
        asked += 1
        bad['حكم يخالف الإرسال'] += int(v['ok'] != r['ok'] or v.get('code') != r.get('code')
                                         or v.get('missing') != r.get('missing'))
check('%d سؤالًا قبل الإرسال: سؤال كتب شيئًا %d، وحكم يخالف حكم الإرسال %d' % (asked, bad['كتب شيئًا'],
                                                                         bad['حكم يخالف الإرسال']),
      asked == 9000 and sum(bad.values()) == 0)

# 24) فحص الاستقلال: يوم بعد يوم الدرس، والإعادة بعد يوم وجلسة تدريب، والفحص يستهلك حصة التعليم
e = Engine(NET)
start(e, 'S1', 'start')
ev(e, 'open_lesson', session='S1', skill='1-1-1')
ev(e, 'lesson_opening_result', session='S1', skill='1-1-1', outcome='full_help')
ev(e, 'understanding_proved', session='S1', skill='1-1-1')
a = refused(e, 'check_started', 'check_same_day', None, session='S1', skill='1-1-1', check_id='k1', content_version=1)
end(e, 'S1')
start(e, 'S2', 'follow')
ev(e, 'check_started', session='S2', skill='1-1-1', check_id='k1', content_version=1)
b = refused(e, 'resume_lesson', 'quota_teach', None, session='S2', skill='1-1-1')
ev(e, 'independence_result', session='S2', skill='1-1-1', check_id='k1', result='fail')
c = refused(e, 'check_started', 'check_same_day', None, session='S2', skill='1-1-1', check_id='k2', content_version=1)
end(e, 'S2')
start(e, 'S3', 'follow')
d = refused(e, 'check_started', 'check_needs_practice', None, session='S3', skill='1-1-1', check_id='k2',
            content_version=1)
ev(e, 'resume_lesson', session='S3', skill='1-1-1')                     # جلسة تدريب
end(e, 'S3')
start(e, 'S4', 'follow')
ev(e, 'check_started', session='S4', skill='1-1-1', check_id='k2', content_version=1)
ev(e, 'independence_result', session='S4', skill='1-1-1', check_id='k2', result='help')
end(e, 'S4')
start(e, 'S5', 'follow', day=e.s['sessions']['S4']['day'])           # اليوم نفسه
g = refused(e, 'check_started', 'check_same_day', None, session='S5', skill='1-1-1', check_id='k3', content_version=1)
end(e, 'S5')
start(e, 'S6', 'follow')
ev(e, 'resume_lesson', session='S6', skill='1-1-1')
h = refused(e, 'check_started', 'quota_teach', None, session='S6', skill='1-1-1', check_id='k3', content_version=1)
end(e, 'S6')
start(e, 'S7', 'follow')
r = ev(e, 'check_started', session='S7', skill='1-1-1', check_id='k3', content_version=1)
ev(e, 'independence_result', session='S7', skill='1-1-1', check_id='k3', result='pass')
k = refused(e, 'check_started', 'already_satisfied', None, session='S7', skill='1-1-1', check_id='k4',
            content_version=1)
check('فحص في يوم الدرس يُرفض. بعد الإخفاق: في اليوم نفسه يُرفض، وفي يوم لاحق بلا جلسة تدريب يُرفض، وبعدها يُقبل. '
      'بعد طلب الدعم: يوم لاحق يكفي. والفحص يستهلك حصة التعليم في الاتجاهين، ولا يُبدأ لمهارة مستوفاة',
      a and b and c and d and g and h and r['ok'] and k and e.derive()['1-1-1'] == 'met')

# 25) تنبيه التاريخ (9.1): جلسة قبل آخر يوم أو بعده بأكثر من 30 يومًا تُحفظ بتنبيه، ولا يُقبل فيها ما يعتمد على التاريخ
e = Engine(NET)
start(e, 'S1', 'start', day=10)
ev(e, 'open_lesson', session='S1', skill='1-1-1')
ev(e, 'lesson_opening_result', session='S1', skill='1-1-1', outcome='full_help')
ev(e, 'understanding_proved', session='S1', skill='1-1-1')
end(e, 'S1')
start(e, 'S2', 'follow', day=50)
a = e.s['sessions']['S2']['clock'] and refused(e, 'check_started', 'date_unconfirmed', None, session='S2',
                                               skill='1-1-1', check_id='k1', content_version=1)
b = ev(e, 'gate_result', session='S2', skill='3-8-1', result='pass')['ok']     # ما لا يعتمد على التاريخ يُقبل
c = refused(e, 'date_confirmed', 'not_flagged', None, target='S1')
ev(e, 'date_confirmed', target='S2')
r = ev(e, 'check_started', session='S2', skill='1-1-1', check_id='k1', content_version=1)
end(e, 'S2')
start(e, 'S3', 'follow', day=49)
d = e.s['sessions']['S3']['clock'] and [h['what'] for h in e.s['history']].count('clock_flag') == 2
f = refused(e, 'session_start', 'bad_event', None, session='S4', kind='follow', day=-1)
check('جلسة بعد آخر يوم بـ 40 يومًا: تُفتح بتنبيه، ويُرفض فيها الفحص ويُقبل غيره، وبعد تأكيد الوالد يُقبل. جلسة '
      'يومها قبل آخر يوم تُفتح بتنبيه أيضًا. ويوم سالب يُرفض', a and b and c and r['ok'] and d and f)

# 26) فحص لم تمتلئ خاناته في جلسته: نتيجته بعد استئناف صريح يستهلك حصة الجلسة اللاحقة (7.1). والمعلَّق للمراجعة
#     لا يُستأنف ولا تُقبل نتيجته، ولا تُبدأ محاولة أخرى، حتى يتركه المعلم (3.6)
e = Engine(NET)
start(e, 'S1', 'start', day=1)
ev(e, 'open_lesson', session='S1', skill='1-1-1')
ev(e, 'lesson_opening_result', session='S1', skill='1-1-1', outcome='full_help')
ev(e, 'understanding_proved', session='S1', skill='1-1-1')
end(e, 'S1')
start(e, 'S2', 'follow', day=2)
ev(e, 'check_started', session='S2', skill='1-1-1', check_id='k1', content_version=1)
end(e, 'S2')                                                   # انتهى وقت الجلسة قبل أن تمتلئ الخانات
start(e, 'S3', 'follow', day=3)
a = (refused(e, 'independence_result', 'check_idle', None, session='S3', skill='1-1-1', check_id='k1', result='pass')
     and refused(e, 'check_held', 'check_idle', None, session='S3', skill='1-1-1', check_id='k1',
                 reason='interruptions'))
r1 = ev(e, 'check_resumed', session='S3', skill='1-1-1', check_id='k1')
b = (refused(e, 'check_resumed', 'already_active', None, session='S3', skill='1-1-1', check_id='k1')
     and refused(e, 'resume_lesson', 'quota_teach', None, session='S3', skill='1-1-1'))
r2 = ev(e, 'independence_result', session='S3', skill='1-1-1', check_id='k1', result='pass')
end(e, 'S3')
start(e, 'S4', 'follow', day=4)
ev(e, 'open_lesson', session='S4', skill='1-1-2')
ev(e, 'lesson_opening_result', session='S4', skill='1-1-2', outcome='full_help')
ev(e, 'understanding_proved', session='S4', skill='1-1-2')
end(e, 'S4')
start(e, 'S5', 'follow', day=5)
ev(e, 'check_started', session='S5', skill='1-1-2', check_id='k2', content_version=1)
r3 = ev(e, 'check_held', session='S5', skill='1-1-2', check_id='k2', reason='no_alternate')
c = (refused(e, 'independence_result', 'check_state', None, session='S5', skill='1-1-2', check_id='k2', result='pass')
     and refused(e, 'check_held', 'check_state', None, session='S5', skill='1-1-2', check_id='k2',
                 reason='no_items'))
end(e, 'S5')
start(e, 'S6', 'follow', day=6)
d = (refused(e, 'check_resumed', 'check_state', None, session='S6', skill='1-1-2', check_id='k2')
     and refused(e, 'check_started', 'check_pending', None, session='S6', skill='1-1-2', check_id='k3',
                 content_version=1))
back = Engine.restore(NET, e.dump(), content_versions=[1])
f = back.s['checks']['k2']['state'] == 'held' and back.s['checks']['k2']['hold_reason'] == 'no_alternate'
ev(e, 'check_abandoned', check_id='k2', reason='المعلم راجع الانقطاعات وترك المحاولة')
r4 = ev(e, 'check_started', session='S6', skill='1-1-2', check_id='k3', content_version=1)
r5 = ev(e, 'independence_result', session='S6', skill='1-1-2', check_id='k3', result='pass')
st = e.derive()
check('فحص 1-1-1 بدأ ولم تمتلئ خاناته: في الجلسة التالية تُرفض نتيجته وتعليقه قبل استئنافه، والاستئناف يستهلك '
      'حصتها فيُرفض استئناف الدرس، ثم تُقبل النتيجة. فحص 1-1-2 عُلّق للمراجعة: تُرفض نتيجته واستئنافه ومحاولة '
      'جديدة، ويبقى معلَّقًا بعد الحفظ والقراءة، وبعد ترك المعلم تُبدأ محاولة وتُجتاز',
      a and r1['ok'] and b and r2['ok'] and r3['ok'] and c and d and f and r4['ok'] and r5['ok']
      and (st['1-1-1'], st['1-1-2']) == ('met', 'met') and e.s['sessions']['S3']['teach'] == 1
      and e.s['checks']['k1']['active'] == 'S3' and e.s['checks']['k2']['state'] == 'abandoned'
      and e.s['checks']['k2']['hold_reason'] == 'no_alternate')

# 27) المعالجة تحددها البوابة (6.1): بوابة أخطاؤها في الفهم وحده والحساب صحيح تعطي «درس البنية»، وخطأ البنود
#     الموجَّهة بعدها يُبقيها. ودرس فُتح بلا بوابة يتعثّر الطفل في افتتاحه يأخذ المسار العادي. وجدته مقارنة أرقام
#     المحاكاة: كان خطأ الافتتاح يجعل المعالجة «عادية» دائمًا
def treatment(e, skill):
    return [x['treatment'] for x in e.valid_evidence(skill, 'stumble')][-1]


e = Engine(NET)
start(e, 'S1', 'search', day=1)
ev(e, 'gate_result', session='S1', skill='1-1-1', result='fail', errors=['ف1', 'ف1'], has_calc=True)
end(e, 'S1')
a = treatment(e, '1-1-1') == 'structure'
start(e, 'S2', 'start', day=2)
ev(e, 'open_lesson', session='S2', skill='1-1-1')
ev(e, 'lesson_opening_result', session='S2', skill='1-1-1', outcome='full_error')
b = treatment(e, '1-1-1') == 'structure' and len(e.valid_evidence('1-1-1', 'stumble')) == 2
e2 = Engine(NET)
start(e2, 'S1', 'start', day=1)
ev(e2, 'open_lesson', session='S1', skill='1-1-1')
ev(e2, 'lesson_opening_result', session='S1', skill='1-1-1', outcome='full_error')
c = treatment(e2, '1-1-1') == 'regular'
e3 = Engine(NET)
start(e3, 'S1', 'search', day=1)
ev(e3, 'gate_result', session='S1', skill='1-1-1', result='fail', errors=['ف3', 'ف1'], has_calc=True)
d = treatment(e3, '1-1-1') == 'regular'
check('بوابة 1-1-1 أخطاؤها في ف1 وحده: «درس البنية»، وخطأ البنود الموجَّهة بعدها يُبقيها. درس بلا بوابة يتعثّر '
      'الطفل في افتتاحه: المسار العادي. وخطأ حساب في البوابة: المسار العادي', a and b and c and d)

# 28) يُحفظ كل دليل ببنوده وتاريخه (3.5): حقل items الاختياري في الحدث يُحفظ مع الدليل ومع المحاولة، ويبقى بعد
#     الحفظ والقراءة وإعادة تشغيل السجل. وقائمة بنود بنوع خاطئ تُرفض قبل أي تغيير
e = Engine(NET)
start(e, 'S1', 'search', day=1)
ev(e, 'gate_result', session='S1', skill='2-6-3', result='help', items=['2-6-3/gate/01'])
ev(e, 'gate_result', session='S1', skill='1-1-1', result='fail', errors=['ف1', 'ف1'], has_calc=True,
   items=['1-1-1/gate/01', '1-1-1/gate/02'])
a = refused(e, 'gate_result', 'bad_event', None, session='S1', skill='1-1-2', result='pass', items='1-1-2/gate/01')
end(e, 'S1')
start(e, 'S2', 'start', day=2)
ev(e, 'open_lesson', session='S2', skill='1-1-1')
ev(e, 'lesson_opening_result', session='S2', skill='1-1-1', outcome='full_error', items=['1-1-1/opening/03'])
ev(e, 'understanding_proved', session='S2', skill='1-1-1', items=['1-1-1/evidence/01', '1-1-1/evidence/02'])
end(e, 'S2')
start(e, 'S3', 'follow', day=3)
ev(e, 'check_started', session='S3', skill='1-1-1', check_id='k1', content_version=1)
ev(e, 'independence_result', session='S3', skill='1-1-1', check_id='k1', result='pass',
   items=['1-1-1/checkA/%02d' % k for k in range(1, 11)])
by = {(x['skill'], x['kind'], x['source']): x['items'] for x in e.s['evidence']}
b = (by[('1-1-1', 'stumble', 'gate')] == ['1-1-1/gate/01', '1-1-1/gate/02']
     and by[('1-1-1', 'stumble', 'lesson')] == ['1-1-1/opening/03']
     and by[('1-1-1', 'understood', 'lesson')] == ['1-1-1/evidence/01', '1-1-1/evidence/02']
     and len(by[('1-1-1', 'independent', 'check')]) == 10)
c = [x['items'] for x in e.s['attempts'] if x['skill'] == '2-6-3'] == [['2-6-3/gate/01']]
back = Engine.restore(NET, e.dump(), content_versions=[1])
again = Engine.replay(NET, e.s['log'])
d = back.s['evidence'] == e.s['evidence'] and again.dump() == e.dump()
check('بنود البوابة والافتتاح ودليل الفهم والفحص تُحفظ مع أدلتها، وبنود بوابة انتهت بطلب دعم مع محاولتها. وتبقى '
      'بعد الحفظ والقراءة وإعادة تشغيل السجل. وقائمة بنود ليست قائمة تُرفض', a and b and c and d)

# 29) فحوص الاحتفاظ (3.7، بقرار الأب في ك8): بعد اجتياز الاستقلال بـ 7 أيام، ثم 21 يومًا بعد يوم الفحص السابق
#     الفعلي، ثم 60. الفحص المتأخر يؤخّر ما بعده. أقل من 4 من 5 تُعلَّم «تحتاج تثبيتًا» ولا تغيّر حالة
def met_on(day):
    e = Engine(NET)
    start(e, 'S1', 'start', day=day - 1)
    ev(e, 'open_lesson', session='S1', skill='1-1-1')
    ev(e, 'understanding_proved', session='S1', skill='1-1-1')
    end(e, 'S1')
    start(e, 'S2', 'follow', day=day)
    ev(e, 'check_started', session='S2', skill='1-1-1', check_id='k1', content_version=1)
    ev(e, 'independence_result', session='S2', skill='1-1-1', check_id='k1', result='pass')
    end(e, 'S2')
    return e


def ret(e, sid, **kw):
    return ev(e, 'retention_result', session=sid, skill='1-1-1', **kw)


e = met_on(2)
a = e.retention_next('1-1-1') == (1, 9, 2, 'S2') and e.retention_due(8) == [] and e.retention_due(9) == [('1-1-1', 1, 9)]
start(e, 'S3', 'follow', day=8)
b = (refused(e, 'retention_result', 'retention_early', None, session='S3', skill='1-1-1', correct=5)
     and refused(e, 'retention_result', 'not_met', None, session='S3', skill='1-1-2', correct=5)
     and refused(e, 'retention_result', 'bad_event', None, session='S3', skill='1-1-1', correct=6)
     and refused(e, 'retention_result', 'bad_event', None, session='S3', skill='1-1-1', correct=True))
end(e, 'S3')
start(e, 'S4', 'follow', day=9)
r1 = ret(e, 'S4', correct=5, items=['1-1-1/deferred/01'])
c = (r1['ok'] and r1['changed'] == {} and refused(e, 'retention_result', 'retention_early', None, session='S4',
                                                  skill='1-1-1', correct=5))
end(e, 'S4')
start(e, 'S5', 'follow', day=35)                              # تأخر 5 أيام عن موعده في اليوم 30
r2 = ret(e, 'S5', correct=3)
end(e, 'S5')
start(e, 'S6', 'follow', day=65)
start_ok = refused(e, 'retention_result', 'retention_early', None, session='S6', skill='1-1-1', correct=5)
end(e, 'S6')
start(e, 'S7', 'follow', day=94)                              # 9 + 21 + 60 = 90 مضى، والموعد 35 + 60 = 95
late = refused(e, 'retention_result', 'retention_early', None, session='S7', skill='1-1-1', correct=5)
end(e, 'S7')
start(e, 'S8', 'follow', day=95)
r3 = ret(e, 'S8', correct=4, exposed=True)
d = (r2['ok'] and start_ok and late and r3['ok']
     and refused(e, 'retention_result', 'retention_done', None, session='S8', skill='1-1-1', correct=5))
end(e, 'S8')
rows = [(x['round'], x['day'], x['due_day'], x['days_since'], x['correct'], x['label'], x['consolidate'])
        for x in e.s['retention']]
f = (rows == [(1, 9, 9, 7, 5, 'retention', False), (2, 35, 30, 26, 3, 'retention', True),
              (3, 95, 95, 60, 4, 'deferred_performance', False)]
     and e.s['retention'][0]['items'] == ['1-1-1/deferred/01'] and e.derive()['1-1-1'] == 'met'
     and [h['what'] for h in e.s['history'] if h['what'].startswith('retention')] == ['retention_consolidate']
     and e.retention_pending() == [])
back = Engine.restore(NET, e.dump(), content_versions=[1])
g = back.s['retention'] == e.s['retention'] and Engine.replay(NET, e.s['log']).dump() == e.dump()
check('فحص الاحتفاظ: يُرفض قبل اليوم 7 ولمهارة غير مستوفاة ولعدد خارج 0 إلى 5. الأول في اليوم 9، والثاني تأخر إلى '
      'اليوم 35 فصار موعد الثالث 95 لا 90. 3 من 5 تُعلَّم «تحتاج تثبيتًا» والحالة باقية. تدريب مباشر في الفاصل: «أداء '
      'مؤجل». بعد الثالث لا رابع. ويبقى كله بعد الحفظ وإعادة تشغيل السجل', a and b and c and d and f and g)

# 30) فحص الاحتفاظ وتنبيه التاريخ والإبطال: جلسة بتنبيه تاريخ لا تقبله حتى يؤكد الوالد. إبطال جلسة الفحص يُسقطه
#     فيعود موعده، وإبطال جلسة الاجتياز يُسقط الاستيفاء فلا فحص احتفاظ. ودرس نشط داخل الفاصل: «أداء مؤجل»
e = met_on(2)
start(e, 'S3', 'follow', day=40)                              # بعد آخر جلسة بأكثر من 30 يومًا
a = refused(e, 'retention_result', 'date_unconfirmed', None, session='S3', skill='1-1-1', correct=5)
ev(e, 'date_confirmed', target='S3')
a = a and ret(e, 'S3', correct=5)['ok'] and e.retention_next('1-1-1')[:2] == (2, 61)
end(e, 'S3')
ev(e, 'invalidate_session', target='S3')
b = (e.retention_next('1-1-1')[:2] == (1, 9) and [x['valid'] for x in e.s['retention']] == [False]
     and 'retention_invalidated' in [h['what'] for h in e.s['history']])
start(e, 'S4', 'follow', day=41)
b = b and ret(e, 'S4', correct=5)['ok'] and e.s['retention'][-1]['round'] == 1
end(e, 'S4')
ev(e, 'invalidate_session', target='S2')
start(e, 'S5', 'follow', day=70)
c = (e.derive()['1-1-1'] != 'met' and e.retention_next('1-1-1') is None
     and refused(e, 'retention_result', 'not_met', None, session='S5', skill='1-1-1', correct=5))
e2 = met_on(2)
start(e2, 'S3', 'follow', day=5)
ev(e2, 'resume_lesson', session='S3', skill='1-1-1')           # تدريب مباشر داخل الفاصل
end(e2, 'S3')
start(e2, 'S4', 'follow', day=9)
ret(e2, 'S4', correct=5)
d = e2.s['retention'][0]['label'] == 'deferred_performance'
old = Engine(NET)
text = old.dump().replace(', "retention": []', '')
d = d and '"retention"' not in text and Engine.restore(NET, text).s['retention'] == []
check('جلسة بتنبيه تاريخ لا تقبل فحص الاحتفاظ حتى يؤكد الوالد. إبطال جلسة الفحص يُسقطه ويعيد موعده. إبطال جلسة '
      'الاجتياز: لا فحص احتفاظ. درس نشط داخل الفاصل: «أداء مؤجل». وحالة محفوظة قبل هذه الإضافة تُقرأ',
      a and b and c and d)

if not all(results):
    print('أخفق اختبار.')
    sys.exit(1)
print('نجحت الاختبارات كلها: %d' % len(results))
