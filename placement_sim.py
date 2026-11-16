#!/usr/bin/env python3
"""محاكاة سياسة التشخيص في خريطة منهج الحساب الذهني (القسمان 6.1 و6.2)، النسخة 2.6.

التشغيل:
    python3 placement_sim.py mental-math-map-v2.6-single-file.md            # الاختبارات ثم المحاكاة
    python3 placement_sim.py mental-math-map-v2.6-single-file.md --selftest  # الاختبارات وحدها

السكربت يقرأ شبكة الإصدار 1 (المراحل 1 إلى 3) من ملف الخريطة نفسه: المعرّف، عمود «تتطلب»،
وأنواع الدليل التي يُشتق منها بنود بوابة كل مهارة. لا يعتمد على مكتبة خارجية، والبذرة ثابتة.

هذا السكربت أداة لفحص السياسة المكتوبة، وليس منطق التطبيق. ما يحاكيه نموذج مفترض:
- لكل مهارة عند الطفل حالة: يعرفها كاملة، أو يعرف ناتجها ولا يفسّره، أو لا يعرفها.
- دقته في البند تتبع هذه الحالة ونوع البند (حساب: ف3 ف4، فهم: ف1 ف2 ف5). أخطاء البنود مستقلة.
- الوحدة جلسة: جزء تشخيص، وجزء «استرجع»، وجزء تعلّم. تُعدّ البنود المعروضة فعلًا بأنواعها.
- للجلسة حصة تعليمية واحدة: فتح درس واحد، أو مضيّ درس بعد إعادة بوابته. لا يجتمعان في جلسة.
- كل تغيير في الأدلة حدث يُكتب في السجل. مرجع مستقل (reference) يعيد حساب الأدلة والانتظار من السجل
  وحده، وتُقارن به حالات السياسة في الاختبارات وفي كل تكرار.
ما لا يحاكيه: أثر الدروس (الطفل لا يتعلّم أثناءها، فالدرس الذي ينتظر تعلّم متطلبه يبقى منتظرًا ويُعدّ)،
مدة الدرس، الانقطاعات، التعب والملل، وزمن البند، وقرارات فتح المعلم (تدخل الاختبارات أحداثًا مفروضة).
"""
import re
import random
import sys
from collections import Counter

# ----------------------------------------------------------------- الشبكة
SRC = open(sys.argv[1], encoding='utf-8').read()
ROW = re.compile(r'^\| (\d-\d-\d) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \|$', re.M)
CALC = ('ف3', 'ف4')                      # بنود حساب؛ ما عداها بنود فهم
IDS, PRE, ITEMS = [], {}, {}
for sid, _txt, _model, req, ev, _ans in ROW.findall(SRC):
    types = re.findall(r'ف\d', ev)
    if not types or sid in PRE or sid[0] not in '123':
        continue                          # صف من جدول آخر، أو مهارة خارج الإصدار 1
    IDS.append(sid)
    PRE[sid] = re.findall(r'\d-\d-\d', req)
    items = []
    for t in types:                       # قالب 6.1: بندان لكل نوع، و5 لنوع ف3
        items += [t] * (5 if t == 'ف3' else 2)
    k = 0
    while len(items) < 6:                 # لا تقل عن 6، ويُكمَّل من أنواع المهارة نفسها
        items.append(types[k % len(types)])
        k += 1
    items.sort(key=lambda t: 0 if t in CALC else 1)   # بنود الحساب أولًا
    ITEMS[sid] = items
IDX = {s: n for n, s in enumerate(IDS)}
KIDS = {s: [c for c in IDS if s in PRE[c]] for s in IDS}
for s in IDS:
    assert all(IDX[p] < IDX[s] for p in PRE[s]), 'متطلب يأتي بعد مهارته: ' + s


def closure(x, edges):
    out, stack = set(), list(edges[x])
    while stack:
        y = stack.pop()
        if y not in out:
            out.add(y)
            stack.extend(edges[y])
    return out


ANC = {s: closure(s, PRE) for s in IDS}
DESC = {s: closure(s, KIDS) for s in IDS}
HAS_CALC = {s: any(t in CALC for t in ITEMS[s]) for s in IDS}
UND = {s: [t for t in ITEMS[s] if t not in CALC] for s in IDS}

SESSION_CAP = 4                   # جلسات البحث قبل جلسة البدء، للكبيرين وللصغير
GATES_PER_SESSION = {'older': 2, 'young': 1}
ITEM_BUDGET = 20                  # بنود البوابات المخططة في جلسة بحث للكبيرين
SHORT_PER_SESSION = 2             # تحققان قصيران على الأكثر في جزء «استرجع» من الجلسة
SHORT_AT_START = 4                # تحققات قصيرة على الأكثر في جلسة البدء


def p_tolerant(n, p):
    return p ** n + n * (1 - p) * p ** (n + 1)


def p_strict(n, p):
    return p ** n


# ----------------------------------------------------------------- الطفل
class Child:
    """know[s] = 'full' يعرفها كاملة، 'calc' يعرف الناتج ولا يفسّر. الغائب لا يعرفه."""

    def __init__(self, know, ak=0.95, au=0.40, au_u=0.40, help_k=0.0, help_u=0.0, script=None):
        self.know, self.ak, self.au, self.au_u = know, ak, au, au_u
        self.help_k, self.help_u = help_k, help_u
        self.script = list(script) if script else None    # إجابات مفروضة، للاختبارات

    def masters(self, s, t):
        k = self.know.get(s)
        return k == 'full' or (k == 'calc' and t in CALC)

    def item(self, s, t):
        """True صحيح مستقل، False خطأ، None طلب دعم."""
        if self.script:
            return self.script.pop(0)
        m = self.masters(s, t)
        h = self.help_k if m else self.help_u
        if h and random.random() < h:
            return None
        if m:
            return random.random() < self.ak
        return random.random() < (self.au_u if self.know.get(s) == 'calc' else self.au)


# ----------------------------------------------------------------- المرجع المستقل
def reference(log):
    """يقرأ سجل الأحداث وحده. يحسب الدليل المباشر لكل مهارة، ثم الانتظار بانتشار أمامي من كل
    مهارة متعثَّر فيها عبر توابعها التي لا دليل مباشر لها. لا يستعمل حالات السياسة ولا شروطها.
    طلب الدعم (gate:help، lesson:help) ليس دليلًا: لا يُكتب في proof."""
    proof = {}
    for _n, kind, s in log:
        if kind == 'gate:pass':
            proof[s] = 'exempt'
        elif kind in ('gate:fail', 'lesson:fail'):
            proof[s] = 'stumbled'
        elif kind == 'met':
            proof[s] = 'met'
        elif kind == 'invalidate':
            proof.pop(s, None)
    waiting, front = set(), [s for s in proof if proof[s] == 'stumbled']
    while front:
        x = front.pop()
        for c in KIDS[x]:
            if c not in proof and c not in waiting:
                waiting.add(c)
                front.append(c)
    return proof, waiting


def ref_blocked(log, s):
    """هل يمنع متطلبٌ مباشر أي نشاط على المهارة؟ من السجل وحده."""
    proof, waiting = reference(log)
    return any(proof.get(p) == 'stumbled' or p in waiting for p in PRE[s])


def ref_can_open(log, s, in_start, bypass=()):
    """هل يُفتح درس المهارة؟ من السجل وحده: كل متطلب مباشر مجتاز أو مستوفى أو متجاوز بقرار،
    أو، في جلسة البدء وحدها، اجتاز تحققه القصير ولا يمنعه شيء."""
    proof, waiting = reference(log)
    short_ok = {x for _n, k, x in log if k == 'short:ok'}
    for p in PRE[s]:
        if p in bypass or proof.get(p) in ('exempt', 'met'):
            continue
        if in_start and p in short_ok and proof.get(p) != 'stumbled' and p not in waiting:
            continue
        return False
    return True


# ----------------------------------------------------------------- السياسة
TEACH = ('skip', 'lesson')        # حدثا الحصة التعليمية: درس اختُصر، أو درس مضى كاملًا


class Placement:
    def __init__(self, ch, group='older', tolerant=True, regate=True, teacher_def=(), audit=False, trust=False):
        self.ch, self.group, self.tol, self.regate = ch, group, tolerant, regate
        self.ev = {}              # دليل مباشر: exempt / stumbled / met
        self.helped = set()       # مهارات انتهت بوابتها أو درسها بطلب دعم: علّة، لا حالة
        self.tdef = set(teacher_def)   # مؤجَّلة بقرار المعلم
        self.tdec = {}            # قرار فتح من المعلم: المهارة -> المتطلبات المتجاوزة
        self.treat = {}           # معالجة المهارة المتعثّر فيها: structure / regular
        self.errs = {}            # أنواع البنود التي أخطأ فيها في بوابتها
        self.opened = set()       # فُتح درسها
        self.lesson = set()       # مضى درسها كاملًا
        self.verified = set()     # اجتازت التحقق القصير
        self.checked = set()      # أُجري تحققها القصير
        if trust:
            self.checked |= self.tdef  # بديل للمقارنة: قرار المعلم يُسقط التحقق القصير أيضًا
        self.pending = []         # بوابات مسجَّلة لجزء التشخيص في جلسة لاحقة
        self.n = Counter()        # عدّاد البنود المعروضة بأنواعها
        self.gate_n = Counter()   # عدد بوابات كل مهارة
        self.gates = 0
        self.sessions = 0
        self.start = None
        self.start_at = None
        self.in_start = False
        self.log = []             # (الجلسة، الحدث، المهارة)
        self.audit = audit        # يقارن كل نشاط بالمرجع المستقل لحظة تنفيذه
        self.viol = 0             # نشاط نُفّذ على مهارة ممنوعة
        self._st = None

    # --- الأحداث: المكان الوحيد الذي يتغير فيه الدليل
    def event(self, kind, s):
        self.log.append((self.sessions, kind, s))
        if kind == 'gate:pass':
            self.ev[s] = 'exempt'
        elif kind in ('gate:fail', 'lesson:fail'):
            self.ev[s] = 'stumbled'
        elif kind in ('gate:help', 'lesson:help'):
            self.helped.add(s)                        # تُحفظ العلّة، ولا يتغير الدليل السابق
        elif kind == 'met':
            self.ev[s] = 'met'                        # متطلب استوفاه الطفل بالتعلّم (حدث مفروض)
        elif kind == 'invalidate':
            self.ev.pop(s, None)                      # أُبطل دليله (حدث مفروض)
        self._st = None

    # --- الحالات: دليل مباشر، ثم انتظار يُحسب من المتطلبات، ثم تأجيل
    def st(self):
        if self._st is None:
            anc_ex = set()
            for s, b in self.ev.items():
                if b == 'exempt':
                    anc_ex |= ANC[s]
            st = {}
            for s in IDS:                             # المتطلبات تسبق مهاراتها في الترتيب
                b = self.ev.get(s)
                if b:
                    st[s] = b
                elif any(st[p] in ('stumbled', 'waiting') for p in PRE[s]):
                    st[s] = 'waiting'                 # طلب الدعم لا يستثني المهارة من الانتظار
                elif s in anc_ex or s in self.tdef:
                    st[s] = 'deferred'
                else:
                    st[s] = None
            self._st = st
        return self._st

    def blocked(self, s):
        """أهلية أي نشاط على المهارة تُحسب من متطلباتها، لا من حالتها هي."""
        st = self.st()
        return any(st[p] in ('stumbled', 'waiting') for p in PRE[s])

    def blockers(self, s):
        """المتطلبات المتعثَّر فيها التي تمنع المهارة."""
        st, out, stack = self.st(), set(), list(PRE[s])
        while stack:
            p = stack.pop()
            if st[p] == 'stumbled':
                out.add(p)
            elif st[p] == 'waiting':
                stack.extend(PRE[p])
        return out

    def eligible(self, s, in_start=False):
        """دالة الأهلية الواحدة لفتح درس (3.4). تعيد (مسموح، سبب المنع، المتطلب الناقص)."""
        st = self.st()
        bypass = self.tdec.get(s, ())
        for p in sorted(PRE[s], key=IDX.get):
            if p in bypass or st[p] in ('exempt', 'met'):
                continue
            if st[p] in ('stumbled', 'waiting'):
                return False, 'متطلب متعثَّر فيه أو ينتظر', p
            if in_start and p in self.verified:
                continue                              # استثناء جلسة البدء: التحقق القصير يكفي
            return False, 'متطلب لم يُفحص: بوابته أولًا', p
        return True, None, None

    def mismatch(self):
        """عدد المهارات التي تخالف حالتها المرجع المستقل."""
        proof, waiting = reference(self.log)
        st, bad = self.st(), 0
        for s in IDS:
            if (st[s] == 'waiting') != (s in waiting):
                bad += 1
            elif proof.get(s) != (st[s] if st[s] in ('exempt', 'stumbled', 'met') else None):
                bad += 1
        return bad

    def _guard(self, s):
        """قبل كل بوابة أو تحقق قصير: المهارة الممنوعة لا تُفحص."""
        if self.blocked(s):
            self.viol += 1
        if self.audit and ref_blocked(self.log, s):
            self.viol += 1

    # --- البنود والبوابة
    def ask(self, s, t, cat):
        self.n[cat] += 1
        return self.ch.item(s, t)

    def gate(self, s):
        """بلا تغذية راجعة، بنود الحساب أولًا. يعيد pass أو fail أو help."""
        self._guard(s)
        self.gates += 1
        self.gate_n[s] += 1
        errs = []
        for t in ITEMS[s]:
            r = self.ask(s, t, 'gate')
            if r is None:
                return self._end(s, 'help', errs)
            if not r:
                errs.append(t)
                if len(errs) == 2 or not self.tol:
                    return self._end(s, 'fail', errs)
        if errs:
            for _ in range(2):                        # تعويض الخطأ الواحد ببندين من نوعه
                r = self.ask(s, errs[0], 'comp')
                if r is None:
                    return self._end(s, 'help', errs)
                if not r:
                    return self._end(s, 'fail', errs + [errs[0]])
        return self._end(s, 'pass', errs)

    def _end(self, s, res, errs):
        self.event('gate:' + res, s)
        if res == 'fail':
            self.errs[s] = list(errs)
            only_und = HAS_CALC[s] and all(e not in CALC for e in errs)
            self.treat[s] = 'structure' if only_und else 'regular'
        return res

    def short_check(self, s):
        """3 بنود في جزء «استرجع»، فيها بنود الطريقة إن وُجدت. خطأ واحد أو طلب دعم يكفي."""
        self._guard(s)
        self.checked.add(s)
        types = (UND[s] + ITEMS[s])[:2] + [ITEMS[s][0]]
        ok = True
        for t in types:
            if self.ask(s, t, 'short') is not True:
                ok = False
        self.log.append((self.sessions, 'short:ok' if ok else 'short:no', s))
        if ok:
            self.verified.add(s)
        return ok

    # --- البحث عن نقطة العمل
    def need(self, s):
        """تحتاج فتح درس: تعثّر فيها الطفل، أو طلب فيها دعمًا وهي لا تنتظر."""
        v = self.st()[s]
        return v == 'stumbled' or (s in self.helped and v in (None, 'deferred'))

    def candidate(self):
        for s in IDS:                                 # الأدنى في ترتيب الشبكة
            if self.need(s):
                return s
        return None

    def next_gate(self, start):
        st = self.st()
        done = ('exempt', 'met')
        if self.group == 'young':                     # صعود بترتيب الشبكة حتى أول تعثّر
            if self.candidate() is not None:
                return None
            fresh = [x for x in IDS if st[x] is None]
            return fresh[0] if fresh else None
        if self.gates == 0 and start and st[start] is None:
            return start
        c = self.candidate()
        if c is not None:
            if all(st[p] in done for p in PRE[c]):
                return None                           # نقطة العمل محسومة
            fresh = [a for a in sorted(ANC[c], key=IDX.get) if st[a] is None]
            if fresh:
                def split(a):
                    below = sum(1 for b in ANC[a] if st[b] is None)
                    return min(below + 1, len(fresh) - below)
                return max(fresh, key=split)
            need = [p for p in sorted(PRE[c], key=IDX.get) if st[p] not in done]
            return need[0]
        fresh = [x for x in IDS if st[x] is None]
        if not fresh:
            return None

        def split(x):
            below = sum(1 for b in ANC[x] if st[b] is None)
            above = sum(1 for d in DESC[x] if st[d] is None)
            return min(below + 1, above + 1)
        return max(fresh, key=split)

    def search(self, start):
        """جلسات البحث: لا تتجاوز SESSION_CAP، وفي كل جلسة بوابة أو بوابتان ضمن ميزانية البنود."""
        while self.sessions < SESSION_CAP:
            x = self.next_gate(start)
            if x is None:
                return
            self.sessions += 1
            budget, done = ITEM_BUDGET, 0
            while x is not None and done < GATES_PER_SESSION[self.group]:
                if done and len(ITEMS[x]) > budget:
                    break
                budget -= len(ITEMS[x])
                self.gate(x)
                done += 1
                x = self.next_gate(start)             # تُحسب من جديد بعد كل نتيجة

    def working_point(self):
        """نقطة العمل في جلسة البدء: تحقق قصير لكل متطلب مباشر غير مجتاز، ونزول عند الخطأ."""
        st = self.st()
        w = self.candidate()
        if w is None:
            w = next((x for x in IDS if st[x] is None), None)
        if w is None:
            return None
        k = 0
        while True:
            moved = False
            for p in sorted(PRE[w], key=IDX.get):
                if st[p] in ('exempt', 'met') or p in self.verified:
                    continue
                if k == SHORT_AT_START:
                    return w                          # انتهت حصة التحقق: دالة الأهلية تحسم
                k += 1
                if not self.short_check(p):
                    w, moved = p, True
                    break
            if not moved:
                return w

    def open_lesson(self, w):
        """فتح الدرس بلا بوابة: «جرّب أولًا»، ثم أول 3 بنود موجَّهة. يعيد skip أو lesson."""
        if not self.eligible(w, self.in_start)[0]:
            self.viol += 1
        if self.audit and not ref_can_open(self.log, w, self.in_start, self.tdec.get(w, ())):
            self.viol += 1
        self.opened.add(w)
        e = self.errs.get(w)
        types = [e[0], e[-1]] if e else [ITEMS[w][0], (UND[w] or ITEMS[w])[0]]
        seen = [self.ask(w, t, 'try') for t in types]
        ok = all(r is True for r in seen)
        if not ok:
            ok = True
            for t in ((UND[w] or ITEMS[w]) * 3)[:3]:
                r = self.ask(w, t, 'lesson')
                seen.append(r)
                if r is not True:
                    ok = False
                    break
        if ok:
            # قاعدة اختصار الدرس واحدة، سُمح بإعادة البوابة أم لم يُسمح
            self.log.append((self.sessions, 'skip', w))
            if self.regate or self.ev.get(w) != 'stumbled':
                self.pending.append(w)                # البوابة في جزء التشخيص من جلسة لاحقة
            return 'skip'
        # درس كامل. خطأ في الأجوبة دليل تعثّر من الدرس؛ طلب الدعم وحده ليس دليلًا
        self.event('lesson:fail' if False in seen else 'lesson:help', w)
        if self.ev.get(w) == 'stumbled':
            self.treat.setdefault(w, 'regular')
        self.lesson.add(w)
        self.log.append((self.sessions, 'lesson', w))
        return 'lesson'

    def start_session(self):
        """جلسة البدء: لا بوابة فيها. يعيد (نقطة العمل، ما جرى)."""
        self.sessions += 1
        self.start_at = self.sessions
        self.in_start = True
        w = self.working_point()
        self.items_before = sum(self.n.values())
        what = 'none'
        if w is not None:
            if self.eligible(w, True)[0]:
                what = self.open_lesson(w)
            else:                                     # لم تُحسم مهارة تُفتح: نشاط «استعمل»، وبوابتها لاحقًا
                what = 'use'
                if self.st()[w] in (None, 'deferred') and self.gate_n[w] == 0 and w not in self.pending:
                    self.pending.insert(0, w)
        if what in ('none', 'use'):
            self.log.append((self.sessions, what, w))
        self.in_start = False
        return w, what

    # --- بعد جلسة البدء
    def pick_gate(self):
        """بوابة الجلسة. الأهلية تُفحص لحظة الاختيار، والقائمة المسجَّلة لا تمنح إذنًا دائمًا."""
        st = self.st()
        for x in list(self.pending):
            if x in self.lesson or self.gate_n[x] >= 2 or st[x] in ('exempt', 'met'):
                self.pending.remove(x)                # لم تعد لها بوابة
            elif not self.blocked(x):
                self.pending.remove(x)
                return x                              # الممنوعة تبقى مسجَّلة حتى يزول المانع
        for s in IDS:                                 # متطلب غير مفحوص يمنع فتح درس: بوابته أولًا
            if self.need(s) and s not in self.opened:
                ok, _why, p = self.eligible(s)
                if not ok and st[p] in (None, 'deferred') and p not in self.helped \
                        and p not in self.opened and self.gate_n[p] == 0:
                    return p
        if not self.lesson:                           # لم يبدأ درس كامل بعد: يستمر البحث
            g = self.next_gate(self.start)
            if g is not None and g not in self.opened and g not in self.helped \
                    and self.gate_n[g] == 0 and not self.blocked(g):
                return g
        for x in IDS:                                 # ثم الفجوات بترتيب الشبكة
            if st[x] is None and x not in self.opened and x not in self.helped:
                return x
        return None

    def pick_lesson(self):
        for s in IDS:
            if self.need(s) and s not in self.opened and self.eligible(s)[0]:
                return s
        return None

    def pick_short(self):
        st = self.st()
        for x in IDS:
            if st[x] == 'deferred' and x not in self.checked:
                return x
        return None

    def session(self):
        """جلسة بعد البدء: بوابة واحدة على الأكثر، تحققان قصيران، حصة تعليمية واحدة."""
        g = self.pick_gate()
        if g is None and self.pick_short() is None and self.pick_lesson() is None:
            return False
        self.sessions += 1
        taught = False
        if g is not None:
            was_open = g in self.opened
            r = self.gate(g)
            if was_open and r != 'pass':
                # نتائج البوابة بعد فتح الدرس كلٌّ على حدة: الإخفاق دليل تعثّر (سجّله _end)،
                # وطلب الدعم يوجّه إلى الدرس ولا يولّد دليل تعثّر ولا تعليقًا للتوابع
                self.lesson.add(g)
                self.log.append((self.sessions, 'lesson', g))
                taught = True                         # استُهلكت حصة الجلسة التعليمية
        for _ in range(SHORT_PER_SESSION):            # تُختار بعد نتيجة البوابة، لا قبلها
            x = self.pick_short()
            if x is None:
                break
            if not self.short_check(x):
                self.pending.append(x)                # خطأ في التحقق يستدعي بوابتها
        if not taught:
            o = self.pick_lesson()
            if o is not None:
                self.open_lesson(o)
        return True

    def run(self, start):
        self.start = start
        self.search(start)
        w, what = self.start_session()
        while self.session():
            pass
        return w, what

    def teach_counts(self):
        """عدد الأنشطة التعليمية في كل جلسة، من السجل."""
        return Counter(n for n, k, _s in self.log if k in TEACH)


# ----------------------------------------------------------------- الاختبارات
def selftest():
    """حالات مضادة للسياسة. كل اختبار يطبع نتيجته، وأي إخفاق يوقف السكربت.
    القيم المتوقعة مكتوبة هنا صراحة، أو مأخوذة من المرجع المستقل reference، لا من دوال السياسة."""
    results = []

    def check(name, cond):
        results.append(bool(cond))
        print('  %s  %d. %s' % ('نجح' if cond else 'أخفق', len(results), name))

    full = {s: 'full' for s in IDS}
    sure = dict(ak=1.0, au=0.0, au_u=0.0)

    def after_start(know=None, **kw):
        pl = Placement(Child(know or full, ak=1.0, au=0.0, au_u=0.0, **kw), audit=True)
        pl.sessions = SESSION_CAP + 1
        return pl

    # 1) تعثّر في متطلب بعد تأجيله: التوابع المؤجَّلة تنتقل إلى الانتظار
    pl = Placement(Child(full, **sure))
    pl.event('gate:pass', '2-6-3')
    before = [s for s in IDS if pl.st()[s] == 'deferred']
    pl.event('gate:fail', '1-1-1')
    st = pl.st()
    left = [s for s in before if s != '1-1-1' and st[s] == 'deferred']
    check('اجتياز 2-6-3 ثم تعثّر 1-1-1: لا يبقى تابع لها «مؤجَّلًا» (كانت %d، بقي %d)، و1-1-2 تنتظر'
          % (len(before), len(left)), not left and st['1-1-2'] == 'waiting' and st['2-6-3'] == 'exempt')
    check('بعد ذلك تطابق الحالات المرجع المستقل', pl.mismatch() == 0)

    # 2) طلب دعم في أول بند من بوابة الجذر لا يعلّق شيئًا ولا يسجّل تعثّرًا
    pl = Placement(Child(full, script=[None]))
    r = pl.gate('1-1-1')
    st = pl.st()
    check('طلب دعم في أول بند من بوابة 1-1-1: النتيجة «%s»، لا دليل تعثّر، وعدد المنتظرات %d'
          % (r, sum(1 for s in IDS if st[s] == 'waiting')),
          r == 'help' and st['1-1-1'] is None and '1-1-1' in pl.helped and 'waiting' not in st.values())

    # 3) التعثّر لا يمسّ فرعًا لا يعتمد عليه
    pl = Placement(Child(full, **sure))
    pl.event('gate:fail', '3-5-1')
    st = pl.st()
    check('تعثّر 3-5-1 لا يغيّر 3-8-1، ويجعل 3-6-2 تنتظر ومانعها 3-5-1',
          st['3-8-1'] is None and st['3-6-2'] == 'waiting' and pl.blockers('3-6-2') == {'3-5-1'})

    # 4) الدليل المباشر يبقى، ويقطع سريان الانتظار
    pl.event('gate:pass', '3-6-2')
    st = pl.st()
    check('3-6-2 المجتازة ببوابتها تبقى مجتازة رغم تعثّر متطلبها، و3-6-4 لا تنتظر بسببها',
          st['3-6-2'] == 'exempt' and st['3-6-4'] != 'waiting' and pl.mismatch() == 0)

    # 5) المعالجة من أنواع الأخطاء، وبنود الحساب أولًا
    s = '2-4-1'                                        # ف1 ف2 ف3: 5 حساب ثم 4 فهم
    pl = Placement(Child(full, script=[True] * 5 + [False, False]))
    r1 = pl.gate(s)
    t1 = pl.treat.get(s)
    pl = Placement(Child(full, script=[False, True, True, True, True, False]))
    r2 = pl.gate(s)
    t2 = pl.treat.get(s)
    pl = Placement(Child(full, script=[True] * 5 + [False, True, True, True] + [True, True]))
    r3 = pl.gate(s)
    check('خطآن في الفهم بعد حساب صحيح: درس البنية. خطأ حساب وخطأ فهم: المسار العادي. خطأ واحد معوَّض: إعفاء',
          (r1, t1, r2, t2, r3) == ('fail', 'structure', 'fail', 'regular', 'pass') and pl.n['comp'] == 2)

    # 6) س1: طلب دعم في إعادة البوابة، بلا أي إجابة خاطئة، لا يسجّل تعثّرًا ولا يعلّق تابعًا
    pl = after_start(script=[True, True, None])
    pl.open_lesson('1-1-1')                            # «جرّب أولًا» صحيح: اختُصر الدرس وسُجّلت البوابة
    pl.session()                                       # البوابة: طلب دعم في أول بند
    st = pl.st()
    proof, waiting = reference(pl.log)
    check('طلب دعم في إعادة بوابة 1-1-1: لا دليل تعثّر، المنتظرات %d، ويمضي درسها مساعدةً تعليمية'
          % len(waiting),
          st['1-1-1'] is None and '1-1-1' not in proof and not waiting and 'waiting' not in st.values()
          and '1-1-1' in pl.lesson and '1-1-1' in pl.helped)

    # 7) س2: طلب الدعم لا يستثني المهارة من انتظار متطلبها
    pl = Placement(Child(full, script=[None]), audit=True)
    pl.gate('1-1-2')                                   # انتهت بطلب دعم
    pl.event('gate:fail', '1-1-1')                     # ثم تعثّر متطلبها
    st = pl.st()
    proof, waiting = reference(pl.log)
    check('1-1-2 انتهت بوابتها بطلب دعم ثم تعثّر 1-1-1: تصير «تنتظر متطلبًا» ومانعها 1-1-1، وتبقى علّتها',
          st['1-1-2'] == 'waiting' and '1-1-2' in waiting and pl.blockers('1-1-2') == {'1-1-1'}
          and '1-1-2' in pl.helped and not pl.need('1-1-2') and pl.mismatch() == 0)

    # 8) س3: بعد نتيجة تغيّر الحالة لا يُنفَّذ تحقق ولا بوابة على مهارة صارت تنتظر
    pl = after_start({x: 'full' for x in IDS if x != '1-1-1'})   # لا يعرف الجذر وحده
    pl.event('gate:pass', '2-6-3')                     # أسلافها مؤجَّلة
    pl.pending = ['1-1-1', '1-1-2', '1-2-1']           # بوابات مسجَّلة قبل تغيّر الحالة
    pl.session()                                       # بوابة 1-1-1 تُخفق
    n0 = pl.sessions
    touched = [(k, x) for n, k, x in pl.log if n == n0 and x in DESC['1-1-1'] and k[:4] in ('gate', 'shor')]
    pl.session()
    later = [(k, x) for n, k, x in pl.log if n > n0 and x in ('1-1-2', '1-2-1') and k[:4] in ('gate', 'shor')]
    check('إخفاق بوابة 1-1-1 بعد تأجيل: لا تحقق قصير ولا بوابة لتوابعها في الجلسة نفسها (%d) ولا بعدها وهي تنتظر (%d)'
          % (len(touched), len(later)),
          not touched and not later and pl.viol == 0 and pl.st()['1-1-2'] == 'waiting'
          and '1-1-2' in pl.pending)

    # 9) س4: حصة تعليمية واحدة في الجلسة
    A, B = '3-5-1', '3-8-1'
    assert A not in ANC[B] and B not in ANC[A]
    pl = after_start(script=[True, True, False, False])
    for p in PRE[A] + PRE[B]:
        pl.event('gate:pass', p)
    pl.event('gate:fail', A)
    pl.event('gate:fail', B)
    pl.open_lesson(A)                                  # اختُصر درس A وسُجّلت إعادة بوابته
    pl.session()                                       # إعادة بوابة A تُخفق: يمضي درسه كاملًا
    n1 = pl.sessions
    in_n1 = [(k, x) for n, k, x in pl.log if n == n1 and k in TEACH]
    pl.session()
    in_n2 = [(k, x) for n, k, x in pl.log if n == n1 + 1 and k in TEACH]
    check('إعادة بوابة %s تُخفق فيمضي درسها، ودرس %s يؤجَّل إلى الجلسة التالية: %s ثم %s'
          % (A, B, in_n1, in_n2),
          in_n1 == [('lesson', A)] and len(in_n2) == 1 and in_n2[0][1] == B
          and max(pl.teach_counts().values()) == 1 and pl.viol == 0)

    # 10) س5: قاعدة اختصار الدرس لا تتغير بخيار إعادة البوابة
    out = []
    for rg in (True, False):
        pl = Placement(Child(full, script=[True, True]), regate=rg)
        pl.event('gate:fail', '1-1-1')
        out.append((pl.open_lesson('1-1-1'), list(pl.pending)))
    check('الإجابتان الصحيحتان نفسهما: مع الإعادة %s، وبلا إعادة %s' % (out[0], out[1]),
          out == [('skip', ['1-1-1']), ('skip', [])])

    # 11) س6: دالة الأهلية الواحدة، بأحداث مفروضة، مقابل المرجع المستقل
    s = '3-5-1'
    P = sorted(PRE[s], key=IDX.get)                   # 3-2-3 و3-3-2
    pl = Placement(Child(full, **sure))
    got = [pl.eligible(s)]                             # المتطلبات غير مفحوصة
    ref = [ref_can_open(pl.log, s, False)]
    for p in P:
        pl.sessions = SESSION_CAP + 1
        pl.short_check(p)                              # تحقق قصير ناجح
    got += [pl.eligible(s, True), pl.eligible(s, False)]
    ref += [ref_can_open(pl.log, s, True), ref_can_open(pl.log, s, False)]
    pl.event('gate:fail', P[0])                        # تعثّر متطلب
    got.append(pl.eligible(s, True))
    ref.append(ref_can_open(pl.log, s, True))
    pl.event('met', P[0])                              # استوفاه بالتعلّم
    pl.event('gate:pass', P[1])
    got.append(pl.eligible(s))
    ref.append(ref_can_open(pl.log, s, False))
    pl.event('invalidate', P[0])                       # أُبطل دليله
    got.append(pl.eligible(s))
    ref.append(ref_can_open(pl.log, s, False))
    pl.tdec[s] = [P[0]]                                # قرار فتح من المعلم يتجاوزه
    got.append(pl.eligible(s))
    ref.append(ref_can_open(pl.log, s, False, [P[0]]))
    want = [False, True, False, False, True, False, True]
    check('أهلية فتح درس 3-5-1 في سبع حالات مفروضة: %s' % ' '.join('نعم' if g[0] else 'لا' for g in got),
          [g[0] for g in got] == want and ref == want
          and got[0][2] == P[0] and got[3][2] == P[0] and got[5][2] == P[0])

    # 12) السقف: جلسة البدء لا تتأخر عن الخامسة ولا بوابة فيها، في كل الحالات وببوابة لا تخطئ
    ok = True
    for name, know, start, group in PROFILES:
        pl = Placement(Child(know, **sure), group, audit=True)
        pl.run(start)
        in_start = [e for e in pl.log if e[0] == pl.start_at and e[1].startswith('gate')]
        if pl.start_at > SESSION_CAP + 1 or in_start or pl.mismatch() or pl.viol:
            ok = False
    check('كل الحالات ببوابة لا تخطئ: جلسة البدء عند %d على الأكثر، بلا بوابة فيها، والحالات تطابق المرجع'
          % (SESSION_CAP + 1), ok)

    # 13) تشغيل عشوائي مع طلب دعم، وكل نشاط يُقارن بالمرجع المستقل لحظة تنفيذه
    random.seed(7)
    bad = Counter()
    for name, know, start, group in PROFILES:
        for _ in range(200):
            pl = Placement(Child(know, help_k=0.02, help_u=0.2), group, audit=True)
            pl.run(start)
            bad['حالة تخالف المرجع'] += pl.mismatch()
            bad['جلسة بدء بعد السقف أو فيها بوابة'] += int(pl.start_at > SESSION_CAP + 1) + sum(
                1 for e in pl.log if e[0] == pl.start_at and e[1].startswith('gate'))
            bad['نشاط على مهارة ممنوعة'] += pl.viol
            bad['جلسة فيها نشاطان تعليميان'] += sum(1 for v in pl.teach_counts().values() if v > 1)
            bad['مهارة ببوابات أكثر من 2'] += sum(1 for v in pl.gate_n.values() if v > 2)
    check('1600 تشغيل عشوائي مع طلب دعم: ' + '، '.join('%s %d' % kv for kv in bad.items()),
          sum(bad.values()) == 0)

    if not all(results):
        print('أخفق اختبار. توقّف.')
        sys.exit(1)
    print('نجحت الاختبارات كلها: %d' % len(results))


# ----------------------------------------------------------------- الأطفال
def K(pred, level='full'):
    return {s: level for s in IDS if pred(s)}


U35 = {'3-5-1', '3-5-2', '3-5-3'}
BRANCH = set().union(U35, *(DESC[s] for s in U35))
MEMO = {s for s in IDS if s[:3] in ('2-3', '2-4', '2-5')} | {s for s in IDS if s[0] == '3' and s[:3] != '3-1'}
CALC_ONLY = dict(K(lambda s: s[0] == '1'))
CALC_ONLY.update({s: ('calc' if UND[s] else 'full') for s in IDS if s[0] in '23' and HAS_CALC[s]})
PROFILES = [
    ('أ يعرف محتوى الإصدار 1 كله', K(lambda s: True), '2-6-3', 'older'),
    ('ب يعرف المرحلتين 1 و2', K(lambda s: s[0] in '12'), '2-6-3', 'older'),
    ('ج يعرف حتى الوحدة 3-4', K(lambda s: s[0] in '12' or s[:3] in ('3-1', '3-2', '3-3', '3-4')), '2-6-3', 'older'),
    ('د تنقصه مهارات الاستراتيجيات كاملة', K(lambda s: s not in MEMO), '2-6-3', 'older'),
    ('هـ فجوتان منفردتان', K(lambda s: s not in ('2-6-2', '3-1-4')), '2-6-3', 'older'),
    ('و يتعثر في فرع الطرح 3-5 ويعرف ما لا يعتمد عليه', K(lambda s: s not in BRANCH), '2-6-3', 'older'),
    ('ح يحسب ولا يفسّر في المرحلتين 2 و3', CALC_ONLY, '2-6-3', 'older'),
    ('ز الصغير: يعرف الوحدتين 1-1 و1-2', K(lambda s: s[:3] in ('1-1', '1-2')), None, 'young'),
]
RUNS = 2000
STAGES_12 = {s for s in IDS if s[0] in '12'}


def q(v, f):
    v = sorted(v)
    return v[min(len(v) - 1, int(f * len(v)))]


def pct(x, n):
    return '%.1f%%' % (100.0 * x / n)


def run(label, runs=RUNS, tolerant=True, regate=True, teacher=(), trust=False, only=None, **kw):
    print('\n=== %s' % label)
    c0 = Child({}, **kw)
    print('    دقة ما يعرفه %.2f | ما لا يعرفه %.2f | فهم من يحسب ولا يفسّر %.2f | بوابة %s | إعادة البوابة: %s | '
          'طلب دعم %.2f/%.2f | تكرارات %d' % (c0.ak, c0.au, c0.au_u, 'متسامحة' if tolerant else 'صارمة',
                                            'نعم' if regate else 'لا', c0.help_k, c0.help_u, runs))
    for name, know, start, group in PROFILES:
        if only and name[0] not in only:
            continue
        needs = [s for s in IDS if know.get(s) != 'full']
        calc_only = [s for s in IDS if know.get(s) == 'calc']
        S = Counter()
        sess0, items0, sess_all, items_all, first_needed = [], [], [], [], []
        cat = Counter()
        what0 = Counter()
        for _ in range(runs):
            pl = Placement(Child(know, **kw), group, tolerant, regate, teacher, trust=trust)
            w, what = pl.run(start)
            st = pl.st()
            S['ref'] += pl.mismatch()
            S['viol'] += pl.viol
            S['teach2'] += sum(1 for v in pl.teach_counts().values() if v > 1)
            S['gate3'] += sum(1 for v in pl.gate_n.values() if v > 2)
            sess0.append(pl.start_at)
            items0.append(pl.items_before)
            sess_all.append(pl.sessions)
            diag = sum(v for k, v in pl.n.items() if k != 'lesson')
            items_all.append(diag)
            cat.update(pl.n)
            S['gates'] += pl.gates
            if what == 'none':
                what0['لا شيء يُدرَّس'] += 1
            elif what == 'use':
                what0['نشاط «استعمل»: لم تُحسم مهارة تُفتح'] += 1
            elif what == 'skip':
                what0['درس اختُصر لمهارة يعرفها' if know.get(w) == 'full' else 'درس اختُصر لمهارة لا يعرفها'] += 1
            elif know.get(w) == 'full':
                what0['درس لا يحتاجه'] += 1
            elif all(know.get(p) == 'full' or (know.get(p) == 'calc' and know.get(w) == 'calc') for p in PRE[w]):
                what0['درس مناسب'] += 1
            else:
                what0['درس أعلى من مستواه'] += 1
            fn = [e[0] for e in pl.log if e[1] == 'lesson' and know.get(e[2]) != 'full']
            if fn:
                first_needed.append(fn[0])
            unneeded = sum(1 for s in pl.lesson if know.get(s) == 'full')
            S['unneeded'] += unneeded
            S['unneeded_any'] += int(unneeded > 0)
            S['known_wait'] += sum(1 for s in IDS if know.get(s) == 'full' and st[s] == 'waiting')
            S['known_stum'] += sum(1 for s in IDS if know.get(s) == 'full' and st[s] == 'stumbled')
            S['held'] += sum(1 for s in IDS if pl.need(s) and s not in pl.opened)
            S['unk_exempt'] += sum(1 for s in IDS if s not in know and st[s] == 'exempt')
            S['unk_def'] += sum(1 for s in IDS if know.get(s) != 'full' and st[s] == 'deferred')
            S['co_exempt'] += sum(1 for s in calc_only if st[s] == 'exempt')
            S['co_struct'] += sum(1 for s in calc_only if st[s] == 'stumbled' and pl.treat.get(s) == 'structure')
            S['co_regular'] += sum(1 for s in calc_only if st[s] == 'stumbled' and pl.treat.get(s) == 'regular')
            S['co_other'] += sum(1 for s in calc_only if st[s] not in ('exempt', 'stumbled'))
            S['none_left'] += sum(1 for s in IDS if st[s] is None and s not in pl.helped)
        n = float(runs)
        print('  %s  (مهارات تحتاج تعليمًا: %d)' % (name, len(needs)))
        print('     قبل أول نشاط تعلّم: الجلسة %d في الوسيط، %d في المئين 95، %d أقصى | بنود تشخيصية قبله: %d وسيط، %d مئين 95'
              % (q(sess0, .5), q(sess0, .95), max(sess0), q(items0, .5), q(items0, .95)))
        print('     ما جرى في جلسة البدء: ' + '، '.join('%s %s' % (k, pct(v, n)) for k, v in what0.most_common()))
        if first_needed:
            print('     أول درس كامل لمهارة يحتاجها: الجلسة %d وسيط، %d مئين 95 (وقع في %s من التكرارات)'
                  % (q(first_needed, .5), q(first_needed, .95), pct(len(first_needed), n)))
        print('     حتى اكتمال التشخيص: %d جلسة وسيط، %d مئين 95 | بنود تشخيصية: %d وسيط، %d مئين 95 | '
              'متوسطها: بوابات %.0f (في %.1f بوابة)، تعويض %.1f، «جرّب أولًا» %.1f، تحقق قصير %.0f'
              % (q(sess_all, .5), q(sess_all, .95), q(items_all, .5), q(items_all, .95),
                 cat['gate'] / n, S['gates'] / n, cat['comp'] / n, cat['try'] / n, cat['short'] / n))
        print('     دروس كاملة لمهارات يعرفها: %.2f في المتوسط، ووقع واحد على الأقل في %s من التكرارات | '
              'يعرفها وبقيت «متعثّر فيها» %.2f | يعرفها وتنتظر عند النهاية %.2f'
              % (S['unneeded'] / n, pct(S['unneeded_any'], n), S['known_stum'] / n, S['known_wait'] / n))
        print('     لا يعرفها وأُعفي %.3f | تحتاج تعليمًا وبقيت مؤجَّلة %.3f | تحتاج درسًا ودرسها ينتظر متطلبًا لم يُتعلَّم %.1f | بلا حالة %d'
              % (S['unk_exempt'] / n, S['unk_def'] / n, S['held'] / n, S['none_left']))
        print('     مخالفات: حالة تخالف المرجع المستقل %d | نشاط على مهارة ممنوعة %d | جلسة فيها نشاطان تعليميان %d | مهارة ببوابات أكثر من 2: %d'
              % (S['ref'], S['viol'], S['teach2'], S['gate3']))
        if calc_only:
            print('     مهارات «يحسب ولا يفسّر» (%d): أُعفي %.1f | درس البنية %.1f | المسار العادي %.1f | مؤجَّلة أو تنتظر %.1f'
                  % (len(calc_only), S['co_exempt'] / n, S['co_struct'] / n, S['co_regular'] / n, S['co_other'] / n))


if __name__ == '__main__':
    print('الشبكة: %d مهارة في الإصدار 1، جذورها %s' % (len(IDS), [s for s in IDS if not PRE[s]]))
    lens = Counter(len(v) for v in ITEMS.values())
    print('أطوال البوابات: %s | مهارات بلا بنود حساب: %s' % (dict(sorted(lens.items())), [s for s in IDS if not HAS_CALC[s]]))
    print('السقف: %d جلسات بحث ثم جلسة البدء | في جلسة البحث: بوابتان للكبيرين ضمن %d بندًا مخططًا، وبوابة للصغير'
          % (SESSION_CAP, ITEM_BUDGET))
    print('بعد البدء، في كل جلسة: بوابة واحدة، و%d تحقق قصير، وحصة تعليمية واحدة، على الأكثر' % SHORT_PER_SESSION)
    print('\n=== اختبارات الحالات المضادة')
    selftest()
    if '--selftest' in sys.argv:
        sys.exit(0)
    print('\n=== احتمال اجتياز البوابة بحسب طولها (نموذج مبسّط: بنود مستقلة)')
    print('    الطول | نوع البوابة | ' + ' | '.join('دقة %d%%' % round(p * 100) for p in (0.95, 0.90, 0.75, 0.50, 0.40)))
    for n in (6, 7, 9, 11):
        for nm, f in (('متسامحة', p_tolerant), ('صارمة  ', p_strict)):
            print('    %5d | %s | ' % (n, nm) + ' | '.join('%6.2f%%' % (100 * f(n, p)) for p in (0.95, 0.90, 0.75, 0.50, 0.40)))

    random.seed(20261111)
    run('بوابة لا تخطئ (تغطية وعبء فقط)', runs=1, ak=1.0, au=0.0, au_u=0.0)
    run('الأساس')
    run('بوابة صارمة للمقارنة', tolerant=False)
    run('بلا إعادة البوابة للمقارنة، وقاعدة اختصار الدرس كما هي', regate=False)
    run('طفل أقل دقة في ما يعرفه', ak=0.90)
    run('تخمين أسهل: 0.50 في ما لا يعرفه وفي الفهم', au=0.50, au_u=0.50)
    run('مع طلب الدعم: 2% من بنود ما يعرفه و20% من غيرها', help_k=0.02, help_u=0.20)
    run('قرار المعلم: تأجيل تدريس مهارات المرحلتين 1 و2 (27 مهارة) مع بقاء التحقق القصير، للحالتين أ وهـ',
        teacher=STAGES_12, only='أه')
    run('بديل للمقارنة: القرار نفسه ويُسقط التحقق القصير أيضًا، للحالتين أ وهـ', teacher=STAGES_12, trust=True, only='أه')
