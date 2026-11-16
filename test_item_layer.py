#!/usr/bin/env python3
"""اختبارات طبقة البنود والمجدول، ومسارات كاملة بمحتوى الشريحة الفعلي.

    python3 test_item_layer.py <ملف الخريطة>

1. الحقول الخمسة والمؤشرات (3.1، 3.2).
2. الأنشطة واحدًا واحدًا بنتائج مفروضة: البوابة، التحقق القصير، افتتاح الدرس، دليل الفهم، فحص الاستقلال.
3. حفظ نشاط في منتصفه واستئنافه.
4. مسارات كاملة: محتوى الشريحة وطبقة البنود والمجدول والمحرك معًا، بطفل يتعلّم المهارة حين يرى درسها.
القيم المتوقعة مكتوبة هنا صراحة. ومصدر البنود يتوقف إن طُلب نوع دليل لا يطابق البند.
"""
import json
import re
import sys
from collections import Counter

from item_layer import (fold_item, classify, correct_independent, indicators, gate_plan, GateRun, ShortCheckRun,
                        OpeningRun, EvidenceRun, CheckRun, Activity, drive)
from transition_engine import Engine, load_network, ROW
from scheduler import Scheduler
from content_source import ContentSource, load_items

MAP = sys.argv[1]
NET = load_network(MAP)
TYPES = {}
for sid, _t, _m, _r, ev, _a in ROW.findall(open(MAP, encoding='utf-8').read()):
    if sid in NET[1] and sid not in TYPES:
        TYPES[sid] = re.findall(r'ف\d', ev)
ITEMS = load_items()
results = []


def check(name, cond):
    results.append(bool(cond))
    print('  %s  %d. %s' % ('نجح' if cond else 'أخفق', len(results), name))


def feed(act, outcomes):
    for o in outcomes:
        act.feed(o)
    return act


print('=== اختبارات طبقة البنود والمجدول (%d بندًا في المحتوى)' % len(ITEMS))

# ---------------------------------------------------------------- 1. الحقول الخمسة والمؤشرات
r = fold_item([('confirm', 5), ('support', 'extra_model'), ('confirm', 7), ('end',)], 7, assess=False)
check('أخطأ وحده ثم نجح بالنموذج: أول إجابة خاطئة ونتيجته النهائية صحيحة بدعم، والحقلان محفوظان معًا',
      r == dict(status='complete', first=False, support_before=[],
                later=[dict(correct=True, support=['extra_model'])], final='correct',
                support_unanswered=[]) and classify(r) == 'wrong')
r1 = fold_item([('support', 'requested'), ('interrupt',)], 3, assess=True)
r2 = fold_item([('interrupt',)], 3, assess=True)
r3 = fold_item([('support', 'hint'), ('confirm', 3), ('end',)], 3, assess=False)
r4 = fold_item([('confirm', 2), ('interrupt',)], 3, assess=False)
check('طُلب دعم ثم انقطع: منقطع ومعه الدعم، فهو «طلب دعم». انقطاع بلا دعم «انقطاع». تلميح ثم صحيح: مدعوم لا مستقل. '
      'انقطاع بعد أول إجابة: مكتمل ونتيجته لم تكتمل',
      classify(r1) == 'help' and r1['status'] == 'interrupted' and r1['support_before'] == ['requested']
      and classify(r2) == 'interrupted' and classify(r3) == 'supported' and not correct_independent(r3)
      and r4['status'] == 'complete' and r4['final'] == 'incomplete')
errs = 0
for raw, assess in (([('confirm', 1), ('confirm', 2)], True), ([('end',)], False), ([('confirm', 1)], False),
                    ([('support', 'nap'), ('interrupt',)], False)):
    try:
        fold_item(raw, 1, assess)
    except ValueError:
        errs += 1
check('تسلسلات غير سليمة تُرفض: تأكيد ثانٍ في بند تقييم، ونهاية بلا إجابة، وبند لم ينتهِ، ونوع دعم مجهول', errs == 4)
recs = [fold_item([('confirm', 1)], 1, True),                                         # صحيح مستقل
        fold_item([('confirm', 2), ('support', 'extra_model'), ('confirm', 1), ('end',)], 1, False),
        fold_item([('support', 'hint'), ('confirm', 2), ('end',)], 1, False),          # تلميح ثم خطأ
        fold_item([('support', 'requested'), ('interrupt',)], 1, True),               # دعم ثم انقطاع
        fold_item([('interrupt',)], 1, True),
        fold_item([('support', 'hint'), ('confirm', 1), ('end',)], 1, False)]          # تلميح ثم صحيح
ind = indicators(recs)
check('المؤشرات من ستة بنود: الإجابة الأولى 2 من 4 واثنتان بعد دعم، والمستقل 1 من 4، وبمساعدة 2 من 3 ومدعوم منقطع 1، '
      'والمنقطعة 2 منها 1 بدعم',
      (ind['first_answer']['num'], ind['first_answer']['den'], ind['first_answer']['after_support']) == (2, 4, 2)
      and (ind['independent']['num'], ind['independent']['den']) == (1, 4)
      and (ind['assisted']['num'], ind['assisted']['den'], ind['assisted']['supported_unfinished']) == (2, 3, 1)
      and ind['interrupted'] == dict(count=2, with_support=1))

# ---------------------------------------------------------------- 2. الأنشطة
T351 = TYPES['3-5-1']                                                  # ف1 ف2 ف3
plan = gate_plan(T351)
g1 = feed(GateRun('3-5-1', T351), ['correct'] * 9)
g2 = feed(GateRun('3-5-1', T351), ['correct'] * 5 + ['wrong'] + ['correct'] * 3)
w2 = g2.want()
feed(g2, ['correct', 'correct'])
g3 = feed(GateRun('3-5-1', T351), ['correct'] * 5 + ['wrong', 'correct', 'wrong'])
g4 = feed(GateRun('3-5-1', T351), ['wrong', 'wrong'])
g5 = feed(GateRun('3-5-1', T351), ['correct'] * 3 + ['help'])
check('البوابة: قالب 3-5-1 تسعة بنود الحساب أولًا. كلها صحيحة: اجتاز. خطأ واحد ثم بندا تعويض من نوعه صحيحان: اجتاز '
      'والخطأ محفوظ. خطآن في الفهم بعد حساب صحيح: أخفق عند الثاني. خطآن في أولها: أخفق بعد بندين. طلب دعم: ينتهي فورًا',
      plan == ['ف3'] * 5 + ['ف1', 'ف1', 'ف2', 'ف2']
      and (g1.result, g1.shown['gate']) == ('pass', 9) and g1.events()[0]['errors'] == []
      and w2['role'] == 'gate.compensation' and w2['type'] == 'ف1'
      and (g2.result, g2.errors, g2.shown['comp']) == ('pass', ['ف1'], 2)
      and (g3.result, g3.errors, g3.shown['gate']) == ('fail', ['ف1', 'ف2'], 8)
      and (g4.result, g4.shown['gate']) == ('fail', 2) and (g5.result, g5.shown['gate']) == ('help', 4))
g6 = GateRun('3-5-1', T351)
feed(g6, ['interrupted'])
wa = g6.want()
feed(g6, ['interrupted'])
g7 = GateRun('3-5-1', T351)
feed(g7, ['interrupted', 'correct', 'interrupted'])
wb = g7.want()
feed(g7, ['correct', 'correct', 'interrupted'])
g8 = feed(GateRun('3-5-1', T351, tolerant=False), ['correct', 'wrong'])
g9 = feed(GateRun('3-5-1', T351), ['correct'] * 5 + ['wrong'] + ['correct'] * 3 + ['wrong'])
g10 = GateRun('3-5-1', T351)
g10.unavailable()
check('البوابة والانقطاع: بعد انقطاع يُطلب بديل من نوعه، وانقطاعان في بند واحد يعلّقانها بلا نتيجة. بديلا نوع واحد '
      'يُرقَّمان 0 ثم 1، والانقطاع الثالث يعلّقها. البوابة الصارمة تُخفق بأول خطأ، وخطأ في التعويض يُخفق، ونفاد البدائل يعلّقها',
      (wa['alternate'], wa['alt_index'], g6.result) == (1, 0, 'interrupted')
      and (wb['alternate'], wb['alt_index'], g7.result) == (1, 1, 'interrupted')
      and g8.result == 'fail' and (g9.result, g9.errors) == ('fail', ['ف1', 'ف1']) and g10.result == 'interrupted')
rc = feed(GateRun('3-5-1', T351, event='recheck_result'), ['correct'] * 9)
ri = feed(GateRun('3-5-1', T351, event='recheck_result'), ['interrupted', 'interrupted'])
check('إعادة التحقق بقالب البوابة: اجتياز يعطي recheck_result صحيحًا، والتعليق لا يعطي حدثًا',
      rc.events() == [dict(type='recheck_result', skill='3-5-1', ok=True)] and ri.events() == [])
s1 = feed(ShortCheckRun('3-5-1', T351), ['correct'] * 3)
s2 = feed(ShortCheckRun('3-5-1', T351), ['wrong'])
s3 = feed(ShortCheckRun('3-5-1', T351, stop_early=False), ['wrong', 'correct', 'correct'])
s4 = feed(ShortCheckRun('3-5-1', T351), ['correct', 'interrupted'])
s5 = feed(ShortCheckRun('3-5-1', T351), ['help'])
check('التحقق القصير: ف1 ثم ف3 ثم ف3. ثلاثة صحيحة: نعم. خطأ أول: لا، ويتوقف بعد بند واحد. بلا توقف مبكر: ثلاثة بنود. '
      'الانقطاع بلا نتيجة ولا حدث. طلب الدعم: لا',
      s1.types == ['ف1', 'ف3', 'ف3'] and s1.result is True and (s2.result, s2.shown['short']) == (False, 1)
      and (s3.result, s3.shown['short']) == (False, 3) and s4.result is None and s4.events() == []
      and s5.result is False)
o1 = feed(OpeningRun('3-5-1', T351), ['correct', 'correct'])
o2 = feed(OpeningRun('3-5-1', T351), ['wrong', 'correct', 'correct', 'correct', 'correct'])
o3 = feed(OpeningRun('3-5-1', T351), ['wrong', 'wrong', 'correct', 'wrong'])
o4 = feed(OpeningRun('3-5-1', T351), ['wrong', 'correct', 'help'])
o5 = feed(OpeningRun('3-5-1', T351, try_errors_count=True), ['wrong', 'correct', 'help'])
o6 = OpeningRun('3-5-1', T351)
w6a = o6.want()
feed(o6, ['interrupted'])
w6b = o6.want()
check('افتتاح الدرس: «جرّب أولًا» ف3 ثم ف1 والموجَّهة ف1. صحّا: اختُصر. أخطأ ثم صحّت الموجَّهة: اختُصر. خطأ في موجَّه: '
      'درس كامل بدليل تعثّر. طلب دعم في موجَّه: درس كامل بلا دليل، وفي وضع المحاكاة القديمة يُعدّ خطأ «جرّب أولًا» '
      'دليلًا. والبند المنقطع يُعاد عرضه',
      o1.try_types == ['ف3', 'ف1'] and o1.guided == ['ف1'] * 3 and o1.result == 'skip'
      and (o2.result, o2.shown['try'], o2.shown['lesson']) == ('skip', 2, 3) and o3.result == 'full_error'
      and o4.result == 'full_help' and o5.result == 'full_error'
      and (w6a['pos'], w6a['type']) == (w6b['pos'], w6b['type']) and w6b['reshown'] == 1)
T142 = TYPES['1-4-2']                                                  # ف2 ف3 ف4
e1 = feed(EvidenceRun('1-4-2', T142), ['correct'] * 6)
e2 = EvidenceRun('1-4-2', T142)
feed(e2, ['correct', 'correct', 'wrong'])
w = e2.want()
feed(e2, ['correct', 'correct', 'correct', 'correct'])
e3 = feed(EvidenceRun('1-4-2', T142), ['correct', 'correct', 'supported', 'correct', 'wrong'])
e4 = EvidenceRun('1-4-2', T142, proven=['ف2'])
w4 = e4.want()
e5 = EvidenceRun('1-4-2', T142)
e5.unavailable()
check('دليل الفهم: بندان صحيحان لكل نوع بترتيبه. خطأ في ف3: درس قصير ثم بندان احتياطيان منه، فإن صحّا ثبت الفهم. '
      'بند مدعوم يُعامل كالخطأ، وخطأ في الاحتياطي يُنهي الجولة بلا دليل. النوع الثابت لا يُعاد، ونفاد البنود يُعلَّم',
      e1.result == 'proven' and e1.events() == [dict(type='understanding_proved', skill='1-4-2')]
      and (w['role'], w['type'], w['short_lesson_before']) == ('evidence.reserve', 'ف3', True)
      and e2.result == 'proven' and e2.short_lessons == 1
      and (e3.result, e3.failed, e3.events()) == ('not_proven', 'ف3', [])
      and w4['type'] == 'ف3' and (e5.result, e5.failed) == ('no_items', 'ف2'))
c1 = feed(CheckRun('1-4-1', 'k1', 1), ['correct'] * 9 + ['wrong'])
c2 = feed(CheckRun('1-4-1', 'k2', 1), ['correct'] * 8 + ['wrong', 'wrong'])
c3 = feed(CheckRun('1-4-1', 'k3', 1), ['correct', 'wrong', 'correct', 'help'])
c4 = CheckRun('1-4-1', 'k4', 1)
feed(c4, ['correct', 'interrupted'])
w4 = c4.want()
feed(c4, ['interrupted'])
c5 = feed(CheckRun('1-4-1', 'k5', 1), ['interrupted', 'correct', 'interrupted', 'correct', 'interrupted'])
c6 = CheckRun('1-4-1', 'k6', 1)
feed(c6, ['interrupted'])
c6.unavailable()
check('فحص الاستقلال: 9 من 10 يجتاز و8 يُخفق. طلب الدعم يغلقه «انتهت بطلب دعم» وإجاباته السابقة محفوظة. بعد انقطاع '
      'يُطلب بديل الخانة، وانقطاعان فيها أو ثلاثة في الفحص أو نفاد البديل تعلّقه للمراجعة بحدث تعليق وسببه، بلا نتيجة',
      (c1.result, c2.result, c3.result) == ('pass', 'fail', 'help') and c3.answers == {'1': 'correct', '2': 'wrong',
                                                                                     '3': 'correct', '4': 'help'}
      and (w4['slot'], w4['alternate'], w4['role']) == (2, 1, 'check.alternate')
      and (c4.result, c4.hold) == ('held', 'interruptions') and (c5.result, c5.hold) == ('held', 'interruptions')
      and (c6.result, c6.hold) == ('held', 'no_alternate')
      and c6.events() == [dict(type='check_held', skill='1-4-1', check_id='k6', reason='no_alternate')]
      and c1.start_event() == dict(type='check_started', skill='1-4-1', check_id='k1', content_version=1))

# ---------------------------------------------------------------- 3. الحفظ والاستئناف
ok = True
for make, seq in ((lambda: GateRun('3-5-2', TYPES['3-5-2']), ['correct', 'interrupted', 'correct', 'wrong'] +
                   ['correct'] * 8 + ['correct', 'correct']),
                  (lambda: CheckRun('3-5-2', 'k', 2), ['correct', 'interrupted'] + ['correct'] * 8 + ['wrong']),
                  (lambda: EvidenceRun('3-5-2', TYPES['3-5-2']), ['correct', 'wrong'] + ['correct'] * 8)):
    whole = feed(make(), seq)
    part = feed(make(), seq[:4])
    back = Activity.from_dict(json.loads(json.dumps(part.to_dict(), ensure_ascii=False)))
    feed(back, seq[4:])
    ok = ok and back.result == whole.result and back.shown == whole.shown and back.events() == whole.events()
check('بوابة وفحص ودليل فهم تُحفظ حالتها نصًّا في منتصفها ثم تُستأنف: النتيجة والبنود المعروضة والأحداث كما في التشغيل '
      'المتصل', ok)


# ---------------------------------------------------------------- 4. مسارات كاملة بمحتوى الشريحة
class LearningChild:
    """يجيب صحيحًا عن مهارة يعرفها، ويتعلّم المهارة حين يرى بنود درسها. slips: أحداث مفروضة لبنود بعينها."""

    def __init__(self, knows=(), slips=None):
        self.known, self.slips, self.seen = set(knows), dict(slips or {}), []

    def __call__(self, item, want):
        a = want['activity']
        self.seen.append(item['id'])
        if a in ('lesson', 'practice'):
            if a == 'lesson':
                self.known.add(item['skill'])
            return 'correct'
        assess = a in ('gate', 'short', 'check', 'retention')
        tail = [] if assess else [('end',)]
        if item['id'] in self.slips:
            raw = self.slips.pop(item['id'])
        elif item['skill'] in self.known:
            raw = [('confirm', item['answer'])] + tail
        else:
            wrong = item['answer'] + 1 if item['answer'] < 99 else item['answer'] - 1
            raw = [('confirm', wrong)] + tail
        return raw, item['answer'], assess


def flow(e):
    out = []
    for x in e.s['log']:
        out.append((x.get('session', '-'), x['type'], x.get('skill') or x.get('target') or '',
                    x.get('result') or x.get('outcome') or ''))
    return out


def scenario(scope, group, start, decisions, knows=(), slips=None, same_fact=True, before=None, sessions=30,
             **sched):
    e = Engine(NET, group=group)
    for k, (skill, bypass) in enumerate(decisions):
        e.apply(dict(id='d%d' % k, type='teacher_open', skill=skill, bypass=bypass, reason='قرار الشريحة في 10.2'))
    src = ContentSource(ITEMS, allow_same_fact=same_fact)
    child = LearningChild(knows, slips)
    records = []
    sc = Scheduler(e, TYPES, src, child, group=group, start=start, scope=set(scope), learning=True,
                   records=records, **sched)
    if before:
        before(sc)
    sc.run(max_sessions=sessions)
    return e, sc, child, src, records


def sessions_of(e, kinds=('gate_result', 'open_lesson', 'lesson_opening_result', 'understanding_proved',
                          'check_started', 'independence_result', 'resume_lesson', 'short_check_result',
                          'check_abandoned')):
    return [(s, t, k, r) for s, t, k, r in flow(e) if t in kinds]


def item_of(skill, group, role, slot=None, pos=0):
    lst = [i for i in ITEMS if i['skill'] == skill and i['group'] == group and i['role'] == role
           and (slot is None or i['slot'] == slot)]
    return lst[pos]['id']


# أ) الصغير في الوحدة 1-4: قرار المعلم يتجاوز 1-3-3 كما في 10.2
e, sc, child, src, recs = scenario(['1-4-1', '1-4-2'], 'young', None, [('1-4-1', ['1-3-3'])])
want = [('S1', 'gate_result', '1-4-1', 'fail'),
        ('S2', 'open_lesson', '1-4-1', ''), ('S2', 'lesson_opening_result', '1-4-1', 'full_error'),
        ('S2', 'understanding_proved', '1-4-1', ''),
        ('S3', 'check_started', '1-4-1', ''), ('S3', 'independence_result', '1-4-1', 'pass'),
        ('S4', 'gate_result', '1-4-2', 'fail'), ('S4', 'open_lesson', '1-4-2', ''),
        ('S4', 'lesson_opening_result', '1-4-2', 'full_error'), ('S4', 'understanding_proved', '1-4-2', ''),
        ('S5', 'check_started', '1-4-2', ''), ('S5', 'independence_result', '1-4-2', 'pass')]
st = e.derive()
ind = indicators([r for r in recs if r['activity'] == 'check'])
check('الوحدة 1-4 كاملة: بوابة 1-4-1 تُخفق، ثم درسها في جلسة البدء ودليل فهمها، ثم فحصها في اليوم التالي، ثم بوابة '
      '1-4-2 ودرسها، ثم فحصها. خمس جلسات، ولا رفض، وكل بند من نوعه، وبنود الفحصين صحيحة مستقلة كلها',
      sessions_of(e) == want and (st['1-4-1'], st['1-4-2']) == ('met', 'met') and sc.refused == []
      and sc.sessions == 5 and (ind['independent']['num'], ind['independent']['den']) == (20, 20))

# ب) الكبيران في الوحدة 3-5: قراران يتجاوزان متطلبات 3-5-1 و3-5-2، والبدء عند 3-5-3
e, sc, child, src, recs = scenario(['3-5-1', '3-5-2', '3-5-3'], 'older', '3-5-3',
                                   [('3-5-1', ['3-3-2', '3-2-3']), ('3-5-2', ['3-2-1', '3-3-1', '2-5-2'])])
want = [('S1', 'gate_result', '3-5-3', 'fail'), ('S1', 'gate_result', '3-5-1', 'fail'),
        ('S2', 'open_lesson', '3-5-1', ''), ('S2', 'lesson_opening_result', '3-5-1', 'full_error'),
        ('S2', 'understanding_proved', '3-5-1', ''),
        ('S3', 'gate_result', '3-5-2', 'fail'), ('S3', 'check_started', '3-5-1', ''),
        ('S3', 'independence_result', '3-5-1', 'pass'),
        ('S4', 'open_lesson', '3-5-2', ''), ('S4', 'lesson_opening_result', '3-5-2', 'full_error'),
        ('S4', 'understanding_proved', '3-5-2', ''),
        ('S5', 'check_started', '3-5-2', ''), ('S5', 'independence_result', '3-5-2', 'pass'),
        ('S6', 'open_lesson', '3-5-3', ''), ('S6', 'lesson_opening_result', '3-5-3', 'full_error'),
        ('S6', 'understanding_proved', '3-5-3', ''),
        ('S7', 'check_started', '3-5-3', ''), ('S7', 'independence_result', '3-5-3', 'pass')]
st = e.derive()
served = Counter(i.split('/')[1] for i in src.served)
check('الوحدة 3-5 كاملة: بوابتا 3-5-3 و3-5-1 في جلسة البحث، ودرس 3-5-1 في جلسة البدء، وبوابة 3-5-2 مع فحص 3-5-1 '
      'في جلسة واحدة، ثم درس 3-5-2 وفحصه، ثم 3-5-3 حين استُوفي متطلباها. سبع جلسات بلا رفض، ولم يُعرض بند مرتين',
      sessions_of(e) == want and all(st[s] == 'met' for s in ('3-5-1', '3-5-2', '3-5-3')) and sc.refused == []
      and sc.sessions == 7 and len(src.served) == len(set(src.served)) and served['regate'] == 0)

# ج) زلّة في البوابة: يعرف 3-5-3 فيُختصر درسها، وإعادة البوابة ببنود جديدة تُعفيه
slips = {item_of('3-5-3', 'gate', 'gate', pos=0): [('confirm', 0)], item_of('3-5-3', 'gate', 'gate', pos=1): [('confirm', 0)]}
e, sc, child, src, recs = scenario(['3-5-3'], 'older', '3-5-3', [('3-5-3', ['3-5-1', '3-5-2'])], knows=['3-5-3'],
                                   slips=slips)
want = [('S1', 'gate_result', '3-5-3', 'fail'), ('S2', 'open_lesson', '3-5-3', ''),
        ('S2', 'lesson_opening_result', '3-5-3', 'skip'), ('S3', 'gate_result', '3-5-3', 'pass')]
regate_items = [i for i in src.served if '/regate/' in i]
check('زلّتان في بوابة 3-5-3 لطفل يعرفها: «جرّب أولًا» يختصر الدرس، وإعادة البوابة في جلسة لاحقة ببنود جديدة '
      'تُعفيه. ثلاث جلسات ولا درس كامل',
      sessions_of(e) == want and e.derive()['3-5-3'] == 'exempt' and len(regate_items) == 6
      and not set(regate_items) & {i for i in src.served if '/gate/' in i} and sc.refused == [])


# د) انقطاع في خانة لا عدد آخر يحقق شرطها في المجال الصغير. بقرار الأب (3.6): تُعاد الحقيقة نفسها ويُسجَّل ذلك
def abandon_when_held(sc):
    old_teach = sc.teach

    def teach():
        held = [k for k, c in sc.e.s['checks'].items() if c['state'] == 'held' and sc.cur and
                c['held_session'] != sc.cur]
        for k in held:                                     # المعلم يرى الفحص المعلَّق فيتركه
            sc.send(dict(type='check_abandoned', check_id=k, reason='انقطاعان في خانة واحدة'))
        return old_teach()
    sc.teach = teach


cut = item_of('1-4-1', 'checkA', 'check', slot=7)                         # خانة «خمسة أقراص»
alt = item_of('1-4-1', 'checkA', 'check.alternate', slot=7)
e1, sc1, _, _, recs1 = scenario(['1-4-1'], 'young', None, [('1-4-1', ['1-3-3'])], slips={cut: [('interrupt',)]},
                                sessions=6)
e2, sc2, *_ = scenario(['1-4-1'], 'young', None, [('1-4-1', ['1-3-3'])],
                       slips={cut: [('interrupt',)], alt: [('interrupt',)]}, before=abandon_when_held, sessions=8)
e3, sc3, *_ = scenario(['1-4-1'], 'young', None, [('1-4-1', ['1-3-3'])], slips={cut: [('interrupt',)]},
                       same_fact=False, sessions=6)
f1 = [x for x in sessions_of(e1) if x[1] in ('check_started', 'independence_result')]
f2 = [x for x in sessions_of(e2) if x[1] in ('check_started', 'independence_result', 'check_abandoned')]
f3 = [x for x in sessions_of(e3) if x[1] in ('check_started', 'independence_result')]
again = [r['item'] for r in recs1 if r.get('reshown_after_interrupt')]
check('انقطاع في خانة «خمسة أقراص»: بقرار الأب تُعاد الحقيقة نفسها، ويُسجَّل البند «أُعيد عرضه بعد انقطاع»، ويُجتاز '
      'الفحص في المحاولة نفسها. وانقطاع ثانٍ في الخانة يعلّق الفحص للمراجعة، فإن تركه المعلم بُدئت المحاولة ب '
      'واجتيزت. وبالنص السابق للقرار يُعلَّق الفحص عند أول انقطاع',
      f1 == [('S3', 'check_started', '1-4-1', ''), ('S3', 'independence_result', '1-4-1', 'pass')]
      and again == [alt] and e1.derive()['1-4-1'] == 'met'
      and [x[1] for x in f2] == ['check_started', 'check_abandoned', 'check_started', 'independence_result']
      and f2[-1][3] == 'pass' and e2.derive()['1-4-1'] == 'met'
      and e2.s['checks']['1-4-1/check/1']['hold_reason'] == 'interruptions'
      and f3 == [('S3', 'check_started', '1-4-1', '')]
      and (e3.s['checks']['1-4-1/check/1']['state'], e3.s['checks']['1-4-1/check/1']['hold_reason']) == ('held', 'no_alternate')
      and sc1.refused == sc2.refused == sc3.refused == [])

# هـ) طلب دعم في الفحص، ثم إخفاقان: الإعادة بعد يوم، وبعد الإخفاق جلسة تدريب أولًا، ثم تنفد البنود
cut = item_of('1-4-1', 'checkA', 'check', slot=3)
wrongs = {item_of('1-4-1', g, 'check', slot=k): [('confirm', -1)] for g in ('checkB', 'checkC') for k in (1, 2)}
slips = dict({cut: [('support', 'requested'), ('interrupt',)]}, **wrongs)
e, sc, child, src, recs = scenario(['1-4-1'], 'young', None, [('1-4-1', ['1-3-3'])], slips=slips, sessions=10)
f = [x for x in sessions_of(e) if x[1] in ('check_started', 'independence_result', 'resume_lesson')]
held = [x for x in sc.log if x[1] == 'check_held']
check('طلب دعم في الخانة 3 يغلق المحاولة أ «انتهت بطلب دعم»، والمحاولة ب في اليوم التالي بلا تدريب. خطآن فيها: '
      '8 من 10 لم تُجتز، فجلسة تدريب، ثم المحاولة ج في يوم لاحق ببنودها. خطآن فيها أيضًا، فجلسة تدريب، ثم محاولة رابعة '
      'لا بنود لها في المحتوى، فتُعلَّق للمعلم',
      f == [('S3', 'check_started', '1-4-1', ''), ('S3', 'independence_result', '1-4-1', 'help'),
            ('S4', 'check_started', '1-4-1', ''), ('S4', 'independence_result', '1-4-1', 'fail'),
            ('S5', 'resume_lesson', '1-4-1', ''),
            ('S6', 'check_started', '1-4-1', ''), ('S6', 'independence_result', '1-4-1', 'fail'),
            ('S7', 'resume_lesson', '1-4-1', ''), ('S8', 'check_started', '1-4-1', '')]
      and sc.refused == [] and held == [(8, 'check_held', '1-4-1')]
      and any('/checkC/' in i for i in src.served)
      and (e.s['checks']['1-4-1/check/4']['state'], e.s['checks']['1-4-1/check/4']['hold_reason']) == ('held', 'no_items'))

# و) قيد الإعادة في المجدول (6.1): مهارة انتهت بوابتها بطلب دعم، ثم صارت مؤجَّلة وأخطأ تحققها القصير، لا تُقترح
#    بوابتها حتى يُفتح درسها ويُختصر. كشفت هذه الحالةَ المحاكاةُ الكاملة: بدونها كرّر المجدول اقتراحًا يرفضه المحرك
e = Engine(NET, group='older')
for k, (skill, bypass) in enumerate([('3-5-1', ['3-3-2', '3-2-3']), ('3-5-2', ['3-2-1', '3-3-1', '2-5-2'])]):
    e.apply(dict(id='d%d' % k, type='teacher_open', skill=skill, bypass=bypass, reason='قرار الشريحة في 10.2'))
sc = Scheduler(e, TYPES, ContentSource(ITEMS), LearningChild(knows=['3-5-1', '3-5-2', '3-5-3']), group='older',
               start='3-5-3', scope={'3-5-1', '3-5-2', '3-5-3'}, learning=True)
sc.begin('search')
sc.send(dict(type='gate_result', skill='3-5-1', result='help'))
sc.send(dict(type='gate_result', skill='3-5-3', result='pass', errors=[], has_calc=True))
sc.end()
sc.begin('start')
sc.send(dict(type='short_check_result', skill='3-5-1', ok=False))
sc.end()
a = e.s['queue'] == ['3-5-1'] and e.derive()['3-5-1'] == 'deferred'
pick1 = sc.pick_gate()
sc.begin('follow')
v = e.preflight(dict(type='gate_result', id='q', session=sc.cur, skill='3-5-1', result='pass'))
sc.teach()
sc.end()
pick2 = sc.pick_gate()
check('3-5-1 انتهت بوابتها بطلب دعم، ثم اجتيزت 3-5-3 فصارت مؤجَّلة، وأخطأ تحققها القصير فطُلبت بوابتها. المحرك '
      'يرفض البوابة الآن، والمجدول لا يقترحها، ويفتح درسها فيُختصر، ثم يقترح بوابتها في الجلسة التالية',
      a and pick1 != '3-5-1' and v['code'] == 'regate_not_allowed'
      and e.s['opened']['3-5-1']['phase'] == 'skipped' and pick2 == '3-5-1' and sc.refused == [])

# ز) جولة ثانية لدليل الفهم ببنود جديدة (3.5)، وكل دليل يحفظ بنوده
def ev_items(skill, role, t, rnd):
    return [i['id'] for i in ITEMS if i['skill'] == skill and i['group'] == 'evidence' and i['role'] == role
            and i['evidence'] == t and i.get('round') == rnd]


t0 = TYPES['1-4-1'][0]
slips = {ev_items('1-4-1', 'evidence', t0, 1)[0]: [('confirm', -1), ('end',)],
         ev_items('1-4-1', 'evidence.reserve', t0, 1)[0]: [('confirm', -1), ('end',)]}
e, sc, child, src, recs = scenario(['1-4-1'], 'young', None, [('1-4-1', ['1-3-3'])], slips=slips, sessions=8)
ev_served = [i for i in src.served if '/evidence/' in i]
und = [x for x in e.s['evidence'] if x['skill'] == '1-4-1' and x['kind'] == 'understood']
ind = [x for x in e.s['evidence'] if x['skill'] == '1-4-1' and x['kind'] == 'independent']
round2 = {i['id'] for i in ITEMS if i['skill'] == '1-4-1' and i['group'] == 'evidence' and i.get('round') == 2}
check('خطأ في بند دليل الفهم ثم في البند الاحتياطي: لم يثبت الفهم في الجولة الأولى. في الجلسة التالية جولة ثانية '
      'ببنود جديدة يثبت بها، ثم يُجتاز الفحص. لم يُعرض بند دليل مرتين، ودليل الفهم يحفظ بنود الجولة الثانية، ودليل '
      'الاستقلال يحفظ بنود الفحص العشرة',
      len(ev_served) == len(set(ev_served)) and len(und) == 1 and und[0]['items']
      and set(und[0]['items']) <= round2 and len(ind) == 1
      and len([i for i in ind[0]['items'] if '/checkA/' in i]) == 10 and e.derive()['1-4-1'] == 'met'
      and [x[1] for x in sc.log if x[1].startswith('evidence_')] == ['evidence_not_proven'] and sc.refused == [])

# ح) بندا «جرّب أولًا» من نوعي الخطأ في بوابة المهارة (6.2، بقرار الأب في ك4)
D351 = [('3-5-1', ['3-3-2', '3-2-3'])]
g351 = lambda pos: item_of('3-5-1', 'gate', 'gate', pos=pos)       # القالب: ف3 خمسة، ثم ف1 اثنان، ثم ف2 اثنان


def tried(slips, **kw):
    e, sc, child, src, recs = scenario(['3-5-1'], 'older', '3-5-1', D351, knows=['3-5-1'], slips=slips, sessions=6,
                                       **kw)
    errs = [x.get('errors') for x in e.s['log'] if x['type'] == 'gate_result'][0]
    return errs, [i for i in src.served if '/opening/' in i or '/tryfirst/' in i], e.derive()['3-5-1'], sc.refused


def typed_try(t, k):
    return [i['id'] for i in ITEMS if i['skill'] == '3-5-1' and i['group'] == 'tryfirst' and i['evidence'] == t][k]


bad = [('confirm', 0)]
r1 = tried({g351(7): bad, g351(8): bad})
r2 = tried({g351(5): bad, g351(7): bad})
r3 = tried({g351(7): bad, g351(8): bad}, try_from_gate=False)
r4 = tried({g351(0): [('support', 'requested'), ('interrupt',)]})
fixed = [item_of('3-5-1', 'opening', 'opening.try', pos=0), item_of('3-5-1', 'opening', 'opening.try', pos=1)]
check('«جرّب أولًا» بعد بوابة أخفقت: خطآن في ف2 يعرضان بندي ف2، وخطأ في ف1 ثم في ف2 يعرض بندًا من كل نوع. بوابة '
      'انتهت بطلب دعم بلا خطأ: البندان الثابتان. وبالقاعدة السابقة للقرار: البندان الثابتان دائمًا. الطفل يعرف '
      'المهارة، فيُختصر الدرس وتُعفيه إعادة البوابة في الحالات الأربع',
      r1[:2] == (['ف2', 'ف2'], [typed_try('ف2', 0), typed_try('ف2', 1)])
      and r2[:2] == (['ف1', 'ف2'], [typed_try('ف1', 0), typed_try('ف2', 0)])
      and r3[:2] == (['ف2', 'ف2'], fixed) and r4[:2] == ([], fixed)
      and all(r[2] == 'exempt' and r[3] == [] for r in (r1, r2, r3, r4)))

# ط) سقف الوقت يقطع بوابة (7.1، بقرار الأب في ك9): تُستأنف أول الجلسة التالية بما بقي من بنودها، وتُحسب من
#    بوابات الجلسة التي اكتملت فيها، والجلسات كلها تُحسب في سقف جلسات البحث
D35 = [('3-5-1', ['3-3-2', '3-2-3']), ('3-5-2', ['3-2-1', '3-3-1', '2-5-2'])]
gate_minute = lambda w: 60 if w['activity'] == 'gate' else 0      # كل بند بوابة دقيقة، والسقف 4 دقائق


def set_searches(sc):
    sc.searches = 3


def gates(e):
    return [(x['session'], x['skill'], x['result'], x.get('items', [])) for x in e.s['log'] if x['type'] == 'gate_result']


e, sc, child, src, recs = scenario(['3-5-1', '3-5-2', '3-5-3'], 'older', '3-5-1', D35, knows=['3-5-1'], cap=240,
                                   item_seconds=gate_minute, sessions=14)
nine = [item_of('3-5-1', 'gate', 'gate', pos=k) for k in range(9)]
kinds = [e.s['sessions'][x]['kind'] for x in e.s['order']]
a = (gates(e)[0] == ('S3', '3-5-1', 'pass', nine) and gates(e)[1][:3] == ('S3', '3-5-2', 'fail')
     and [e.s['sessions'][x]['gate'] for x in ('S1', 'S2', 'S3')] == [0, 0, 2] and kinds[:4] == ['search'] * 3 + ['start']
     and sc.searches == 3 and [x for x in sc.log if x[1] == 'capped'] == [(1, 'capped', '3-5-1'), (2, 'capped', '3-5-1')]
     and len(src.served) == len(set(src.served)) and sc.refused == [] and sc.carry is None
     and all(e.derive()[x] in ('exempt', 'met') for x in ('3-5-1', '3-5-2', '3-5-3')))
e, sc, child, src, recs = scenario(['3-5-1', '3-5-2', '3-5-3'], 'older', '3-5-1', D35, knows=['3-5-1'], cap=240,
                                   item_seconds=gate_minute, sessions=14, before=set_searches)
kinds = [e.s['sessions'][x]['kind'] for x in e.s['order']]
b = (kinds[:4] == ['search', 'start', 'follow', 'follow'] and gates(e)[0] == ('S4', '3-5-1', 'pass', nine)
     and e.s['sessions']['S2']['gate'] == 0 and sc.searches == 4 and sc.refused == []
     and len(src.served) == len(set(src.served)))
check('بوابة من 9 بنود والسقف يسع 4: تُعرض 4 في الجلسة الأولى و4 في الثانية، وتكتمل في الثالثة ببندها الأخير، '
      'ونتيجتها حدث واحد فيها ببنودها التسعة، ثم بوابة ثانية في الجلسة نفسها. ثلاث جلسات بحث محسوبة. ولم يُعرض بند '
      'مرتين. وبوابة قطعها السقف في جلسة البحث الرابعة لا تُستأنف في جلسة البدء، وتُستأنف في المتابعة', a and b)

# ي) سقف الوقت يقطع الدرس ثم الفحص: يُستأنف الدرس بحدث resume_lesson من موضعه، والفحص بحدث check_resumed
e, sc, child, src, recs = scenario(['1-4-1'], 'young', None, [('1-4-1', ['1-3-3'])], cap=300, sessions=10,
                                   item_seconds=lambda w: 60 if w['activity'] in ('check', 'lesson') else 0)
f = sessions_of(e, ('open_lesson', 'resume_lesson', 'understanding_proved', 'check_started', 'check_resumed',
                    'independence_result'))
ind = [x for x in e.s['evidence'] if x['kind'] == 'independent'][0]
lesson_items = [i for i in src.served if '/lesson/' in i]
check('السقف يسع 5 بنود: الدرس يُقطع بعد خامس بنوده في جلسة البدء، ويُستأنف في الجلسة التالية من بنده السادس ثم '
      'يثبت الفهم. والفحص يُقطع بعد خانته الخامسة، ويُستأنف في الجلسة التالية بحدث يستهلك حصتها، ونتيجته فيها '
      'بخاناته العشر. لم يُعرض بند مرتين',
      f == [('S2', 'open_lesson', '1-4-1', ''), ('S3', 'resume_lesson', '1-4-1', ''),
            ('S3', 'understanding_proved', '1-4-1', ''), ('S4', 'check_started', '1-4-1', ''),
            ('S5', 'check_resumed', '1-4-1', ''), ('S5', 'independence_result', '1-4-1', 'pass')]
      and len(lesson_items) == 7 and len(src.served) == len(set(src.served))
      and len([i for i in ind['items'] if '/checkA/' in i]) == 10 and len(ind['items']) == 10
      and [e.s['sessions'][x]['teach'] for x in ('S2', 'S3', 'S4', 'S5')] == [1, 1, 1, 1]
      and [x for x in sc.log if x[1] == 'capped'] == [(2, 'capped', '1-4-1'), (4, 'capped', '1-4-1')]
      and e.derive()['1-4-1'] == 'met' and sc.refused == [] and sc.carry is None)

# ك) فحوص الاحتفاظ في المسار (3.7، بقرار الأب في ك8)، بجلسة كل يوم
def deferred(rnd):
    return [i['id'] for i in ITEMS if i['skill'] == '1-4-1' and i['group'] == 'deferred' and i['slot'] == rnd]


def rows(e):
    return [(x['round'], x['session'], x['day'], x['due_day'], x['days_since'], x['correct'], x['consolidate'])
            for x in e.s['retention']]


e, sc, child, src, recs = scenario(['1-4-1'], 'young', None, [('1-4-1', ['1-3-3'])], retention=True, sessions=120)
a = (rows(e) == [(1, 'S10', 9, 9, 7, 5, False), (2, 'S31', 30, 30, 21, 5, False), (3, 'S91', 90, 90, 60, 5, False)]
     and [x['items'] for x in e.s['retention']] == [deferred(1), deferred(2), deferred(3)] and sc.sessions == 91
     and sc.refused == [] and len(src.served) == len(set(src.served)) and e.derive()['1-4-1'] == 'met')
slips = {deferred(1)[0]: [('interrupt',)], deferred(2)[0]: [('confirm', -1)], deferred(2)[1]: [('confirm', -1)]}
e, sc, child, src, recs = scenario(['1-4-1'], 'young', None, [('1-4-1', ['1-3-3'])], retention=True, sessions=120,
                                   slips=slips)
b = (rows(e) == [(1, 'S11', 10, 9, 8, 5, False), (2, 'S32', 31, 31, 21, 3, True), (3, 'S92', 91, 91, 60, 5, False)]
     and [x for x in sc.log if x[1] == 'retention_cut'] == [(10, 'retention_cut', '1-4-1')]
     and sc.refused == [] and e.derive()['1-4-1'] == 'met')
check('اجتاز 1-4-1 في اليوم 2: فحوص الاحتفاظ في الأيام 9 ثم 30 ثم 90، كل منها ببنود جولته الخمسة، ولم يُعرض بند '
      'مرتين. وانقطاع في الفحص الأول ينهيه بلا نتيجة فيُجرى في اليوم التالي، فتتأخر المواعد بعده يومًا. وخطآن في '
      'الثاني: 3 من 5 تُعلَّم «تحتاج تثبيتًا»، والمهارة باقية مستوفاة', a and b)

if not all(results):
    print('أخفق اختبار.')
    sys.exit(1)
print('نجحت الاختبارات كلها: %d' % len(results))
