#!/usr/bin/env python3
"""طبقة البنود: من أحداث البند الخام إلى أحداث المحرك (الأقسام 3.1 و3.2 و3.4 و3.5 و3.6 و6.1 و6.2).

    python3 test_item_layer.py <ملف الخريطة>

ثلاثة أجزاء:
1. fold_item: أحداث البند الخام (تأكيد، دعم، انقطاع، نهاية) إلى الحقول الخمسة في 3.1.
   و classify: الحقول الخمسة إلى نتيجة واحدة يحتاجها النشاط.
2. indicators: المؤشرات الأربعة في 3.2.
3. أنشطة تنتهي بحدث للمحرك: البوابة، التحقق القصير، افتتاح الدرس، دليل الفهم، فحص الاستقلال،
   وإعادة التحقق.

كل نشاط آلة حالات لا تعرف بنك البنود ولا المحرك. تطلب بـ want() وصفًا لما يُعرض («بند بوابة من نوع ف3»،
«الخانة 4، البديل الأول»)، ومصدر البنود يعطيه أو يقول إنه غير موجود، فتُستدعى unavailable(). تستقبل
نتيجة البند بـ feed(). وتعيد أحداث المحرك بـ events()، والمشغّل يرسلها عبر Engine.apply بعد أن يسأل
Engine.preflight قبل عرض أول بند. حالة كل نشاط قاموس يُحفظ ويُستأنف (to_dict و from_dict).

ما في هذا الملف تفسير للمواصفة حيث سكتت، وكل تفسير معلَّم بكلمة «تفسير» ومسرود في المواصفة.
"""
import json
from collections import Counter

CALC = ('ف3', 'ف4')                      # بنود حساب. ما عداها بنود فهم (6.1)
SUPPORT = ('hint', 'extra_model', 'someone', 'requested')
# requested: ضغط الطفل «أحتاج مساعدة» في بوابة أو فحص، ولا يُعطى فيهما دعم. تفسير: ليست في قائمة 3.1


# ---------------------------------------------------------------- 3.1 الحقول الخمسة
def fold_item(raw, answer, assess):
    """raw: قائمة أحداث البند بترتيبها: ('confirm', قيمة)، ('support', نوع)، ('interrupt',)، ('end',).
    assess: بند بوابة أو فحص أو تحقق، ينتهي بأول تأكيد ولا محاولات بعده.
    يعيد الحقول الخمسة: status، first، support_before، later، final."""
    first, before, later, pending, last = None, [], [], [], None
    interrupted = ended = False
    for ev in raw:
        kind = ev[0]
        if ended or interrupted:
            raise ValueError('حدث بعد نهاية البند: %r' % (ev,))
        if kind == 'support':
            if ev[1] not in SUPPORT:
                raise ValueError('نوع دعم غير معروف: %r' % (ev[1],))
            pending.append(ev[1])
        elif kind == 'confirm':
            ok = ev[1] == answer
            if first is None:
                first, before = ok, pending
                if assess:
                    ended = True                    # بند التقييم ينتهي بأول تأكيد
            else:
                later.append(dict(correct=ok, support=pending))
            pending, last = [], ok
        elif kind == 'interrupt':
            interrupted = True
        elif kind == 'end':
            if first is None:
                raise ValueError('نهاية بلا إجابة مؤكَّدة: هذا انقطاع أو طلب دعم')
            ended = True
        else:
            raise ValueError('حدث بند غير معروف: %r' % (ev,))
    if not (ended or interrupted):
        raise ValueError('البند لم ينتهِ بعد')
    if first is None:
        before = pending                            # «بند طُلب فيه دعم ثم انقطع يُسجَّل منقطعًا ومعه الدعم»
    status = 'complete' if first is not None else 'interrupted'
    if first is None or interrupted:
        final = 'incomplete'
    else:
        final = 'correct' if last else 'wrong'
    return dict(status=status, first=first, support_before=before, later=later, final=final)


def correct_independent(rec):
    """«صحيحة مستقلة»: مكتمل، أول إجابة مؤكَّدة صحيحة، ولا دعم قبلها (3.1)."""
    return rec['status'] == 'complete' and rec['first'] is True and not rec['support_before']


def classify(rec):
    """النتيجة التي يحتاجها النشاط: correct، wrong، supported، help، interrupted."""
    if rec['status'] == 'interrupted':
        return 'help' if rec['support_before'] else 'interrupted'
    if rec['first'] is False:
        return 'wrong'
    return 'supported' if rec['support_before'] else 'correct'


# ---------------------------------------------------------------- 3.2 المؤشرات
def indicators(records):
    complete = [r for r in records if r['status'] == 'complete']
    used = [r for r in records if r['support_before'] or any(a['support'] for a in r['later'])]
    reached = [r for r in used if r['final'] in ('correct', 'wrong')]
    cut = [r for r in records if r['status'] == 'interrupted']

    def rate(a, b):
        return dict(num=a, den=b, value=None if b == 0 else a / b)
    return dict(
        first_answer=dict(rate(sum(1 for r in complete if r['first']), len(complete)),
                          after_support=sum(1 for r in complete if r['support_before'])),
        independent=rate(sum(1 for r in complete if correct_independent(r)), len(complete)),
        assisted=dict(rate(sum(1 for r in reached if r['final'] == 'correct'), len(reached)),
                      supported_unfinished=len(used) - len(reached)),
        interrupted=dict(count=len(cut), with_support=sum(1 for r in cut if r['support_before'])))


# ---------------------------------------------------------------- القوالب
def gate_plan(types):
    """قالب 6.1: بندان لكل نوع و5 لـ ف3، لا أقل من 6، بنود الحساب أولًا."""
    items = []
    for t in types:
        items += [t] * (5 if t == 'ف3' else 2)
    k = 0
    while len(items) < 6:
        items.append(types[k % len(types)])
        k += 1
    items.sort(key=lambda t: 0 if t in CALC else 1)
    return items


def short_types(types):
    """التحقق القصير: بند طريقة (فهم) أولًا، ثم بندا حساب. تفسير: 6.2 تقول «فيها بنود الطريقة»."""
    calc = next((t for t in types if t in CALC), types[0])
    und = next((t for t in types if t not in CALC), calc)
    return [und, calc, calc]


def opening_types(types):
    """«جرّب أولًا»: بند حساب وبند من أول أنواع المهارة. والموجَّهة: ثلاثة من أول أنواعها. تفسير."""
    calc = next((t for t in types if t in CALC), types[0])
    return [calc, types[0]], [types[0]] * 3


# ---------------------------------------------------------------- الأنشطة
class Activity:
    name = None

    def __init__(self, skill):
        self.skill, self.done, self.result = skill, False, None
        self.shown = Counter()                      # البنود المعروضة بفئاتها، للعبء

    def _finish(self, result):
        self.result, self.done = result, True

    def unavailable(self):
        raise RuntimeError('%s: لا يُطلب بديل في هذا النشاط' % self.name)

    def to_dict(self):
        return json.loads(json.dumps(dict(self.__dict__, _class=type(self).__name__), ensure_ascii=False))

    @staticmethod
    def from_dict(d):
        d = dict(d)
        cls = CLASSES[d.pop('_class')]
        obj = cls.__new__(cls)
        obj.__dict__.update(d)
        obj.shown = Counter(d['shown'])
        return obj


class GateRun(Activity):
    """بوابة الإعفاء (6.1). event='recheck_result' يجعلها إعادة تحقق (3.4). تفسير: أداة إعادة التحقق
    هي قالب البوابة نفسه، لأن نتيجتها تعيد المهارة مجتازة كالإعفاء."""
    name = 'gate'

    def __init__(self, skill, types, tolerant=True, event='gate_result', attempt=1):
        super().__init__(skill)
        self.plan, self.has_calc = gate_plan(types), any(t in CALC for t in types)
        self.tolerant, self.event, self.attempt = tolerant, event, attempt   # attempt 2: الإعادة ببنود جديدة
        self.stage, self.pos, self.errors = 'main', 0, []
        self.alt, self.cuts, self.total_cuts = {}, {}, 0
        self.alt_used, self.alt_index = {}, {}          # بدائل كل نوع المستعملة، وبديل كل موضع من بدائل نوعه

    def _key(self):
        return '%s%d' % (self.stage, self.pos)

    def _type(self):
        return self.plan[self.pos] if self.stage == 'main' else self.errors[0]

    def want(self):
        if self.done:
            return None
        k = self._key()
        return dict(activity=self.name, role='gate' if self.stage == 'main' else 'gate.compensation',
                    type=self._type(), pos=self.pos, alternate=self.alt.get(k, 0), alt_index=self.alt_index.get(k),
                    attempt=self.attempt)

    def feed(self, outcome):
        assert not self.done
        k = self._key()
        self.shown['gate' if self.stage == 'main' else 'comp'] += 1
        if outcome == 'interrupted':                 # يُستبدل ببديل من نوعه
            self.cuts[k] = self.cuts.get(k, 0) + 1
            self.total_cuts += 1
            if self.cuts[k] >= 2 or self.total_cuts >= 3:
                return self._finish('interrupted')  # تُعلَّق للمراجعة بلا نتيجة
            t = self._type()
            self.alt[k] = self.alt.get(k, 0) + 1
            self.alt_index[k] = self.alt_used.get(t, 0)
            self.alt_used[t] = self.alt_index[k] + 1
            return
        if outcome in ('help', 'supported'):
            return self._finish('help')
        if outcome == 'wrong':
            self.errors.append(self._type())
            if self.stage == 'comp' or len(self.errors) >= 2 or not self.tolerant:
                return self._finish('fail')         # الخطأ الأصلي الثاني ينهي البوابة فورًا
        self.pos += 1
        if self.stage == 'main' and self.pos == len(self.plan):
            if not self.errors:
                return self._finish('pass')
            self.stage, self.pos = 'comp', 0        # بندان جديدان من نوع الخطأ في آخر البوابة
        elif self.stage == 'comp' and self.pos == 2:
            self._finish('pass')

    def unavailable(self):
        self._finish('interrupted')                 # نفدت البدائل: كالانقطاع، بلا نتيجة

    def events(self):
        if self.event == 'recheck_result':
            return [] if self.result == 'interrupted' else [
                dict(type='recheck_result', skill=self.skill, ok=self.result == 'pass')]
        return [dict(type='gate_result', skill=self.skill, result=self.result, errors=list(self.errors),
                     has_calc=self.has_calc)]


class ShortCheckRun(Activity):
    """التحقق القصير (6.2): 3 بنود. تفسير: يتوقف عند أول بند غير صحيح مستقل، لأن النتيجة حُسمت.
    وتفسير: الانقطاع ينهيه بلا نتيجة ولا حدث، فيُعاد في جلسة لاحقة."""
    name = 'short'

    def __init__(self, skill, types, stop_early=True):
        super().__init__(skill)
        self.types, self.stop_early, self.pos, self.failed = short_types(types), stop_early, 0, False

    def want(self):
        if self.done:
            return None
        return dict(activity=self.name, role='short_check', type=self.types[self.pos], pos=self.pos, alternate=0)

    def feed(self, outcome):
        assert not self.done
        self.shown['short'] += 1
        if outcome == 'interrupted':
            return self._finish(None)
        if outcome != 'correct':
            self.failed = True
            if self.stop_early:
                return self._finish(False)
        self.pos += 1
        if self.pos == 3:
            self._finish(not self.failed)

    def events(self):
        return [] if self.result is None else [dict(type='short_check_result', skill=self.skill, ok=self.result)]


class OpeningRun(Activity):
    """افتتاح الدرس (6.2): بندا «جرّب أولًا»، ثم مثال الدرس و3 بنود موجَّهة إن لم يصحّا.
    بندا «جرّب أولًا» من نوعي الخطأ في بوابة المهارة إن أخفقت لها بوابة (try_types مع typed)، وإلا بند حساب وبند
    من أول أنواعها.
    خطأ في أجوبة البنود الموجَّهة دليل تعثّر، وطلب الدعم فيها ليس دليلًا.
    try_errors_count=True يحاكي المحاكاة القديمة: خطأ في «جرّب أولًا» يُعدّ دليل تعثّر. للمقارنة فقط.
    تفسير: البند المنقطع في الافتتاح يُعاد عرضه، لأن الافتتاح تعليم لا تقييم.
    وتفسير: البند المدعوم في الموجَّهة ليس «صحيحًا مستقلًا» ولا خطأ، فيمضي الدرس كاملًا بلا دليل كطلب الدعم."""
    name = 'opening'

    def __init__(self, skill, types, try_types=None, try_errors_count=False, typed=False):
        super().__init__(skill)
        self.try_types, self.guided = opening_types(types)
        if try_types:
            self.try_types = list(try_types)
        # typed: النوعان من أخطاء بوابة المهارة (6.2)، فيُطلب البند بنوعه وترتيبه بين بنود نوعه
        self.typed = bool(typed and try_types)
        self.try_errors_count = try_errors_count
        self.stage, self.pos, self.try_out, self.reshown = 'try', 0, [], 0

    def want(self):
        if self.done:
            return None
        t = self.try_types[self.pos] if self.stage == 'try' else self.guided[self.pos]
        w = dict(activity=self.name, role='opening.try' if self.stage == 'try' else 'opening.guided',
                 type=t, pos=self.pos, alternate=0, reshown=self.reshown)
        if self.stage == 'try' and self.typed:
            w.update(typed=True, type_index=self.try_types[:self.pos].count(t))
        return w

    def feed(self, outcome):
        assert not self.done
        self.shown['try' if self.stage == 'try' else 'lesson'] += 1
        if outcome == 'interrupted':
            self.reshown += 1
            return
        self.reshown = 0
        if self.stage == 'try':
            self.try_out.append(outcome)
            self.pos += 1
            if self.pos == 2:
                if all(o == 'correct' for o in self.try_out):
                    return self._finish('skip')
                self.stage, self.pos = 'guided', 0
            return
        if outcome == 'correct':
            self.pos += 1
            if self.pos == 3:
                self._finish('skip')                # انتهى الدرس مبكرًا
            return
        if outcome == 'wrong' or (self.try_errors_count and 'wrong' in self.try_out):
            return self._finish('full_error')
        self._finish('full_help')

    def events(self):
        return [dict(type='lesson_opening_result', skill=self.skill, outcome=self.result)]


class EvidenceRun(Activity):
    """دليل الفهم (3.5): لكل نوع بندان جديدان «صحيحان مستقلان». الإخفاق في بند يستدعي درسًا قصيرًا ثم
    بندين جديدين من نوعه. تفسيرات: الأنواع بترتيبها في جدول المهارة؛ البند المدعوم لا يُحسب ويُعامل
    كالإخفاق؛ إخفاق البندين الاحتياطيين ينهي الجولة بلا دليل؛ النوع الذي ثبت يبقى ثابتًا في الدرس نفسه
    (proven)؛ البند المنقطع يُعاد عرضه."""
    name = 'evidence'

    def __init__(self, skill, types, proven=(), round=1):
        super().__init__(skill)
        self.types, self.proven = list(types), [t for t in types if t in proven]
        self.round = round                          # الجولة: لكل جولة بنود جديدة (3.5)
        self.stage, self.pos, self.failed, self.short_lessons, self.reshown = 'first', 0, None, 0, 0
        if self._current() is None:
            self._finish('proven')

    def _current(self):
        return next((t for t in self.types if t not in self.proven), None)

    def want(self):
        if self.done:
            return None
        return dict(activity=self.name, role='evidence' if self.stage == 'first' else 'evidence.reserve',
                    type=self._current(), pos=self.pos, alternate=0, reshown=self.reshown, round=self.round,
                    short_lesson_before=self.stage == 'reserve' and self.pos == 0)

    def feed(self, outcome):
        assert not self.done
        self.shown['evidence'] += 1
        if outcome == 'interrupted':
            self.reshown += 1
            return
        self.reshown = 0
        t = self._current()
        if outcome == 'correct':
            self.pos += 1
            if self.pos == 2:
                self.proven.append(t)
                self.stage, self.pos = 'first', 0
                if self._current() is None:
                    self._finish('proven')
            return
        if self.stage == 'first':
            self.stage, self.pos = 'reserve', 0
            self.short_lessons += 1
            return
        self.failed = t
        self._finish('not_proven')

    def unavailable(self):
        self.failed = self._current()
        self._finish('no_items')                    # لا بنود جديدة في البنك: يحتاج مراجعة المعلم

    def events(self):
        return [dict(type='understanding_proved', skill=self.skill)] if self.result == 'proven' else []


class CheckRun(Activity):
    """فحص الاستقلال (3.6): 10 خانات، يُجتاز بـ 9 «صحيحة مستقلة»، بلا تغذية راجعة.
    طلب الدعم يغلق المحاولة «انتهت بطلب دعم». البند المنقطع يُستبدل ببديل خانته. انقطاعان في خانة، أو 3 في
    الفحص، أو نفاد بدائل خانة، أو لا بنود لهذه المحاولة: يُعلَّق «للمراجعة» بحدث check_held وسببه، بلا نتيجة،
    والمحرك لا يستأنفه ولا يقبل نتيجته حتى يتركه المعلم (check_abandoned). تفسير: الفحص يكمل خاناته العشر
    بعد أن تتعذر 9 صحيحة، لأن التوقف المبكر تغذية راجعة ضمنية."""
    name = 'check'

    def __init__(self, skill, check_id, content_version, attempt='A', slots=10, need=9):
        super().__init__(skill)
        self.check_id, self.content_version, self.attempt = check_id, content_version, attempt
        self.slots, self.need = slots, need
        self.slot, self.correct, self.answers = 1, 0, {}
        self.alt, self.cuts, self.total_cuts, self.hold = {}, {}, 0, None

    def want(self):
        if self.done:
            return None
        a = self.alt.get(str(self.slot), 0)
        return dict(activity=self.name, role='check' if a == 0 else 'check.alternate', slot=self.slot,
                    alternate=a, attempt=self.attempt)

    def feed(self, outcome):
        assert not self.done
        self.shown['check'] += 1
        k = str(self.slot)
        if outcome == 'interrupted':
            self.cuts[k] = self.cuts.get(k, 0) + 1
            self.total_cuts += 1
            if self.cuts[k] >= 2 or self.total_cuts >= 3:
                return self._hold('interruptions')
            self.alt[k] = self.alt.get(k, 0) + 1
            return
        if outcome in ('help', 'supported'):
            self.answers[k] = 'help'
            return self._finish('help')
        self.answers[k] = outcome
        self.correct += outcome == 'correct'
        self.slot += 1
        if self.slot > self.slots:
            self._finish('pass' if self.correct >= self.need else 'fail')

    def _hold(self, why):
        self.hold = why
        self._finish('held')

    def unavailable(self):
        self._hold('no_alternate' if self.alt.get(str(self.slot), 0) else 'no_items')   # لا بنود لهذه المحاولة

    def start_event(self):
        return dict(type='check_started', skill=self.skill, check_id=self.check_id,
                    content_version=self.content_version)

    def events(self):
        if self.result == 'held':
            return [dict(type='check_held', skill=self.skill, check_id=self.check_id, reason=self.hold)]
        return [dict(type='independence_result', skill=self.skill, check_id=self.check_id, result=self.result)]


class RetentionRun(Activity):
    """فحص الاحتفاظ (3.7): 5 بنود جديدة بلا تمهيد وبلا تغذية راجعة، ويُعدّ منها «الصحيح المستقل».
    تفسيران: البند المدعوم أو المنتهي بطلب دعم لا يُحسب صحيحًا ويمضي الفحص؛ والانقطاع ينهيه بلا نتيجة ولا حدث،
    كالتحقق القصير، فيُعاد في جلسة لاحقة."""
    name = 'retention'

    def __init__(self, skill, round, size=5):
        super().__init__(skill)
        self.round, self.size, self.pos, self.correct = round, size, 0, 0

    def want(self):
        if self.done:
            return None
        return dict(activity=self.name, role='deferred_check', round=self.round, pos=self.pos, alternate=0)

    def feed(self, outcome):
        assert not self.done
        self.shown['retention'] += 1
        if outcome == 'interrupted':
            return self._finish(None)
        self.correct += outcome == 'correct'
        self.pos += 1
        if self.pos == self.size:
            self._finish('done')

    def events(self):
        return [] if self.result is None else [dict(type='retention_result', skill=self.skill, correct=self.correct)]


CLASSES = {c.__name__: c for c in (GateRun, ShortCheckRun, OpeningRun, EvidenceRun, CheckRun, RetentionRun)}


# ---------------------------------------------------------------- التشغيل
def drive(act, source, answer, records=None, pause=None):
    """يعرض بنود النشاط حتى ينتهي. source(skill, want) يعيد البند أو None. answer(item, want) يعيد أحداث
    البند الخام وجوابه الصحيح ونوع البند، أو نتيجة جاهزة (للمحاكاة).
    pause(want) تُسأل بعد كل بند اكتمل: إن أعادت صحيحًا توقف العرض والنشاط غير منتهٍ، ليُحفظ ويُستأنف في جلسة
    لاحقة. بها يُنفَّذ سقف الوقت الذي لا يقطع بندًا جاريًا (7.1)."""
    while True:
        w = act.want()
        if w is None:
            return act
        item = source(act.skill, w)
        if item is None:
            act.unavailable()
            continue
        got = answer(item, w)
        if isinstance(got, str):
            act.feed(got)
            if pause and pause(w) and not act.done:
                return act
            continue
        raw, correct, assess = got
        rec = fold_item(raw, correct, assess)
        if records is not None:
            r = dict(rec, skill=act.skill, activity=act.name, role=w['role'],
                     item=item.get('id') if isinstance(item, dict) else None)
            if isinstance(item, dict) and item.get('reshown_same_fact'):
                r['reshown_after_interrupt'] = True        # 3.6: «أُعيد عرضه بعد انقطاع»
            records.append(r)
        act.feed(classify(rec))
        if pause and pause(w) and not act.done:
            return act
