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
بعد البند الذي يبلغه تُختم الجلسة، ويُحفظ النشاط غير المكتمل في saved، ويُستأنف أول جلسة تالية فيها حصته.

الأنشطة المحفوظة (المراجعة 13): saved قائمة، لكل نشاط مدخل بمفتاحه (نوعه ومهارته). بدء نشاط آخر أو بلوغه السقف لا
يستبدل نشاطًا محفوظًا: cut يضيف ولا يكتب فوق شيء، وحفظ مفتاح محفوظ من قبل خطأ صريح. وأولوية الاستئناف في جلسة
المتابعة بترتيب أجزائها: فحص الاحتفاظ المحفوظ ثم المستحق، ثم البوابة المحفوظة، ثم التحقق القصير المحفوظ، ثم الحصة
التعليمية: نشاطها المحفوظ، ثم المركون، ثم الجديد. كل نشاط يُستأنف من موضعه.
البوابة المستأنفة تُحسب من بوابات الجلسة التي اكتملت فيها ومن ميزانية بنودها، والجلستان تُحسبان في سقف
جلسات البحث. جلسة البدء لا بوابة فيها، فبوابة قطعها السقف في جلسة البحث الرابعة تُستأنف في أول جلسة متابعة.
والفحص يُستأنف بحدث check_resumed، وأنشطة الدرس بعد resume_lesson. بلا cap لا يتغير شيء.

فحوص الاحتفاظ (3.7، ك8): retention=True يعرض في أول جلسة المتابعة ما استحق منها، واحدًا في الجلسة والأقدم
استحقاقًا أولًا (تفسير: النص لا يحدد العدد، و«لا يتضاعف العمل»)، ويواصل الجلسات حتى تنتهي الفحوص الثلاثة.
"""
import functools
import itertools
from collections import Counter

from item_layer import (CALC, Activity, GateRun, ShortCheckRun, OpeningRun, EvidenceRun, CheckRun, RetentionRun,
                        drive_steps, run_sync, gate_plan, fold_item, exposure)
from transition_engine import OPEN_CHECK

GATES_PER_SEARCH = {'older': 2, 'young': 1}
ITEM_BUDGET = 20          # بنود البوابات المخططة في جلسة بحث للكبيرين
SHORT_FOLLOW = 2          # تحققان قصيران على الأكثر في جلسة متابعة
SHORT_START = 4           # في جلسة البدء
SEARCH_CAP = 4
DONE = ('exempt', 'met')
DIAG = ('gate', 'comp', 'try', 'short')      # البنود التشخيصية
RETENTION_PER_SESSION = 1
TEACH_KINDS = ('opening', 'evidence', 'show', 'check')     # أنشطة الحصة التعليمية
# أسباب رفض استئناف نشاط محفوظ (المراجعة 11، الملاحظة الأولى). النهائية وحدها تُسقطه: لم يعد في المحرك ما يُستأنف.
# الخاصة بالجلسة تُبقيه في saved حتى جلسة فيها الحصة وتاريخها مؤكد، ولا يُعلَّم فيها غيره. وما سواها مؤقت يخص
# المهارة (توقيت الفحص، تعليق الدرس): يُركن النشاط بتقدّمه في parked، وتمضي الجلسة، ويُستأنف أول جلسة يُقبل فيها
FINAL_REFUSALS = ('check_state', 'no_check', 'version_unavailable', 'already_satisfied', 'unknown_skill', 'bad_event')
SESSION_REFUSALS = ('date_unconfirmed', 'no_session')


def refusal_kind(code):
    if code in FINAL_REFUSALS:
        return 'final'
    if code in SESSION_REFUSALS or code.startswith('quota_'):
        return 'session'
    return 'later'


class Capped(Exception):
    """بلغت الجلسة سقف وقتها: تُختم، وما لم يكتمل محفوظ في saved."""


class Halted(Capped):
    """تغيّرت صلاحية النشاط الجاري أثناءه (المراجعة 16): لا يتقدم ولا تُحتسب الإجابة. حُفظ أو رُكن أو أُسقط بقاعدة
    سبب الرفض، وتُختم الجلسة كما تُختم عند السقف."""


def exposed(raw):
    """هل وقع في البند ما يتجاوز رؤية السؤال: إجابة مؤكدة أو طلب دعم؟ (R18-01)"""
    return any(ev[0] in ('confirm', 'support') for ev in raw)


class Void:
    """ما ترسله طبقة الخطوات بدل الإجابة حين تجد النشاط الجاري غير صالح. answered: هل حاول الطفل الإجابة الآن؟
    ومعه ما سُجّل في البند قبل تغيّر الصلاحية (R17-01): هل عُرض، وأحداثه الخام، وجوابه الصحيح ونوعه. الحدث الذي
    كشف التغيّر ليس منها."""

    def __init__(self, answered, shown=False, raw=(), answer=None, assess=False):
        self.answered, self.shown = answered, shown
        self.raw, self.answer, self.assess = [tuple(x) for x in raw], answer, assess


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
        self.elapsed, self.saved, self.carried_items = 0, [], []
        self.parked = {}                    # مهارة ← نشاط تعليمي محفوظ رُفض استئنافه رفضًا مؤقتًا يخص المهارة
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
        # موضع الجلسة الجارية بين أجزائها (المرحلة 0ج): به تُكمَل الجلسة نفسها بعد إغلاق التطبيق، فلا تُستهلك جلسة
        # ولا حصة ولا يتجدد الوقت. يُحفظ مع الحالة. و live النشاط المعروض الآن، للّقطة، ولا يُحفظ بنفسه
        self.stage, self.live, self.today = None, None, None
        self.last = None                    # آخر بند عُرض في الجلسة المفتوحة (seen)، للتتابع بين الأنشطة (R22-01)
        self.halts = []                     # توقفات هذا التشغيل لتغيّر الصلاحية: (الجلسة، السبب، المهارة، النوع). للبالغ

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
        # today: يوم الأسرة يضعه التطبيق قبل بدء الجلسة. بلا قيمة يمضي يوم لكل جلسة، كما في المحاكاة
        self.day = self.day + 1 if self.today is None else self.today
        self.sessions += 1
        self.cur = 'S%d' % self.sessions
        self.elapsed = 0
        self.stage = dict(kind=kind, recall=False, gate=None, gate_done=False, done=0, budget=ITEM_BUDGET, shorts=0,
                          shorts_done=False, teach=False, lesson=None, after=None, w=None, what=None)
        self.send(dict(type='session_start', session=self.cur, kind=kind, day=self.day))

    def end(self):
        self.send(dict(type='session_end', session=self.cur))
        self.cur = self.stage = self.last = None

    def seen(self, skill, activity, item, got=None):
        """آخر بند عُرض في الجلسة (R22-01): مهارته ونشاطه ومعرّفه وحقيقته. counts: هل يُحتسب تعرّضًا؟ لا يُحتسب بند
        انقطع ولم تُقبل قبل انقطاعه إجابة ولم يُقدَّم فيه دعم (R22-02): وصف السجل بأنه منقطع لا يكفي. البنود التي لا
        تحمل حقيقة (مصادر المحاكاة المجردة) لا تُسجَّل، فلا تتغير الحالة المحفوظة في غير المحتوى الفعلي."""
        if not isinstance(item, dict) or item.get('fact') is None:
            self.last = None
            return
        if isinstance(got, str):
            counts = got != 'interrupted'
        elif isinstance(got, (tuple, list)):
            raw = got[0]
            counts = exposed(raw) or not (raw and raw[-1][0] == 'interrupt')
        else:
            counts = True
        self.last = dict(session=self.cur, skill=skill, activity=activity, item=item.get('id'),
                         fact=list(item['fact']), counts=counts)

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

    def entry(self, kind, skill=None):
        """النشاط المحفوظ من هذا النوع، ولهذه المهارة إن ذُكرت، أو None."""
        return next((c for c in self.saved if c['kind'] == kind and skill in (None, c['skill'])), None)

    def carried(self, kind, skill=None):
        """المهارة التي حُفظ لها نشاط من هذا النوع لم يكتمل، أو None."""
        c = self.entry(kind, skill)
        return c['skill'] if c else None

    def save(self, c):
        """حفظ نشاط لم يكتمل. لا يُستبدل به نشاط محفوظ: المفتاح نوعه ومهارته، ولا يُحفظ مرتين."""
        if self.entry(c['kind'], c['skill']) is not None:
            raise RuntimeError('نشاط محفوظ بالمفتاح نفسه: %s %s' % (c['kind'], c['skill']))
        self.saved.append(c)

    def unsave(self, c):
        self.saved = [x for x in self.saved if x is not c]

    def take(self, kind, skill):
        """النشاط المحفوظ لهذه المهارة إن كان، ليُستأنف من حيث توقف."""
        c = self.entry(kind, skill)
        if c is None:
            return None
        self.unsave(c)
        self.carried_items = c['items']
        return Activity.from_dict(c['act'])

    def drop_carry(self, why, c):
        self.log.append((self.sessions, 'carry_dropped:' + why, c['skill']))
        self.unsave(c)
        self.carried_items = []

    def invalid(self, kind, skill, check_id=None):
        """سبب رفض المحرك لاستمرار هذا النشاط في الجلسة الجارية، أو None إن كان صالحًا."""
        v = self.e.may_continue(kind, self.cur, skill, check_id)
        return None if v['ok'] else v['code']

    def live_invalid(self):
        """سبب عدم صلاحية النشاط المعروض الآن، أو None. تسأله طبقة الخطوات قبل العرض وقبل قبول أي حدث."""
        v = self.live
        if v is None:
            return None
        if v['kind'] == 'show':
            return self.invalid('show', v['skill'])
        return self.invalid(v['kind'], v['act'].skill, getattr(v['act'], 'check_id', None))

    def halt(self, code, entry, started, answered, void=None, about=None):
        """النشاط الجاري لم يعد صالحًا: لا يتقدم. مصيره بقاعدة سبب الرفض كما عند استئناف نشاط محفوظ: الرفض الخاص
        بالجلسة يُبقيه محفوظًا، والمؤقت الخاص بالمهارة يركن النشاط التعليمي بتقدّمه، وما عداهما يُسقطه. ما أُنجز منه
        باقٍ في السجلات. وإجابة جاءت بعد تغيّر الصلاحية لا تُحتسب دليلًا ولا خطأً.
        void و about: البند المعروض عند التوقف وما سُجّل فيه قبل تغيّر الصلاحية (R17-01). تاريخه يُحفظ في سجلات
        البنود مع سبب استبعاده (void)، ولا يُعطى للنشاط ولا يدخل عدّادًا ولا مؤشرًا: الحفظ غير الاستعمال في التقييم."""
        if void is not None and void.shown and about is not None and self.records is not None:
            rec = fold_item(void.raw + [('interrupt',)], void.answer, void.assess)
            self.records.append(dict(rec, skill=entry['skill'], activity=about['activity'], role=about['role'],
                                     item=about['item'], void=code))
        self.live, self.carried_items = None, []
        k, skill = refusal_kind(code), entry['skill']
        if k == 'session' and started:
            self.save(entry)
            what = 'carry_kept'
        elif k == 'later' and entry['kind'] in TEACH_KINDS and started:
            self.parked[skill] = entry
            what = 'carry_parked'
        else:
            what = 'carry_dropped'
        self.log.append((self.sessions, what + ':' + code, skill))
        if answered:
            self.log.append((self.sessions, 'answer_void:' + code, skill))
        self.halts.append((self.cur, code, skill, entry['kind']))
        raise Halted(code)

    def resume_verdict(self, c, need):
        """حكم المحرك على استئناف نشاط تعليمي محفوظ. بحدث استئناف: قبول الحدث. وبلا حدث، لأن النشاط من هذه الجلسة
        نفسها فلا حصة جديدة: صلاحية استمراره الآن. سبق الإذن ليس إذنًا دائمًا (R16-01)."""
        if need:
            return self.e.preflight(dict(need, id='ask', session=self.cur))
        return self.e.may_continue(c['kind'], self.cur, c['skill'],
                                   c['act']['check_id'] if c['kind'] == 'check' else None)

    def resume_need(self, c):
        """حدث استئناف نشاط تعليمي محفوظ: check_resumed للفحص، و resume_lesson لأنشطة الدرس إن لم يكن نشطًا."""
        s = c['skill']
        if c['kind'] == 'check':
            ch = self.e.s['checks'].get(c['act']['check_id'])
            if ch and self.cur in ch['sessions']:           # المحاولة بدأت أو استؤنفت في هذه الجلسة نفسها
                return None
            return dict(type='check_resumed', skill=s, check_id=c['act']['check_id'])
        return None if self.e.s['opened'][s]['active'] == self.cur else dict(type='resume_lesson', skill=s)

    def cut(self, act, kind, items):
        """السقف: يُحفظ النشاط الذي بدأ. الذي لم يُعرض منه بند لا يُحفظ، إلا الفحص لأن محاولته بدأت في المحرك."""
        if sum(act.shown.values()) or kind == 'check':
            self.save(dict(kind=kind, skill=act.skill, act=act.to_dict(), items=items))
        self.carried_items = []
        self.log.append((self.sessions, 'capped', act.skill))
        raise Capped()

    def g_run_act(self, act, kind=None):
        recs, mark = [], [Counter(act.shown), 0]
        prior, self.carried_items = self.carried_items, []
        if self.over():                                     # الجلسة بلغت سقفها: لا يُعرض بند جديد
            self.cut(act, kind, prior)
        self.live = dict(kind=kind, act=act, prior=prior, recs=recs)

        def settle():
            # كل بند خُتم يدخل عدّاداته وسجلّه مرة واحدة، في الانتقال نفسه الذي يتقدم فيه النشاط (R16-03). فاللقطة
            # عند أي طلب بند تحمل عدّادات وسجلات متوافقة مع تقدّم النشاط، والاستعادة لا تُسقط احتسابًا ولا تكرره
            self.n.update(act.shown - mark[0])
            mark[0] = Counter(act.shown)
            if self.records is not None:
                self.records.extend(recs[mark[1]:])
            mark[1] = len(recs)
        def guard(got=None):
            # الصلاحية تُفحص قبل عرض البند، ومرة أخرى قبل تطبيق الإجابة (R16-01). قرار يقع بينهما يوقف النشاط
            code = self.invalid(kind, act.skill, getattr(act, 'check_id', None))
            if code is None:
                if isinstance(got, Void):
                    raise RuntimeError('طبقة الخطوات أبطلت بندًا والمحرك يراه صالحًا')
                return
            item, w = req
            if isinstance(got, Void) and got.shown:         # التعرّض للبند باقٍ وإن استُبعد من التقييم (R18-01)
                act.voided(item.get('id') if isinstance(item, dict) else None, exposed(got.raw))
            entry = dict(kind=kind, skill=act.skill, act=act.to_dict(),
                         items=prior + [r['item'] for r in recs if r.get('item')])
            self.halt(code, entry, bool(sum(act.shown.values())) or kind == 'check',
                      got is not None and not (isinstance(got, Void) and not got.answered),
                      void=got if isinstance(got, Void) else None,
                      about=dict(activity=act.name, role=w['role'], item=item.get('id') if isinstance(item, dict) else None))
        req = None
        # تاريخ التعرّض من السجلات، لا من كائن النشاط: يبقى بعد إسقاط النشاط وإنشاء غيره (R19-01). لدليل الفهم وافتتاح الدرس
        history = (lambda a: exposure(self.records, a.skill, a.name)) if kind in ('evidence', 'opening') else None

        def prev():
            # آخر بند عُرض للمهارة نفسها في الجلسة نفسها من نشاط آخر، إن كان يُحتسب تعرّضًا (R22-01)
            x = self.last
            if x and x['session'] == self.cur and x['skill'] == act.skill and x['activity'] != act.name and x['counts']:
                return x['item'], x['fact']
            return None
        gen = drive_steps(act, self.source, recs, pause=self.tick if self.cap is not None else None, history=history,
                          prev=prev)
        try:
            req = next(gen)
            while True:
                guard()
                got = yield req
                guard(got)
                self.seen(act.skill, act.name, req[0], got)
                req = gen.send(got)
                settle()
        except StopIteration:
            pass
        settle()
        self.live = None
        items = prior + [r['item'] for r in recs if r.get('item')]
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
        if not v['ok'] and refusal_kind(v['code']) != 'session':
            self.drop_carry(v['code'], self.entry(kind, payload['skill']))   # رفض الجلسة (حصتها، تاريخها) لا يُسقطه
        return v['ok']

    def g_gate(self, s):
        if self.carried('gate', s):
            if not self.still_ok(dict(type='gate_result', skill=s, result='pass'), 'gate'):
                return None
        elif not self.ask(dict(type='gate_result', skill=s, result='pass')):
            return None
        act = self.take('gate', s) or GateRun(s, self.types[s], tolerant=self.tolerant,
                                              attempt=self.e.valid_gates(s) + 1)
        (yield from self.g_run_act(act, 'gate'))
        self.gates_run += 1
        self.emit(act)
        return act.result

    def g_short(self, s):
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
        (yield from self.g_run_act(act, 'short'))
        self.emit(act)
        return act.result

    def last_gate_errors(self, s):
        for x in reversed(self.e.s['log']):
            if x['type'] == 'gate_result' and x['skill'] == s and x['result'] == 'fail':
                if not self.compat and self.e.s['sessions'][x['session']]['invalid']:
                    continue                                # بوابة جلسة أُبطلت لا يُبنى عليها
                return x.get('errors') or None
        return None

    def g_opening(self, s):
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
        (yield from self.g_run_act(act, 'opening'))
        self.emit(act)
        kind = 'skip' if act.result == 'skip' else 'lesson'
        self.log.append((self.sessions, kind, s))
        if self.stage is not None:
            self.stage['what'] = kind
        if kind == 'skip' and self.compat and (self.e.s['regate'] or self.e.direct(s) != 'stumbled'):
            self.pending.append(s)
        if kind == 'lesson' and self.learning:
            (yield from self.g_lesson_body(s))
        return kind

    def g_open_lesson(self, s):
        if not self.send(dict(type='open_lesson', skill=s))['ok']:
            return None
        return (yield from self.g_opening(s))

    def g_show(self, s, activity, k=0):
        """بنود الدرس أو التدريب: تُعرض ولا تصنع حدثًا للمحرك. مصدر المحاكاة المجرد لا يعيد منها شيئًا."""
        while True:
            if self.over():                                 # السقف: يُستأنف العرض من موضعه في جلسة لاحقة
                self.save(dict(kind='show', skill=s, activity=activity, pos=k, items=[]))
                self.log.append((self.sessions, 'capped', s))
                raise Capped()
            w = dict(activity=activity, pos=k, role=activity)
            item = self.source(s, dict(activity=activity, pos=k))
            if item is None:
                return k
            self.live = dict(kind='show', skill=s, activity=activity, pos=k)
            entry = dict(kind='show', skill=s, activity=activity, pos=k, items=[])
            code = self.invalid('show', s)                  # قبل العرض (R16-01)
            if code is not None:
                self.halt(code, entry, True, False)
            got = yield item, w                             # الإجابة تأتي من الغلاف المتزامن أو من الواجهة
            code = self.invalid('show', s)                  # وقبل احتساب البند معروضًا
            if code is not None:
                self.halt(code, entry, True, not (isinstance(got, Void) and not got.answered))
            self.live = None
            self.n[activity] += 1
            self.elapsed += self.item_seconds(w)
            self.seen(s, activity, item)
            k += 1

    def g_lesson_body(self, s, k=0):
        (yield from self.g_show(s, 'lesson', k))
        (yield from self.g_evidence(s))

    def g_evidence(self, s):
        if not self.ask(dict(type='understanding_proved', skill=s)):
            return None
        act = self.take('evidence', s) or EvidenceRun(s, self.types[s], proven=self.proven.get(s, []),
                                                      round=self.ev_round.get(s, 0) + 1)
        (yield from self.g_run_act(act, 'evidence'))
        if act.shown['evidence'] or act.result == 'no_alternate':
            self.ev_round[s] = act.round                    # الجولة التالية ببنود جديدة. ومنها جولة نفد بديل أول بنودها
        self.proven[s] = list(act.proven)
        self.emit(act)
        if act.result != 'proven':
            self.log.append((self.sessions, 'evidence_' + act.result, s))
        return act.result

    def g_check(self, s):
        act = self.take('check', s)                         # محاولة قطعها السقف: استؤنفت بحدث check_resumed
        if act is None:
            k = self.attempt.get(s, 0)
            act = CheckRun(s, '%s/check/%d' % (s, k + 1), self.content_version, attempt=chr(ord('A') + k))
            if not self.send(act.start_event())['ok']:
                return None
            self.attempt[s] = k + 1
        (yield from self.g_run_act(act, 'check'))
        self.emit(act)
        self.log.append((self.sessions, 'check_' + act.result, s))
        return act.result

    def g_retention_check(self, s, rnd):
        """فحص احتفاظ مستحق (3.7): 5 بنود جولته، ونتيجته حدث retention_result."""
        if self.carried('retention', s):
            if not self.still_ok(dict(type='retention_result', skill=s, correct=0), 'retention'):
                return None
        elif not self.ask(dict(type='retention_result', skill=s, correct=0)):
            return None
        act = self.take('retention', s) or RetentionRun(s, rnd)
        (yield from self.g_run_act(act, 'retention'))
        self.emit(act)
        self.log.append((self.sessions, 'retention_%s' % (act.correct if act.result else 'cut'), s))
        return act.result

    def g_recall(self):
        """«استرجع» في أول الجلسة: فحص احتفاظ قطعه السقف، ثم ما استحق، الأقدم استحقاقًا أولًا."""
        if not self.retention:
            return
        done = 0
        s = self.carried('retention')
        if s:
            (yield from self.g_retention_check(s, None))
            done += 1
        for s, rnd, _due in self.e.retention_due(self.day):
            if done >= RETENTION_PER_SESSION:
                break
            (yield from self.g_retention_check(s, rnd))
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
            a = self.entry('gate', x)['act']
            return len(a['plan']) - a['pos'] if a['stage'] == 'main' else 2 - a['pos']
        return len(gate_plan(self.types[x]))

    def g_search(self):
        while self.searches < SEARCH_CAP:
            x = self.carried('gate') or self.next_gate()    # بوابة قطعها السقف تُستأنف أول الجلسة التالية
            if x is None:
                return
            self.begin('search')
            self.searches += 1
            yield from self.g_search_body(x)

    def g_search_body(self, x):
        st = self.stage
        try:
            while x is not None and st['done'] < GATES_PER_SEARCH[self.group]:
                if st['gate'] != x:                         # بوابة جديدة: تُحسب من الميزانية مرة واحدة
                    size = self.gate_size(x)
                    if st['done'] and size > st['budget']:
                        break
                    st['budget'] -= size
                    st['gate'] = x
                (yield from self.g_gate(x))
                st['gate'] = None
                st['done'] += 1
                x = self.next_gate()
        except Capped:
            pass
        self.end()

    def g_working_point(self):
        st, helped, gated = self.view()
        sg = self.stage if self.stage is not None else dict(w=None, shorts=0)
        w = self.candidate(st, helped)
        if w is None:
            w = next((x for x in self.ids if st[x] is None), None)
        if sg['w'] is not None:                             # جلسة تُكمَل: نقطة العمل التي بلغها البحث قبل الإغلاق
            w = sg['w']
        if w is None:
            return None
        verified = {x['skill'] for x in self.e.valid_evidence(kind='short_ok')}
        while True:
            moved = False
            for p in sorted(self.pre[w], key=self.idx.get):
                if st[p] in DONE or p in verified or p not in self.inscope:
                    continue
                if sg['shorts'] == SHORT_START:
                    return w
                sg['w'] = w
                res = (yield from self.g_short(p))
                sg['shorts'] += 1
                if res is True:
                    verified.add(p)
                elif res is False:
                    w, moved = p, True
                    sg['w'] = w
                    break
            if not moved:
                return w

    def g_start_session(self):
        self.begin('start')
        self.start_at = self.sessions
        yield from self.g_start_body()

    def g_start_body(self):
        sg = self.stage
        w, what = None, 'none'
        try:
            if sg['lesson'] is not None:                    # جلسة تُكمَل: درسها فُتح قبل الإغلاق
                w = sg['lesson']
                yield from self.g_resume_mine()
                what = sg['what'] or 'none'
            else:
                w = (yield from self.g_working_point())
                self.items_before = sum(self.n[c] for c in DIAG)
            if w is not None and sg['lesson'] is None:
                if self.e.eligible(w, 'start')['ok']:
                    sg['lesson'] = w
                    what = (yield from self.g_open_lesson(w)) or 'none'
                else:
                    what = 'use'
                    st, helped, gated = self.view()
                    if st[w] in (None, 'deferred') and gated[w] == 0:
                        target = self.pending if self.compat else self.intent
                        if w not in target:
                            target.insert(0, w)
        except Capped:
            what = 'capped'                                 # السقف قطع جلسة البدء: ما لم يكتمل في saved
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

    def g_follow(self):
        """جلسة متابعة في وضع التشخيص: بوابة، ثم تحققان قصيران، ثم الحصة التعليمية إن لم تُستهلك."""
        g = self.carried('gate') or self.pick_gate()
        if g is None and not self.saved and self.pick_short() is None and self.pick_lesson() is None:
            return False
        self.begin('follow')
        shown = sum(self.n.values())
        taught = capped = False
        try:
            if g is not None:
                was_open = g in self.e.s['opened']
                r = (yield from self.g_gate(g))
                if was_open and r in ('fail', 'help'):
                    taught = True                           # المحرك أمضى الدرس كاملًا واستهلك الحصة
                    self.log.append((self.sessions, 'lesson', g))
                    if self.learning:
                        (yield from self.g_lesson_body(g))
            for _ in range(SHORT_FOLLOW):
                x = self.carried('short') or self.pick_short()
                if x is None:
                    break
                if (yield from self.g_short(x)) is False and self.compat:
                    self.pending.append(x)
            if not taught:
                if self.learning:
                    taught = (yield from self.g_teach())
                elif self.carried('opening'):               # افتتاح قطعه السقف: يُستأنف درسه ثم يُكمل
                    o = self.carried('opening')
                    if self.still_ok(dict(type='resume_lesson', skill=o), 'opening'):
                        self.send(dict(type='resume_lesson', skill=o))
                        (yield from self.g_opening(o))
                else:
                    o = self.pick_lesson()
                    if o is not None:
                        (yield from self.g_open_lesson(o))
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
    def g_teach(self):
        """الحصة التعليمية في وضع التعلّم: درس جارٍ، ثم فحص مستحق أو جلسة تدريب قبله، ثم درس جديد."""
        for c in [c for c in self.saved if c['kind'] in TEACH_KINDS]:
            # نشاط قطعه السقف: يُستأنف أولًا. الفحص بحدث check_resumed، وأنشطة الدرس بعد resume_lesson
            r = (yield from self.g_resume(c))
            if r is not None:
                return r
        teaching = any(c['kind'] in TEACH_KINDS for c in self.saved)
        for s in list(self.parked) if not teaching else ():   # نشاط رُكن: يُستأنف أول جلسة يُقبل فيها
            c = self.parked[s]
            need = self.resume_need(c)
            v = self.resume_verdict(c, need)
            if v['ok'] or refusal_kind(v['code']) != 'later':
                c = self.parked.pop(s)
                self.save(c)
                if v['ok']:
                    self.log.append((self.sessions, 'carry_resumed', s))
                r = (yield from self.g_resume(c))
                if r is not None:
                    return r
        st = self.e.derive()
        for s in self.ids:
            o = self.e.s['opened'].get(s)
            if not o or s in self.parked or s in self.e.s['suspended'] or st[s] in DONE or o['phase'] == 'skipped':
                continue
            if o['phase'] == 'due' or not self.e.progress(s)[1]:
                if o['active'] != self.cur and not self.send(dict(type='resume_lesson', skill=s))['ok']:
                    continue
                if self.e.s['opened'][s]['phase'] == 'opening':
                    (yield from self.g_opening(s))
                else:
                    (yield from self.g_lesson_body(s))
                return True
        for s in self.ids:
            o = self.e.s['opened'].get(s)
            if not o or s in self.parked or s in self.e.s['suspended'] or st[s] in DONE or not self.e.progress(s)[1]:
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
                (yield from self.g_check(s))
                return True
            if v['code'] == 'check_needs_practice' and self.send(dict(type='resume_lesson', skill=s))['ok']:
                if self.stage is not None:
                    self.stage['after'] = ['practice', s]
                (yield from self.g_show(s, 'practice'))
                self.log.append((self.sessions, 'practice', s))
                if self.stage is not None:
                    self.stage['after'] = None
                return True
        o = self.pick_lesson()
        if o is not None:
            (yield from self.g_open_lesson(o))
            return True
        return False

    def g_resume(self, c):
        """استئناف النشاط التعليمي المحفوظ في saved. True إن استؤنف، و False إن بقي محفوظًا ولا تعليم في الجلسة،
        و None إن أُسقط أو رُكن فتمضي الحصة إلى غيره."""
        s, need = c['skill'], self.resume_need(c)
        v = self.resume_verdict(c, need)
        if not v['ok']:
            kind = refusal_kind(v['code'])
            if kind == 'session':
                return False                                # تبقى محفوظة لجلسة فيها الحصة، أو حتى يؤكَّد التاريخ
            if kind == 'final':
                self.drop_carry(v['code'], c)
            else:                                           # مؤقت يخص المهارة: يُركن بتقدّمه، وتمضي الجلسة
                self.unsave(c)
                self.parked[s], self.carried_items = c, []
                self.log.append((self.sessions, 'carry_parked:' + v['code'], s))
            return None
        if need:
            self.send(need)
        if c['kind'] == 'check':
            (yield from self.g_check(s))
        elif c['kind'] == 'opening':
            (yield from self.g_opening(s))
        elif c['kind'] == 'evidence':
            (yield from self.g_evidence(s))
        else:
            self.unsave(c)
            if c['activity'] == 'lesson':
                (yield from self.g_lesson_body(s, c['pos']))
            else:
                (yield from self.g_show(s, 'practice', c['pos']))
        return True

    def satisfied(self):
        st = self.e.derive()
        return all(st[s] in DONE for s in self.ids)

    # ---------------------------------------------------------------- التشغيل
    def g_run(self, max_sessions=200):
        if self.cur is not None:                            # بعد استعادة: الجلسة الجارية تُكمَل أولًا
            yield from self.g_continue()
        if self.start_at is None:
            (yield from self.g_search())
            (yield from self.g_start_session())
        if self.learning:
            while self.sessions < max_sessions and not (self.satisfied() and not self.saved and not self.parked and not (
                    self.retention and self.e.retention_pending())):
                (yield from self.g_follow_learning())
        else:
            while (yield from self.g_follow()):
                pass
        return self.start_w, self.start_what

    def g_follow_learning(self):
        """جلسة متابعة في وضع التعلّم. تُعقد ولو لم يكن فيها غير «استرجع»، فالأيام تمضي."""
        self.begin('follow')
        yield from self.g_follow_body()

    def g_follow_body(self):
        """أجزاء جلسة المتابعة بترتيبها. موضعها في stage، فتُكمَل من حيث توقفت بعد إغلاق التطبيق."""
        st = self.stage
        try:
            if not st['recall']:
                (yield from self.g_recall())
                st['recall'] = True
            if not st['gate_done']:
                g = self.carried('gate') or self.pick_gate()
                if g is not None:
                    was_open = g in self.e.s['opened']
                    r = (yield from self.g_gate(g))
                    st['gate_done'] = True
                    if was_open and r in ('fail', 'help'):
                        st['teach'] = True
                        self.log.append((self.sessions, 'lesson', g))
                        if self.e.s['opened'][g]['phase'] == 'full':
                            st['lesson'] = g
                            (yield from self.g_lesson_body(g))
                            st['lesson'] = None
                st['gate_done'] = True
            elif st['lesson'] is not None:                  # درس البوابة انقطع بإغلاق التطبيق: يُكمَل قبل ما بعده
                yield from self.g_resume_mine()
                st['lesson'] = None
            while not st['shorts_done'] and st['shorts'] < SHORT_FOLLOW:
                x = self.carried('short') or self.pick_short()
                if x is None:
                    break
                (yield from self.g_short(x))
                st['shorts'] += 1
            st['shorts_done'] = True
            if not st['teach']:
                st['teach'] = True
                (yield from self.g_teach())
            else:
                yield from self.g_resume_mine()             # الحصة بدأت قبل الإغلاق: يُكمَل نشاطها إن بقي منه شيء
        except Capped:
            pass
        self.end()

    def mine(self, c):
        """هل هذا النشاط المحفوظ من الحصة التعليمية للجلسة الجارية نفسها؟"""
        if c['kind'] not in TEACH_KINDS:
            return False
        if c['kind'] == 'check':
            ch = self.e.s['checks'].get(c['act']['check_id'])
            return bool(ch) and self.cur in ch['sessions']
        o = self.e.s['opened'].get(c['skill'])
        return bool(o) and o['active'] == self.cur

    def g_resume_mine(self):
        """يكمل النشاط التعليمي الذي قطعه إغلاق التطبيق في هذه الجلسة، إن وُجد، بلا حدث استئناف ولا حصة جديدة."""
        c = next((c for c in self.saved if self.mine(c)), None)
        if c is not None:
            yield from self.g_resume(c)
        st = self.stage
        if st is not None and st['after']:
            self.log.append((self.sessions, st['after'][0], st['after'][1]))
            st['after'] = None

    def g_continue(self):
        """تكملة الجلسة الجارية بعد استعادة: الأجزاء الباقية منها، ثم ختمها. لا تبدأ جلسة ولا تستهلك حصة."""
        if self.cur is None:
            return
        kind = self.stage['kind']
        if kind == 'search':
            yield from self.g_search_body(self.stage['gate'] or self.next_gate())
        elif kind == 'start':
            yield from self.g_start_body()
        elif self.learning:
            yield from self.g_follow_body()
        else:
            raise RuntimeError('تكملة جلسة المتابعة في وضع التشخيص وحده غير منفّذة')


# ---------------------------------------------------------------- الخطوات والأغلفة المتزامنة
# سلسلة الاستدعاء التي تعرض بنودًا مولّدات (g_*): تعطي (البند، المطلوب) وتستقبل ما كانت answer تعيده. والدوال
# بأسمائها السابقة أغلفة متزامنة تشغّل المولّد بـ self.answer، فلا يتغير شيء لمن يستدعيها. والواجهة تشغّل المولّد
# نفسه خطوة خطوة. حالة المولّد ليست مصدر الاستعادة: المتابعة بعد الإغلاق تُبنى من الحالة المحفوظة.
STEPPED = ('run_act', 'show', 'lesson_body', 'open_lesson', 'gate', 'short', 'opening', 'evidence', 'check', 'retention_check', 'recall', 'search', 'working_point', 'start_session', 'follow', 'teach', 'resume', 'run', 'follow_learning', 'resume_mine')


def _sync(name):
    g = getattr(Scheduler, 'g_' + name)

    @functools.wraps(g)
    def method(self, *args, **kw):
        return run_sync(getattr(self, 'g_' + name)(*args, **kw), lambda item, w: self.answer(item, w))
    method.__name__ = name
    method.__qualname__ = 'Scheduler.' + name
    return method


for _n in STEPPED:
    setattr(Scheduler, _n, _sync(_n))
