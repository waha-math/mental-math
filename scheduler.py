#!/usr/bin/env python3
"""المجدول: يختار نشاط الجلسة، ويشغّله عبر طبقة البنود، ويرسل أحداثه إلى المحرك (6.2 و7.1).

لا يحمل المجدول حالة تقدّم. كل ما يقرّر به يقرؤه من المحرك: الحالات، والبوابات، وطلبات الدعم، والدروس،
وطابور البوابات. ويسأل المحرك (preflight) قبل عرض أول بند من أي نشاط. ما يرفضه المحرك يُسجَّل في
refused، وفي التشغيل السليم يبقى فارغًا. حالته الخاصة ثلاثة أشياء تخطيطية: بوابات نواها في جلسة البدء
(intent)، وأنواع دليل الفهم التي ثبتت في الدرس الجاري (proven)، وعدد محاولات الفحص لاختيار بنودها.

وضعان:
- learning=False: سياسة التشخيص وحدها، كما في محاكاة placement_sim.py. الحصة التعليمية تفتح درسًا جديدًا
  ولا تستأنف، لأن الطفل في المحاكاة لا يتعلّم.
- learning=True: مسار التعلّم أيضًا: استئناف الدرس، ودليل الفهم، وفحص الاستقلال في يوم لاحق، وجلسة تدريب
  قبل إعادته.
compat=True يعيد خيارات المحاكاة القديمة التي تخالف المواصفة أو المحتوى، لمقارنتها بها تشغيلًا بتشغيل.

سقف الوقت (7.1، بقرار الأب في ك9): cap ثوانٍ للجلسة، و item_seconds(want) مدة البند. السقف لا يقطع بندًا:
بعد البند الذي يبلغه تُختم الجلسة، ويُحفظ النشاط غير المكتمل في carry، ويُستأنف أول جلسة تالية فيها حصته.
البوابة المستأنفة تُحسب من بوابات الجلسة التي اكتملت فيها ومن ميزانية بنودها، والجلستان تُحسبان في سقف
جلسات البحث. جلسة البدء لا بوابة فيها، فبوابة قطعها السقف في جلسة البحث الرابعة تُستأنف في أول جلسة متابعة.
والفحص يُستأنف بحدث check_resumed، وأنشطة الدرس بعد resume_lesson. بلا cap لا يتغير شيء.

فحوص الاحتفاظ (3.7، ك8): retention=True يعرض في أول جلسة المتابعة ما استحق منها، واحدًا في الجلسة والأقدم
استحقاقًا أولًا (تفسير: النص لا يحدد العدد، و«لا يتضاعف العمل»)، ويواصل الجلسات حتى تنتهي الفحوص الثلاثة.
"""
import itertools
from collections import Counter

from item_layer import (CALC, Activity, GateRun, ShortCheckRun, OpeningRun, EvidenceRun, CheckRun, RetentionRun,
                        drive, gate_plan)
from transition_engine import OPEN_CHECK

GATES_PER_SEARCH = {'older': 2, 'young': 1}
ITEM_BUDGET = 20          # بنود البوابات المخططة في جلسة بحث للكبيرين
SHORT_FOLLOW = 2          # تحققان قصيران على الأكثر في جلسة متابعة
SHORT_START = 4           # في جلسة البدء
SEARCH_CAP = 4
DONE = ('exempt', 'met')
DIAG = ('gate', 'comp', 'try', 'short')      # البنود التشخيصية
RETENTION_PER_SESSION = 1


class Capped(Exception):
    """بلغت الجلسة سقف وقتها: تُختم، وما لم يكتمل محفوظ في carry."""


def old_types(types):
    """أنواع البنود كما اختارتها المحاكاة القديمة، لوضع compat."""
    plan = gate_plan(types)
    und = [t for t in plan if t not in CALC]
    return dict(short=(und + plan)[:2] + [plan[0]], try_=[plan[0], (und or plan)[0]], guided=((und or plan) * 3)[:3])


class Scheduler:
    def __init__(self, engine, types, source, answer, group='older', start=None, scope=None, learning=False,
                 tolerant=True, compat=False, content_version=1, records=None, no_short=(), try_from_gate=True,
                 cap=None, item_seconds=None, retention=False):
        self.e, self.types, self.source, self.answer = engine, types, source, answer
        self.group, self.start, self.learning, self.tolerant, self.compat = group, start, learning, tolerant, compat
        self.ids = [s for s in engine.ids if scope is None or s in scope]
        self.inscope = set(self.ids)
        self.pre, self.anc, self.idx = engine.pre, engine.anc, engine.idx
        self.content_version, self.records = content_version, records
        self.no_short = set(no_short)       # للمقارنة في 6.2: قرار المعلم بالتأجيل يُسقط التحقق القصير أيضًا
        # 6.2 بقرار الأب (ك4): بندا «جرّب أولًا» من نوعي الخطأ في آخر بوابة أخفقت للمهارة، والثابتان إن لم تكن.
        # False يعيد القاعدة السابقة للقرار (البندان الثابتان دائمًا)، للمقارنة وحدها
        self.try_from_gate = try_from_gate
        self.cap, self.item_seconds = cap, item_seconds or (lambda w: 0)
        self.elapsed, self.carry, self.carried_items = 0, None, []
        self.retention = retention
        self.intent, self.pending, self.proven, self.attempt = [], [], {}, {}
        self.ev_round = {}                  # جولات دليل الفهم التي عُرضت بنودها لكل مهارة
        self.last_items = []                # معرّفات بنود آخر نشاط، تُرفق بأحداثه فيُحفظ الدليل ببنوده (3.5)
        self.n = Counter()
        self.gates_run = self.searches = self.sessions = 0
        self.day, self.cur = -1, None
        self.log, self.refused = [], []
        self.stalled = 0                                    # جلسة متابعة لم يجرِ فيها شيء: خطأ في السياسة
        self._ids = itertools.count(1)
        self.start_at = self.items_before = self.start_w = self.start_what = None

    # ---------------------------------------------------------------- المحرك
    def send(self, payload):
        ev = dict(payload, id='e%d' % next(self._ids))
        if payload['type'] in ('gate_result', 'short_check_result', 'open_lesson', 'resume_lesson',
                               'lesson_opening_result', 'understanding_proved', 'check_started',
                               'independence_result', 'check_resumed', 'check_held', 'recheck_result',
                               'retention_result', 'session_end'):
            ev.setdefault('session', self.cur)
        r = self.e.apply(ev)
        if not r['ok']:
            self.refused.append((ev, r))
        return r

    def ask(self, payload):
        """السؤال قبل عرض أول بند. الرفض هنا يعني أن المجدول اقترح ما لا يحق، فيُسجَّل ولا يُعرض شيء."""
        v = self.e.preflight(dict(payload, id='ask', session=self.cur))
        if not v['ok']:
            self.refused.append((payload, v))
        return v['ok']

    def begin(self, kind):
        self.day += 1
        self.sessions += 1
        self.cur = 'S%d' % self.sessions
        self.elapsed = 0
        self.send(dict(type='session_start', session=self.cur, kind=kind, day=self.day))

    def end(self):
        self.send(dict(type='session_end', session=self.cur))
        self.cur = None

    def view(self):
        e = self.e
        st = e.derive()
        helped = {a['skill'] for a in e.s['attempts'] if a['result'] == 'help' and a['what'] in ('gate', 'lesson')}
        gated = Counter(a['skill'] for a in e.s['attempts'] if a['what'] == 'gate' and a['result'] != 'interrupted'
                        and not e.s['sessions'][a['session']]['invalid'])
        return st, helped, gated

    def candidate(self, st, helped):
        for s in self.ids:
            if st[s] == 'stumbled' or (s in helped and st[s] in (None, 'deferred')):
                return s
        return None

    def blocked(self, s, st):
        return any(st[p] in ('stumbled', 'waiting') for p in self.pre[s])

    def regate_ready(self, s, st, gated):
        """6.1: البوابة الثانية، وكل بوابة بعد فتح الدرس، بعد اختصار الدرس وفي جلسة لاحقة، والإعادة لمتعثَّر
        فيها تحتاج السماح. الشرط نفسه في المحرك (can_gate_result)، والمجدول يحترمه قبل أن يقترح."""
        o = self.e.s['opened'].get(s)
        if gated[s] == 0 and not o:
            return True
        if gated[s] >= 2 or not o or o['phase'] != 'skipped':
            return False
        return st[s] != 'stumbled' or self.e.s['regate']

    # ---------------------------------------------------------------- الأنشطة
    def over(self):
        return self.cap is not None and self.elapsed >= self.cap

    def tick(self, w):
        self.elapsed += self.item_seconds(w)
        return self.over()

    def carried(self, kind, skill=None):
        """المهارة التي حُفظ لها نشاط من هذا النوع لم يكتمل، أو None."""
        c = self.carry
        return c['skill'] if c and c['kind'] == kind and skill in (None, c['skill']) else None

    def take(self, kind, skill):
        """النشاط المحفوظ لهذه المهارة إن كان، ليُستأنف من حيث توقف."""
        if not self.carried(kind, skill):
            return None
        c, self.carry = self.carry, None
        self.carried_items = c['items']
        return Activity.from_dict(c['act'])

    def drop_carry(self, why):
        self.log.append((self.sessions, 'carry_dropped:' + why, self.carry['skill']))
        self.carry, self.carried_items = None, []

    def cut(self, act, kind, items):
        """السقف: يُحفظ النشاط الذي بدأ. الذي لم يُعرض منه بند لا يُحفظ، إلا الفحص لأن محاولته بدأت في المحرك."""
        if sum(act.shown.values()) or kind == 'check':
            self.carry = dict(kind=kind, skill=act.skill, act=act.to_dict(), items=items)
        self.carried_items = []
        self.log.append((self.sessions, 'capped', act.skill))
        raise Capped()

    def run_act(self, act, kind=None):
        recs, before = [], Counter(act.shown)
        prior, self.carried_items = self.carried_items, []
        if self.over():                                     # الجلسة بلغت سقفها: لا يُعرض بند جديد
            self.cut(act, kind, prior)
        drive(act, self.source, self.answer, recs, pause=self.tick if self.cap is not None else None)
        if self.records is not None:
            self.records.extend(recs)
        items = prior + [r['item'] for r in recs if r.get('item')]
        self.n.update(act.shown - before)
        if not act.done:
            self.cut(act, kind, items)
        self.last_items = items
        return act

    def emit(self, act):
        """أحداث النشاط إلى المحرك، ومعها بنوده إن عُرفت."""
        for p in act.events():
            self.send(dict(p, items=self.last_items) if self.last_items else p)

    def still_ok(self, payload, kind):
        """قبل استئناف نشاط محفوظ: إن لم يعد يحق، يُترك ولا يُعدّ اقتراحًا مرفوضًا."""
        v = self.e.preflight(dict(payload, id='ask', session=self.cur))
        if not v['ok']:
            self.drop_carry(v['code'])
        return v['ok']

    def gate(self, s):
        if self.carried('gate', s):
            if not self.still_ok(dict(type='gate_result', skill=s, result='pass'), 'gate'):
                return None
        elif not self.ask(dict(type='gate_result', skill=s, result='pass')):
            return None
        act = self.take('gate', s) or GateRun(s, self.types[s], tolerant=self.tolerant,
                                              attempt=self.e.valid_gates(s) + 1)
        self.run_act(act, 'gate')
        self.gates_run += 1
        self.emit(act)
        return act.result

    def short(self, s):
        if self.carried('short', s):
            if not self.still_ok(dict(type='short_check_result', skill=s, ok=True), 'short'):
                return None
        elif not self.ask(dict(type='short_check_result', skill=s, ok=True)):
            return None
        act = self.take('short', s)
        if act is None:
            act = ShortCheckRun(s, self.types[s], stop_early=not self.compat)
            if self.compat:
                act.types = old_types(self.types[s])['short']
        self.run_act(act, 'short')
        self.emit(act)
        return act.result

    def last_gate_errors(self, s):
        for x in reversed(self.e.s['log']):
            if x['type'] == 'gate_result' and x['skill'] == s and x['result'] == 'fail':
                if not self.compat and self.e.s['sessions'][x['session']]['invalid']:
                    continue                                # بوابة جلسة أُبطلت لا يُبنى عليها
                return x.get('errors') or None
        return None

    def opening(self, s):
        """نتيجة افتتاح الدرس. الدرس يجب أن يكون نشطًا في الجلسة (فُتح أو استؤنف فيها)."""
        act = self.take('opening', s)
        if act is not None:
            pass
        elif self.compat:
            o = old_types(self.types[s])
            errs = self.last_gate_errors(s)
            act = OpeningRun(s, self.types[s], try_types=[errs[0], errs[-1]] if errs else o['try_'],
                             try_errors_count=True)
            act.guided = o['guided']
        else:
            errs = self.last_gate_errors(s) if self.try_from_gate else None
            act = OpeningRun(s, self.types[s], try_types=[errs[0], errs[-1]] if errs else None, typed=True)
        self.run_act(act, 'opening')
        self.emit(act)
        kind = 'skip' if act.result == 'skip' else 'lesson'
        self.log.append((self.sessions, kind, s))
        if kind == 'skip' and self.compat and (self.e.s['regate'] or self.e.direct(s) != 'stumbled'):
            self.pending.append(s)
        if kind == 'lesson' and self.learning:
            self.lesson_body(s)
        return kind

    def open_lesson(self, s):
        if not self.send(dict(type='open_lesson', skill=s))['ok']:
            return None
        return self.opening(s)

    def show(self, s, activity, k=0):
        """بنود الدرس أو التدريب: تُعرض ولا تصنع حدثًا للمحرك. مصدر المحاكاة المجرد لا يعيد منها شيئًا."""
        while True:
            if self.over():                                 # السقف: يُستأنف العرض من موضعه في جلسة لاحقة
                self.carry = dict(kind='show', skill=s, activity=activity, pos=k, items=[])
                self.log.append((self.sessions, 'capped', s))
                raise Capped()
            w = dict(activity=activity, pos=k, role=activity)
            item = self.source(s, dict(activity=activity, pos=k))
            if item is None:
                return k
            self.answer(item, w)
            self.n[activity] += 1
            self.elapsed += self.item_seconds(w)
            k += 1

    def lesson_body(self, s, k=0):
        self.show(s, 'lesson', k)
        self.evidence(s)

    def evidence(self, s):
        if not self.ask(dict(type='understanding_proved', skill=s)):
            return None
        act = self.take('evidence', s) or EvidenceRun(s, self.types[s], proven=self.proven.get(s, []),
                                                      round=self.ev_round.get(s, 0) + 1)
        self.run_act(act, 'evidence')
        if act.shown['evidence']:
            self.ev_round[s] = act.round                    # الجولة التالية ببنود جديدة
        self.proven[s] = list(act.proven)
        self.emit(act)
        if act.result != 'proven':
            self.log.append((self.sessions, 'evidence_' + act.result, s))
        return act.result

    def check(self, s):
        act = self.take('check', s)                         # محاولة قطعها السقف: استؤنفت بحدث check_resumed
        if act is None:
            k = self.attempt.get(s, 0)
            act = CheckRun(s, '%s/check/%d' % (s, k + 1), self.content_version, attempt=chr(ord('A') + k))
            if not self.send(act.start_event())['ok']:
                return None
            self.attempt[s] = k + 1
        self.run_act(act, 'check')
        self.emit(act)
        self.log.append((self.sessions, 'check_' + act.result, s))
        return act.result

    def retention_check(self, s, rnd):
        """فحص احتفاظ مستحق (3.7): 5 بنود جولته، ونتيجته حدث retention_result."""
        if self.carried('retention', s):
            if not self.still_ok(dict(type='retention_result', skill=s, correct=0), 'retention'):
                return None
        elif not self.ask(dict(type='retention_result', skill=s, correct=0)):
            return None
        act = self.take('retention', s) or RetentionRun(s, rnd)
        self.run_act(act, 'retention')
        self.emit(act)
        self.log.append((self.sessions, 'retention_%s' % (act.correct if act.result else 'cut'), s))
        return act.result

    def recall(self):
        """«استرجع» في أول الجلسة: فحص احتفاظ قطعه السقف، ثم ما استحق، الأقدم استحقاقًا أولًا."""
        if not self.retention:
            return
        done = 0
        s = self.carried('retention')
        if s:
            self.retention_check(s, None)
            done += 1
        for s, rnd, _due in self.e.retention_due(self.day):
            if done >= RETENTION_PER_SESSION:
                break
            self.retention_check(s, rnd)
            done += 1

    # ---------------------------------------------------------------- سياسة التشخيص (6.2)
    def next_gate(self):
        st, helped, gated = self.view()
        fresh_ok = lambda x: st[x] is None and gated[x] == 0
        c = self.candidate(st, helped)
        if self.group == 'young':
            if c is not None:
                return None
            fresh = [x for x in self.ids if fresh_ok(x)]
            return fresh[0] if fresh else None
        if self.gates_run == 0 and self.start in self.inscope and st[self.start] is None:
            return self.start
        if c is not None:
            if self.e.eligible(c, 'follow', st)['ok']:
                return None                                 # نقطة العمل محسومة
            fresh = [a for a in sorted(self.anc[c] & self.inscope, key=self.idx.get) if fresh_ok(a)]
            if fresh:
                def split(a):
                    below = sum(1 for b in self.anc[a] & self.inscope if st[b] is None)
                    return min(below + 1, len(fresh) - below)
                return max(fresh, key=split)
            need = [p for p in sorted(self.pre[c], key=self.idx.get) if st[p] not in DONE and p in self.inscope]
            return need[0] if need else None
        fresh = [x for x in self.ids if fresh_ok(x)]
        if not fresh:
            return None
        desc = {x: [d for d in self.ids if x in self.anc[d]] for x in fresh}

        def split(x):
            below = sum(1 for b in self.anc[x] & self.inscope if st[b] is None)
            above = sum(1 for d in desc[x] if st[d] is None)
            return min(below + 1, above + 1)
        return max(fresh, key=split)

    def gate_size(self, x):
        """بنود البوابة المخططة، أو ما بقي منها إن قطعها السقف (ك9: تُحسب من ميزانية الجلسة التي تكتمل فيها)."""
        if self.carried('gate', x):
            a = self.carry['act']
            return len(a['plan']) - a['pos'] if a['stage'] == 'main' else 2 - a['pos']
        return len(gate_plan(self.types[x]))

    def search(self):
        while self.searches < SEARCH_CAP:
            x = self.carried('gate') or self.next_gate()    # بوابة قطعها السقف تُستأنف أول الجلسة التالية
            if x is None:
                return
            self.begin('search')
            self.searches += 1
            budget, done = ITEM_BUDGET, 0
            try:
                while x is not None and done < GATES_PER_SEARCH[self.group]:
                    size = self.gate_size(x)
                    if done and size > budget:
                        break
                    budget -= size
                    self.gate(x)
                    done += 1
                    x = self.next_gate()
            except Capped:
                pass
            self.end()

    def working_point(self):
        st, helped, gated = self.view()
        w = self.candidate(st, helped)
        if w is None:
            w = next((x for x in self.ids if st[x] is None), None)
        if w is None:
            return None
        verified = {x['skill'] for x in self.e.valid_evidence(kind='short_ok')}
        k = 0
        while True:
            moved = False
            for p in sorted(self.pre[w], key=self.idx.get):
                if st[p] in DONE or p in verified or p not in self.inscope:
                    continue
                if k == SHORT_START:
                    return w
                k += 1
                res = self.short(p)
                if res is True:
                    verified.add(p)
                elif res is False:
                    w, moved = p, True
                    break
            if not moved:
                return w

    def start_session(self):
        self.begin('start')
        self.start_at = self.sessions
        w, what = None, 'none'
        try:
            w = self.working_point()
            self.items_before = sum(self.n[c] for c in DIAG)
            if w is not None:
                if self.e.eligible(w, 'start')['ok']:
                    what = self.open_lesson(w) or 'none'
                else:
                    what = 'use'
                    st, helped, gated = self.view()
                    if st[w] in (None, 'deferred') and gated[w] == 0:
                        target = self.pending if self.compat else self.intent
                        if w not in target:
                            target.insert(0, w)
        except Capped:
            what = 'capped'                                 # السقف قطع جلسة البدء: ما لم يكتمل في carry
            if self.items_before is None:
                self.items_before = sum(self.n[c] for c in DIAG)
        if what in ('none', 'use'):
            self.log.append((self.sessions, what, w))
        self.start_w, self.start_what = w, what
        self.end()

    def gate_queue(self):
        if self.compat:
            return list(self.pending)
        return self.intent + [q for q in self.e.s['queue'] if q not in self.intent]

    def drop(self, x):
        for lst in (self.pending, self.intent):
            if x in lst:
                lst.remove(x)

    def pick_gate(self):
        st, helped, gated = self.view()
        opened = self.e.s['opened']
        for x in self.gate_queue():
            o = opened.get(x)
            if (o and o['phase'] in ('full', 'due')) or gated[x] >= 2 or st[x] in DONE:
                self.drop(x)
            elif not self.compat and not self.regate_ready(x, st, gated):
                continue        # تبقى في الطابور: مهارة انتهت بوابتها بطلب دعم، تُعاد بوابتها بعد اختصار درسها
            elif not self.blocked(x, st):
                self.drop(x)
                return x
        for s in self.ids:
            if (st[s] == 'stumbled' or (s in helped and st[s] in (None, 'deferred'))) and s not in opened:
                v = self.e.eligible(s, 'follow', st)
                p = v.get('missing')
                if not v['ok'] and p in self.inscope and st[p] in (None, 'deferred') and p not in helped \
                        and p not in opened and gated[p] == 0:
                    return p
        if not any(o['phase'] in ('full', 'due') for o in opened.values()):
            g = self.next_gate()
            if g is not None and g not in opened and g not in helped and gated[g] == 0 and not self.blocked(g, st):
                return g
        for x in self.ids:
            if st[x] is None and x not in opened and x not in helped:
                return x
        return None

    def pick_short(self):
        st = self.e.derive()
        checked = set(self.e.s['checked'])
        return next((x for x in self.ids if st[x] == 'deferred' and x not in checked and x not in self.no_short),
                    None)

    def pick_lesson(self):
        st, helped, gated = self.view()
        for s in self.ids:
            if (st[s] == 'stumbled' or (s in helped and st[s] in (None, 'deferred'))) and s not in self.e.s['opened'] \
                    and self.e.eligible(s, 'follow', st)['ok']:
                return s
        return None

    def follow(self):
        """جلسة متابعة في وضع التشخيص: بوابة، ثم تحققان قصيران، ثم الحصة التعليمية إن لم تُستهلك."""
        g = self.carried('gate') or self.pick_gate()
        if g is None and self.carry is None and self.pick_short() is None and self.pick_lesson() is None:
            return False
        self.begin('follow')
        shown = sum(self.n.values())
        taught = capped = False
        try:
            if g is not None:
                was_open = g in self.e.s['opened']
                r = self.gate(g)
                if was_open and r in ('fail', 'help'):
                    taught = True                           # المحرك أمضى الدرس كاملًا واستهلك الحصة
                    self.log.append((self.sessions, 'lesson', g))
                    if self.learning:
                        self.lesson_body(g)
            for _ in range(SHORT_FOLLOW):
                x = self.carried('short') or self.pick_short()
                if x is None:
                    break
                if self.short(x) is False and self.compat:
                    self.pending.append(x)
            if not taught:
                if self.learning:
                    taught = self.teach()
                elif self.carried('opening'):               # افتتاح قطعه السقف: يُستأنف درسه ثم يُكمل
                    o = self.carried('opening')
                    if self.still_ok(dict(type='resume_lesson', skill=o), 'opening'):
                        self.send(dict(type='resume_lesson', skill=o))
                        self.opening(o)
                else:
                    o = self.pick_lesson()
                    if o is not None:
                        self.open_lesson(o)
        except Capped:
            capped = True
        self.end()
        if sum(self.n.values()) == shown and not taught and not capped and not self.compat:
            # لم يُعرض بند: خطأ في السياسة، فتتوقف المحاكاة ويُعدّ مخالفة. في وضع compat تمضي الجلسة كما في
            # القديمة، وفيه وحده يرفض المحرك اقتراحًا (البوابة الثانية بلا فتح الدرس، 8.2 في المواصفة)
            self.stalled += 1
            return False
        return True

    # ---------------------------------------------------------------- مسار التعلّم
    def teach(self):
        """الحصة التعليمية في وضع التعلّم: درس جارٍ، ثم فحص مستحق أو جلسة تدريب قبله، ثم درس جديد."""
        c = self.carry
        if c and c['kind'] in ('opening', 'evidence', 'show', 'check'):
            # نشاط قطعه السقف: يُستأنف أولًا. الفحص بحدث check_resumed، وأنشطة الدرس بعد resume_lesson
            s = c['skill']
            if c['kind'] == 'check':
                need = dict(type='check_resumed', skill=s, check_id=c['act']['check_id'])
            else:
                need = None if self.e.s['opened'][s]['active'] == self.cur else dict(type='resume_lesson', skill=s)
            v = self.e.preflight(dict(need, id='ask', session=self.cur)) if need else dict(ok=True)
            if not v['ok'] and v['code'] == 'quota_teach':
                return False                                # تبقى محفوظة لجلسة فيها الحصة
            if not v['ok']:
                self.drop_carry(v['code'])
            else:
                if need:
                    self.send(need)
                if c['kind'] == 'check':
                    self.check(s)
                elif c['kind'] == 'opening':
                    self.opening(s)
                elif c['kind'] == 'evidence':
                    self.evidence(s)
                else:
                    self.carry = None
                    if c['activity'] == 'lesson':
                        self.lesson_body(s, c['pos'])
                    else:
                        self.show(s, 'practice', c['pos'])
                return True
        st = self.e.derive()
        for s in self.ids:
            o = self.e.s['opened'].get(s)
            if not o or s in self.e.s['suspended'] or st[s] in DONE or o['phase'] == 'skipped':
                continue
            if o['phase'] == 'due' or not self.e.progress(s)[1]:
                if o['active'] != self.cur and not self.send(dict(type='resume_lesson', skill=s))['ok']:
                    continue
                if self.e.s['opened'][s]['phase'] == 'opening':
                    self.opening(s)
                else:
                    self.lesson_body(s)
                return True
        for s in self.ids:
            o = self.e.s['opened'].get(s)
            if not o or s in self.e.s['suspended'] or st[s] in DONE or not self.e.progress(s)[1]:
                continue
            pend = [c for c in self.e.s['checks'].values() if c['skill'] == s and c['state'] in OPEN_CHECK]
            if pend:
                # معلَّق للمراجعة أو يحتاج إعادة بدء: ينتظر المعلم. والمعلَّقة غير المكتملة لا تقع هنا، لأن المجدول
                # يكمل الفحص في جلسته؛ استئنافها في جلسة لاحقة حدث check_resumed في المحرك
                continue
            k = self.attempt.get(s, 0)
            v = self.e.preflight(dict(type='check_started', id='ask', session=self.cur, skill=s,
                                      check_id='%s/check/%d' % (s, k + 1), content_version=self.content_version))
            if v['ok']:
                self.check(s)
                return True
            if v['code'] == 'check_needs_practice' and self.send(dict(type='resume_lesson', skill=s))['ok']:
                self.show(s, 'practice')
                self.log.append((self.sessions, 'practice', s))
                return True
        o = self.pick_lesson()
        if o is not None:
            self.open_lesson(o)
            return True
        return False

    def satisfied(self):
        st = self.e.derive()
        return all(st[s] in DONE for s in self.ids)

    # ---------------------------------------------------------------- التشغيل
    def run(self, max_sessions=200):
        self.search()
        self.start_session()
        if self.learning:
            while self.sessions < max_sessions and not (self.satisfied() and self.carry is None and not (
                    self.retention and self.e.retention_pending())):
                self.follow_learning()
        else:
            while self.follow():
                pass
        return self.start_w, self.start_what

    def follow_learning(self):
        """جلسة متابعة في وضع التعلّم. تُعقد ولو لم يكن فيها غير «استرجع»، فالأيام تمضي."""
        self.begin('follow')
        taught = False
        try:
            self.recall()
            g = self.carried('gate') or self.pick_gate()
            if g is not None:
                was_open = g in self.e.s['opened']
                r = self.gate(g)
                if was_open and r in ('fail', 'help'):
                    taught = True
                    self.log.append((self.sessions, 'lesson', g))
                    if self.e.s['opened'][g]['phase'] == 'full':
                        self.lesson_body(g)
            for _ in range(SHORT_FOLLOW):
                x = self.carried('short') or self.pick_short()
                if x is None:
                    break
                self.short(x)
            if not taught:
                self.teach()
        except Capped:
            pass
        self.end()
