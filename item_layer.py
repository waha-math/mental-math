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
    يعيد الحقول الخمسة: status، first، support_before، later، final، ومعها support_unanswered: الدعم الذي جاء بعد
    آخر إجابة مؤكَّدة ولم تتبعه إجابة. يُحفظ كل دعم فور حدوثه، ولو انقطع البند قبل الإجابة التالية (3.1)."""
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
    unanswered = []
    if first is None:
        before = pending                            # «بند طُلب فيه دعم ثم انقطع يُسجَّل منقطعًا ومعه الدعم»
    else:
        unanswered = pending                        # دعم بعد آخر إجابة، لم تتبعه إجابة: لا يُنقل إلى ما قبل الأولى
    status = 'complete' if first is not None else 'interrupted'
    if first is None or interrupted:
        final = 'incomplete'
    else:
        final = 'correct' if last else 'wrong'
    return dict(status=status, first=first, support_before=before, later=later, final=final,
                support_unanswered=unanswered)


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
def evidence(raw, key, v=None):
    """ما وقع في البند كما وقع، لتدقيق النتيجة لاحقًا (ك2 في مراجعة 04e0168، وهو P0-04): الجواب الذي صُحّح به (key)،
    وقيم الإجابات المؤكدة بترتيبها (values)، وأنواع الدعم بترتيبها (support)، وبصمة تعريف البند (v) إن عُرفت.
    الحقول الخمسة المطوية (fold_item) تُشتق من هذه ولا تغني عنها: منها يُعرف هل الإجابة صحيحة، لا ما هي."""
    d = dict(key=key, values=[ev[1] for ev in raw if ev[0] == 'confirm'],
             support=[ev[1] for ev in raw if ev[0] == 'support'])
    if v is not None:
        d['v'] = v
    return d


def indicators(records, invalid=()):
    """النجاح بمساعدة: البنود التي سبق دعمٌ إحدى إجاباتها وبلغت نتيجة نهائية. والمدعومة غير المكتملة: كل بند فيه
    دعم، في أي موضع، ونتيجته النهائية غير مكتملة، ويُعدّ مرة واحدة. الدعم بعد آخر إجابة في بند انتهى بنتيجة
    يُحفظ ولا يدخل المؤشرين، لأن الإجابة لم تأتِ بعده.
    والسجل المستبعد (void: بند توقف نشاطه لتغيّر صلاحيته، R17-01) تاريخ محفوظ لا يدخل أي مؤشر.
    invalid: معرّفات الجلسات المبطلة (ك2). سجل بند من جلسة مبطلة يبقى في التاريخ ولا يدخل أي مؤشر. والسجل الذي لا
    يحمل معرّف جلسته لا يُنسب تخمينًا: يبقى في المؤشرات. أعداد المستبعد وغير المنسوب في left_out."""
    invalid = set(invalid)
    records = [r for r in records if not r.get('void') and r.get('session') not in invalid]
    complete = [r for r in records if r['status'] == 'complete']
    used = [r for r in records if r['support_before'] or any(a['support'] for a in r['later'])]
    reached = [r for r in used if r['final'] in ('correct', 'wrong')]
    unfinished = [r for r in records if r['final'] == 'incomplete' and (
        r['support_before'] or r.get('support_unanswered') or any(a['support'] for a in r['later']))]
    cut = [r for r in records if r['status'] == 'interrupted']

    def rate(a, b):
        return dict(num=a, den=b, value=None if b == 0 else a / b)
    return dict(
        first_answer=dict(rate(sum(1 for r in complete if r['first']), len(complete)),
                          after_support=sum(1 for r in complete if r['support_before'])),
        # «أداء بعد تعرض مباشر» (ت2) إجابة أولى صحيحة، وليس صحيحًا مستقلًا
        independent=rate(sum(1 for r in complete if correct_independent(r) and not r.get('after_exposure')),
                         len(complete)),
        assisted=dict(rate(sum(1 for r in reached if r['final'] == 'correct'), len(reached)),
                      supported_unfinished=len(unfinished)),
        interrupted=dict(count=len(cut), with_support=sum(1 for r in cut if r['support_before'])))


def left_out(records, invalid=()):
    """ما لا تحسبه المؤشرات ولماذا، ليبقى التقرير قابلًا للمراجعة (ك2): void سجلات استُبعدت لتغيّر صلاحية نشاطها،
    session سجلات جلسات أُبطلت، و unlinked سجلات بلا معرّف جلسة (قبل نسخة السجل 5): تُحسب في المؤشرات لأنها لا
    تُنسب إلى جلسة تخمينًا، ويُذكر عددها «سجل قديم ناقص النسبة»."""
    invalid = set(invalid)
    live = [r for r in records if not r.get('void')]
    return dict(void=len(records) - len(live), session=sum(1 for r in live if r.get('session') in invalid),
                unlinked=sum(1 for r in live if r.get('session') is None))


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
ALT_PEEK = 8                                        # أقصى عدد بدائل يُسأل عنها لنوع عند تأخير بند


class Activity:
    name = None

    def __init__(self, skill):
        self.skill, self.done, self.result = skill, False, None
        self.shown = Counter()                      # البنود المعروضة بفئاتها، للعبء

    def _finish(self, result):
        self.result, self.done = result, True

    def unavailable(self):
        raise RuntimeError('%s: لا يُطلب بديل في هذا النشاط' % self.name)

    def repeated(self, item_id, fact_at=None):
        """أول بند يُطلب للنشاط حقيقته حقيقة آخر بند عُرض للمهارة نفسها في الجلسة نفسها من نشاط آخر (R22-01).
        تعيد صحيحًا إن غيّر النشاط ما يطلبه (فيُطلب من جديد)، وغير ذلك إن عُرض البند كما هو، فيوسَم بأن حقيقته
        عُرضت للتو. الأنشطة التي لها علاج تعيد تعريفها. fact_at(want): حقيقة البند الذي يُعرض لطلب، دون عرضه."""
        return False

    def _defer(self, pos, last, key, plain, after, fact_at, alts=None):
        """علاج أنشطة التقييم (قرار الأب، 18 نوفمبر): البند الذي يكرر حقيقة ما عُرض قبله يُؤخَّر، ولا يُستبدل. تُعرض
        البنود التي تليه في مرحلته، ثم يُعرض هو عند أقرب موضع لا تجاور فيه حقيقتُه حقيقةَ بند الموضع الذي قبله ولا
        ما بعده. تبقى هوية البنود وخاناتها، ويتغير ترتيب عرضها. قاعدة التوقف تُطبَّق على ترتيب العرض الفعلي، فقد
        يغيّر التأخير البنود التي يصل إليها الطفل وسبب انتهاء النشاط (ت1 في مراجعة 04e0168). pos موضع الترتيب الجاري و last آخر موضع في مرحلته، و key(q)
        مفتاح الموضع، و plain(q) ما يُطلب لبند موضع بلا بديل، و after(q) ما قد يُعرض بعد موضع q: بند الموضع التالي،
        أو أول بنود المرحلة التالية إن كان q آخر مرحلته. fact_at(want): حقيقة بند دون عرضه. alts(q): بدائل بند موضع
        عند الانقطاع: بديل المؤجَّل، إن انقطع في موضعه الجديد، لا تجاور حقيقتُه ما بعده.
        البند المؤجَّل قد يُؤخَّر ثانية إن كرر عند موضعه الجديد حقيقة ما عُرض قبله (بديل بند انقطع مثلًا)، فالفحص
        يجري قبل كل بند تقييم لا عند الدخول وحده (drive_steps).
        تعيد غير صحيح إن لم يوجد موضع، أو كان موضع لاحق طرفًا في تأخير سابق: يُعرض البند موسومًا. الحقل defer لا
        يُنشأ إلا عند التأخير: مفاتيحه مواضع الترتيب، وقيمه مواضع البنود التي تُعرض فيها."""
        if fact_at is None or pos >= last:
            return False
        d = getattr(self, 'defer', {})
        cur = d.get(key(pos), pos)                  # موضع البند المعروض الآن: قد يكون مؤجَّلًا من قبل
        fact = fact_at(plain(cur))
        if fact is None or any(key(q) in d for q in range(pos + 1, last + 1)) or fact_at(plain(pos + 1)) == fact:
            return False
        mine = {tuple(f) for f in (fact_at(w) for w in (alts(cur) if alts else ())) if f is not None} | {tuple(fact)}
        for j in range(1, last - pos + 1):
            if fact_at(plain(pos + j)) == fact or any(tuple(fact_at(w) or ()) in mine for w in after(pos + j)):
                continue
            new = {key(pos + i): pos + i + 1 for i in range(j)}
            new[key(pos + j)] = cur
            self.__dict__.setdefault('defer', {}).update(new)
            return True
        return False

    def _at(self, key, pos):
        return getattr(self, 'defer', {}).get(key, pos)

    def voided(self, item_id, exposed):
        """البند المعروض استُبعد لتغيّر صلاحية النشاط (R17-01). exposed: هل أُجيب عنه أو طُلب فيه دعم قبل التغيّر؟
        الاستبعاد من التقييم لا يمحو التعرّض (R18-01). الأنشطة التي يغيّر التعرّض بندها التالي تعيد تعريفها.
        تعيد صحيحًا إن كان البند لا يُعرض ثانية (يُطلب غيره)، وغير ذلك إن جاز عرضه."""

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

    def _p(self):                                   # موضع البند المعروض الآن: موضع الترتيب، إلا إن أُخّر بند (defer)
        return self._at('%s%d' % (self.stage, self.pos), self.pos)

    def _key(self):
        return '%s%d' % (self.stage, self._p())

    def _type(self):
        return self.plan[self._p()] if self.stage == 'main' else self.errors[0]

    def _plain(self, q, stage=None, t=None):        # ما يُطلب لموضع في مرحلة بلا بديل
        stage = stage or self.stage
        return dict(activity=self.name, role='gate' if stage == 'main' else 'gate.compensation',
                    type=t or (self.plan[q] if stage == 'main' else self.errors[0]), pos=q, alternate=0,
                    alt_index=None, attempt=self.attempt)

    def repeated(self, item_id, fact_at=None):
        if self.alt.get(self._key()):               # بديل بند منقطع: ليس بند موضعه، فلا يُؤخَّر
            return False
        last = len(self.plan) - 1 if self.stage == 'main' else 1

        def after(q):                               # ما بعد آخر المرحلة (أول التعويضية) يُفحص عند عرضه، لا هنا
            return [self._plain(q + 1)] if q < last else []
        return self._defer(self.pos, last, lambda q: '%s%d' % (self.stage, q), self._plain, after, fact_at,
                           lambda q: [dict(self._plain(q), role='gate.alternate', alternate=1, alt_index=k)
                                      for k in range(ALT_PEEK)])

    def want(self):
        if self.done:
            return None
        k = self._key()
        return dict(activity=self.name, role='gate' if self.stage == 'main' else 'gate.compensation',
                    type=self._type(), pos=self._p(), alternate=self.alt.get(k, 0), alt_index=self.alt_index.get(k),
                    attempt=self.attempt)

    def feed(self, outcome):
        assert not self.done
        k = self._key()
        self.shown['gate' if self.stage == 'main' else 'comp'] += 1
        if outcome in ('interrupted', 'exposed'):   # يُستبدل ببديل من نوعه
            # exposed (ت2): إجابة صحيحة عن حقيقة عُرضت للتو. أداء بعد تعرض مباشر، لا دليل: تُستكمل الخانة ببديل نوعها.
            # ليست انقطاعًا، فلا تدخل عدّ الانقطاعات. ونفاد البدائل يعلّق البوابة بلا نتيجة (unavailable)، لا إخفاق
            if outcome == 'interrupted':
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
        p = self._at(str(self.pos), self.pos)
        return dict(activity=self.name, role='short_check', type=self.types[p], pos=p, alternate=0)

    def repeated(self, item_id, fact_at=None):
        def w(q):
            return dict(activity=self.name, role='short_check', type=self.types[q], pos=q, alternate=0)
        return self._defer(self.pos, 2, str, w, lambda q: [w(q + 1)] if q < 2 else [], fact_at)

    def feed(self, outcome):
        assert not self.done
        self.shown['short'] += 1
        if outcome in ('interrupted', 'exposed'):   # exposed (ت2): لا بدائل هنا، فبلا نتيجة ويُعاد في جلسة لاحقة
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
    وتفسير: البند المدعوم في الموجَّهة ليس «صحيحًا مستقلًا» ولا خطأ، فيمضي الدرس كاملًا بلا دليل كطلب الدعم.
    البند المستهلك (أُجيب عنه أو طُلب فيه دعم ثم استُبعد لتغيّر الصلاحية، R18-01): إعادته للتعليم غير استعماله دليلًا
    لقرار. بند «جرّب أولًا» المستهلك لا بديل له، فلا يُعرض ثانية ونتيجته void: لا يتخطى الشرح ولا يُعدّ خطأ. والبند
    الموجَّه المستهلك يُعاد عرضه للتعليم موسومًا بأنه مكرر، ونتيجته أيًّا كانت لا تُستعمل: لا ينهي الدرس مبكرًا ولا
    يُسجَّل تعثّرًا، فيمضي الدرس كاملًا (full_help). الحقلان spent و taint لا يُنشآن إلا عند الاستبعاد."""
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
            k = self.try_types[:self.pos].count(t)
            if getattr(self, 'flip', {}).get(t):    # لكل نوع بندان: بدأ بالثاني لأن الأول يكرر حقيقة ما عُرض للتو
                k = 1 - k
            w.update(typed=True, type_index=k)
        return w

    def repeated(self, item_id, fact_at=None):
        """R22-01: بند الافتتاح الأول يكرر حقيقة آخر بند عُرض (آخر بند في البوابة مثلًا). في «جرّب أولًا» بنوعي الخطأ
        يُبدأ بالبند الآخر من نوعه. وإن لم يكن له آخر، أو كرر الآخر الحقيقة أيضًا، لا يُعرض ونتيجته void: لا يُتخذ منه
        قرار اختصار ولا يُعدّ خطأ. والبند الموجَّه يُعرض للتعليم ولا تُستعمل نتيجته."""
        if self.stage == 'guided':
            self.__dict__['taint'] = item_id
            return False
        t = self.try_types[self.pos]
        if self.typed and not getattr(self, 'flip', {}).get(t) and self.try_types[:self.pos].count(t) == 0:
            self.__dict__.setdefault('flip', {})[t] = True
            return True
        self.try_out.append('void')
        self.reshown = 0
        self._after_try()
        return True

    def voided(self, item_id, exposed):
        if not exposed:
            self.reshown += 1
            return False
        if self.stage == 'guided':
            self.__dict__['taint'] = item_id
            return False
        spent = self.__dict__.setdefault('spent', [])
        if item_id not in spent:
            spent.append(item_id)
            self.try_out.append('void')
            self.reshown = 0
            self._after_try()
        return True

    def _after_try(self):
        self.pos += 1
        if self.pos == 2:
            if all(o == 'correct' for o in self.try_out):
                return self._finish('skip')
            self.stage, self.pos = 'guided', 0

    def feed(self, outcome):
        assert not self.done
        self.shown['try' if self.stage == 'try' else 'lesson'] += 1
        if outcome == 'interrupted':
            self.reshown += 1
            return
        self.reshown = 0
        if self.stage == 'guided' and self.__dict__.pop('taint', None):
            return self._finish('full_help')        # بند مكرر عُرض للتعليم: نتيجته ليست دليلًا لقرار
        if self.stage == 'try':
            self.try_out.append(outcome)
            return self._after_try()
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
    (proven)؛ البند المنقطع يُعاد عرضه.
    البند المستبعد لتغيّر الصلاحية (R18-01): إن لم يقع فيه إلا العرض أُعيد عرضه كالمنقطع، فلم تُقبل فيه إجابة في محاولة
    صالحة. وإن
    أُجيب عنه أو طُلب فيه دعم فقد استُهلك: لا يُحتسب إخفاقًا ولا يُعرض ثانية، ويُطلب لموضعه بديل نوعه في الجولة
    (evidence.alternate). إن لم يوجد البديل انتهت الجولة no_alternate بلا حكم. الحقلان swap و spent لا يُنشآن إلا
    عند أول استبعاد، فلا تتغير صورة النشاط المحفوظ في غير ذلك."""
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
        w = dict(activity=self.name, role='evidence' if self.stage == 'first' else 'evidence.reserve',
                 type=self._current(), pos=self.pos, alternate=0, reshown=self.reshown, round=self.round,
                 short_lesson_before=self.stage == 'reserve' and self.pos == 0)
        swap = getattr(self, 'swap', {}).get(self._key())
        if swap:                                    # موضع استُهلك بنده: بديل النوع، ومعه البند الذي يحل محله
            w.update(role='evidence.alternate', alternate=swap['n'], replaces=swap['item'])
        return w

    def _key(self):
        return '%s/%s/%d' % (self._current(), self.stage, self.pos)

    def repeated(self, item_id, fact_at=None):
        """R22-01: أول بند يُطلب عند دخول دليل الفهم يكرر حقيقة آخر بند عُرض من نشاط آخر: لا يُعرض الآن، ويُطلب لموضعه
        بديل نوعه في الجولة. وإن لم يوجد بديل، أو كرر الحقيقة هو أيضًا، انتهت الجولة no_alternate بلا حكم."""
        swap = self.__dict__.setdefault('swap', {})
        t = self._current()
        swap[self._key()] = dict(n=1 + sum(1 for k in swap if k.split('/')[0] == t), item=item_id)
        return True

    def voided(self, item_id, exposed):
        if not exposed:
            self.reshown += 1
            return False
        swap, spent = self.__dict__.setdefault('swap', {}), self.__dict__.setdefault('spent', [])
        if item_id in spent:                        # سُجّل عند التوقف، ثم وجده تاريخ السجلات عند الاستئناف: مرة واحدة
            return True
        spent.append(item_id)
        t = self._current()
        swap[self._key()] = dict(n=1 + sum(1 for k in swap if k.split('/')[0] == t), item=item_id)
        self.reshown = 0
        return True

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
        if getattr(self, 'swap', {}).get(self._key()):
            self._finish('no_alternate')            # لا بديل لبند استُهلك: بلا حكم، ويظهر للبالغ. لا يُعاد البند سرًا
            return
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
        a = self.alt.get(self._k(), 0)
        return dict(activity=self.name, role='check' if a == 0 else 'check.alternate', slot=int(self._k()),
                    alternate=a, attempt=self.attempt)

    def _k(self):                                   # خانة البند المعروض الآن: خانة الترتيب، إلا إن أُخّر بند (defer)
        return str(self._at(str(self.slot), self.slot))

    def repeated(self, item_id, fact_at=None):
        if self.alt.get(self._k()):                 # بديل بند منقطع: ليس بند خانته، فلا يُؤخَّر
            return False
        def w(q):
            return dict(activity=self.name, role='check', slot=q, alternate=0, attempt=self.attempt)
        return self._defer(self.slot, self.slots, str, w, lambda q: [w(q + 1)] if q < self.slots else [], fact_at,
                           lambda q: [dict(w(q), role='check.alternate', alternate=1)])

    def feed(self, outcome):
        assert not self.done
        self.shown['check'] += 1
        k = self._k()
        if outcome == 'exposed':                    # ت2: تُستكمل الخانة ببديلها، بلا عدّ انقطاع. ولا بديل: تعليق للمراجعة
            if self.alt.get(k, 0):                  # للخانة بديل واحد وقد عُرض: لا يُعاد عرضه، ولا يُعدّ إخفاقًا
                return self._hold('no_alternate')
            self.alt[k] = 1
            return
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
        self._hold('no_alternate' if self.alt.get(self._k(), 0) else 'no_items')   # لا بنود لهذه المحاولة

    def start_event(self):
        return dict(type='check_started', skill=self.skill, check_id=self.check_id,
                    content_version=self.content_version)

    def events(self):
        if self.result == 'held':
            return [dict(type='check_held', skill=self.skill, check_id=self.check_id, reason=self.hold)]
        return [dict(type='independence_result', skill=self.skill, check_id=self.check_id, result=self.result)]


class RetentionRun(Activity):
    """فحص الاحتفاظ (3.7): 5 بنود جديدة بلا تمهيد وبلا تغذية راجعة، ويُعدّ منها «الصحيح المستقل».
    طلب المساعدة ينهي الجولة بلا حكم احتفاظ ولا يُعدّ إخفاقًا (قرار الأب في 18 نوفمبر، ت3 في مراجعة 04e0168): النتيجة
    help وحدثها retention_help، لا retention_result. كان النص هنا «يمضي الفحص»، فدعمٌ ثم أربع إجابات صحيحة يعطي 4 من 5.
    attempt: 1 لبنود الجولة الأصلية، وما فوقه لبنود بديلة بعد طلب مساعدة. الحقل لا يُنشأ إلا لما فوق 1. وإن لم تتوفر
    بدائل: النتيجة no_alternate وحدثها retention_referred، إحالة إلى البالغ بلا إخفاق.
    والانقطاع ينهيه بلا نتيجة ولا حدث،
    كالتحقق القصير، فيُعاد في جلسة لاحقة."""
    name = 'retention'

    def __init__(self, skill, round, size=5, attempt=1):
        super().__init__(skill)
        self.round, self.size, self.pos, self.correct = round, size, 0, 0
        if attempt != 1:
            self.attempt = attempt

    def _w(self, q):
        a = getattr(self, 'attempt', 1) - 1
        return dict(activity=self.name, role='deferred_check.alternate' if a else 'deferred_check', round=self.round,
                    pos=q, alternate=a)

    def want(self):
        if self.done:
            return None
        return self._w(self._at(str(self.pos), self.pos))

    def repeated(self, item_id, fact_at=None):
        w = self._w
        return self._defer(self.pos, self.size - 1, str, w, lambda q: [w(q + 1)] if q < self.size - 1 else [],
                           fact_at)

    def unavailable(self):
        if getattr(self, 'attempt', 1) == 1:
            raise RuntimeError('%s: لا بنود لجولة الاحتفاظ %r' % (self.name, self.round))
        self._finish('no_alternate')                # لا بدائل مناسبة: يُحال القرار إلى البالغ، بلا إخفاق

    def feed(self, outcome):
        assert not self.done
        self.shown['retention'] += 1
        if outcome in ('interrupted', 'exposed'):   # exposed (ت2): بلا نتيجة، وتُعاد الجولة في جلسة لاحقة
            return self._finish(None)
        if outcome in ('help', 'supported'):
            return self._finish('help')
        self.correct += outcome == 'correct'
        self.pos += 1
        if self.pos == self.size:
            self._finish('done')

    def events(self):
        if self.result == 'done':
            return [dict(type='retention_result', skill=self.skill, correct=self.correct)]
        if self.result == 'help':
            return [dict(type='retention_help', skill=self.skill, round=self.round)]
        if self.result == 'no_alternate':
            return [dict(type='retention_referred', skill=self.skill, round=self.round)]
        return []


CLASSES = {c.__name__: c for c in (GateRun, ShortCheckRun, OpeningRun, EvidenceRun, CheckRun, RetentionRun)}
ASSESSING = ('gate', 'short', 'check', 'retention')         # أنشطة التقييم: علاج تكرار الحقيقة فيها تأخير البند


# ---------------------------------------------------------------- التشغيل
def exposure(records, skill, activity):
    """تاريخ التعرّض لبنود نشاط مهارة من السجلات المستبعدة (void) وحدها: لكل بند هل أُجيب عنه أو طُلب فيه دعم قبل
    استبعاده (exposed)، وكم مرة استُبعد (n). السجلات باقية بعد إسقاط النشاط وإنشاء غيره وبعد الحفظ والاستعادة، فهي
    المرجع، لا حالة كائن النشاط (R19-01)."""
    out = {}
    for r in records or ():
        if r.get('void') and r.get('item') and r['skill'] == skill and r['activity'] == activity:
            h = out.setdefault(r['item'], dict(exposed=False, n=0))
            h['n'] += 1
            if r['first'] is not None or r.get('support_before') or r.get('support_unanswered'):
                h['exposed'] = True
    return out


def peek_fact(source, skill, want):
    """حقيقة البند الذي يعرضه المصدر لطلب، دون عرضه: الطلب يحمل peek فلا يُعدّ البند معروضًا."""
    it = source(skill, dict(want, peek=True))
    return list(it['fact']) if isinstance(it, dict) and it.get('fact') is not None else None


def drive_steps(act, source, records=None, pause=None, history=None, prev=None):  # noqa: C901
    """مولّد يعرض بنود النشاط حتى ينتهي. source(skill, want) يعيد البند أو None. يعطي (البند، المطلوب) ويستقبل
    أحداث البند الخام وجوابه الصحيح ونوع البند، أو نتيجة جاهزة (للمحاكاة).
    pause(want) تُسأل بعد كل بند اكتمل: إن أعادت صحيحًا توقف العرض والنشاط غير منتهٍ، ليُحفظ ويُستأنف في جلسة
    لاحقة. بها يُنفَّذ سقف الوقت الذي لا يقطع بندًا جاريًا (7.1)."""
    entry = True                                            # أول بند يُعرض في هذا الدخول إلى النشاط
    inner = None                                            # آخر بند عُرض من هذا النشاط في هذا الدخول، إن احتُسب تعرّضًا
    moved = []                                              # بنود تقييم أُخّرت قبل البند الذي سيُعرض الآن
    while True:
        w = act.want()
        if w is None:
            return act
        item = source(act.skill, w)
        if item is None:
            act.unavailable()
            continue
        # history(act): تاريخ التعرّض لبنود هذا النشاط (exposure). بند استُهلك من قبل لا يُعرض ثانية ولو أُنشئ النشاط
        # من جديد: يُطلب بديله. وبند عُرض ولم تُقبل فيه إجابة في محاولة صالحة يُعاد عرضه موسومًا بالإعادة (R19-01)
        h = history(act).get(item.get('id')) if history and isinstance(item, dict) else None
        if h and h['exposed'] and act.voided(item['id'], True):
            continue
        if h:                                               # يُعرض ثانية: موسوم بالإعادة، وبأنه مكرر إن كان مستهلكًا
            w = dict(w, reshown=max(w.get('reshown', 0), h['n']))
            if h['exposed']:
                w['repeated'] = True
        # prev(): آخر بند عُرض للمهارة نفسها في الجلسة نفسها من نشاط آخر، (معرّفه، حقيقته)، إن كان يُحتسب تعرّضًا.
        # الحقيقة نفسها لا تُعرض في بندين متتاليين (3.5) ولو كانا من نشاطين (R22-01): النشاط يغيّر ما يطلبه إن كان له
        # علاج، وإلا عُرض البند موسومًا بأن حقيقته عُرضت للتو. داخل النشاط الواحد يضمن المحتوى ذلك (content_sequence)
        # وفي أنشطة التقييم العلاج تأخير البند، والتأخير يغيّر الترتيب الذي ضمنه المحتوى، فيُفحص كل بند فيها مع
        # البند الذي عُرض قبله من النشاط نفسه أيضًا (بديل بند انقطع قد يجاور بندًا مؤجَّلًا)
        facted = isinstance(item, dict) and item.get('fact') is not None
        p = prev() if entry and prev and facted else inner if facted and act.name in ASSESSING else None
        if p and p[0] != item['id'] and list(p[1]) == list(item['fact']):
            if act.repeated(item['id'], lambda q: peek_fact(source, act.skill, q)):
                if act.name in ASSESSING:
                    moved.append(item['id'])
                continue
            w = dict(w, fact_just_seen=p[0])
        if moved:                                           # يُحفظ أن الترتيب تغيّر ولماذا: هذا البند عُرض قبل ما أُخّر
            w, moved = dict(w, ahead_of=moved), []
        entry = False
        got = yield item, w
        if facted:                                          # قاعدة Scheduler.seen نفسها: المنقطع بلا إجابة ولا دعم لا يُحتسب
            raw = None if isinstance(got, str) else got[0]
            counts = got != 'interrupted' if raw is None else (
                any(ev[0] in ('confirm', 'support') for ev in raw) or not (raw and raw[-1][0] == 'interrupt'))
            inner = (item['id'], item['fact']) if counts else None
        else:
            inner = None
        # ت2 (قرار الأب في 18 نوفمبر): الإجابة الصحيحة عن حقيقة عُرضت للتو أداءٌ بعد تعرض مباشر. في أنشطة التقييم لا
        # تُعطى للنشاط دليلًا: نتيجتها exposed، فيستكمل النشاط خانتها ببند مستقل لاحق أو ينتهي بلا حكم. الخطأ وطلب
        # الدعم كما هما. وفي أنشطة التعليم للبند الموسوم علاجه (taint في الافتتاح)
        weak = bool(w.get('fact_just_seen')) and act.name in ASSESSING
        if isinstance(got, str):
            act.feed('exposed' if weak and got == 'correct' else got)
            if pause and pause(w) and not act.done:
                return act
            continue
        raw, correct, assess = got[:3]
        rec = fold_item(raw, correct, assess)
        if records is not None:
            r = dict(rec, skill=act.skill, activity=act.name, role=w['role'],
                     item=item.get('id') if isinstance(item, dict) else None,
                     **evidence(raw, correct, item.get('v') if isinstance(item, dict) else None))
            if len(got) > 3 and got[3]:                     # ما تعرفه الواجهة وحدها عن الحدث: وقته
                r.update(got[3])
            if isinstance(item, dict) and item.get('reshown_same_fact'):
                r['reshown_after_interrupt'] = True        # 3.6: «أُعيد عرضه بعد انقطاع»
            if w.get('fact_just_seen'):                     # حقيقته حقيقة آخر بند عُرض من نشاط آخر، ولا علاج له
                r['fact_just_seen'] = w['fact_just_seen']
                if weak and classify(rec) == 'correct':     # ت2: يُحفظ «أداء بعد تعرض مباشر»، ولا يُعدّ صحيحًا مستقلًا
                    r['after_exposure'] = True
            if w.get('ahead_of'):                           # عُرض قبل بنود أُخّرت لأنها تكرر حقيقة ما سبقها
                r['ahead_of'] = list(w['ahead_of'])
            if w.get('repeated'):                           # بند مستهلك أُعيد للتعليم، لا دليلًا لقرار
                r['repeated_after_void'] = True
            if w.get('replaces'):                           # R18-01: بديل بند استُهلك، ووصف التعرّض السابق لحقيقته (3.5)
                r['replaces'] = w['replaces']
                r['fact_seen_before'] = bool(isinstance(item, dict) and item.get('fact_seen_before'))
            records.append(r)
        out = classify(rec)
        act.feed('exposed' if weak and out == 'correct' else out)
        if pause and pause(w) and not act.done:
            return act


def run_sync(gen, answer):
    """يشغّل مولّد خطوات حتى نهايته، ويجيب عن كل بند بـ answer(item, want). يعيد قيمة المولّد."""
    try:
        req = next(gen)
        while True:
            req = gen.send(answer(*req))
    except StopIteration as stop:
        return stop.value


def drive(act, source, answer, records=None, pause=None):
    """الغلاف المتزامن لـ drive_steps: answer(item, want) تجيب عن كل بند."""
    return run_sync(drive_steps(act, source, records, pause), answer)
