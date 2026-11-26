// المجدول بلغة التطبيق: نقل scheduler.py دالةً بدالة. يختار نشاط الجلسة، ويشغّله عبر طبقة البنود، ويرسل أحداثه
// إلى المحرك (6.2 و7.1 في الخريطة).
//
// لا يحمل المجدول حالة تقدّم. كل ما يقرّر به يقرؤه من المحرك، ويسأله (preflight) قبل عرض أول بند من أي نشاط.
// حالته الخاصة تخطيطية: بوابات نواها في جلسة البدء، وأنواع دليل الفهم التي ثبتت، وعدد محاولات الفحص، والنشاط
// المحفوظ الذي قطعه سقف الوقت (saved)، والنشاط المركون بعد رفض مؤقت (parked).
//
// الأنشطة المحفوظة (المراجعة 13): saved قائمة، لكل نشاط مدخل بمفتاحه (نوعه ومهارته). بدء نشاط آخر أو بلوغه السقف لا
// يستبدل نشاطًا محفوظًا: cut يضيف ولا يكتب فوق شيء، وحفظ مفتاح محفوظ من قبل خطأ صريح. وأولوية الاستئناف في جلسة
// المتابعة بترتيب أجزائها: فحص الاحتفاظ المحفوظ ثم المستحق، ثم البوابة المحفوظة، ثم التحقق القصير المحفوظ، ثم الحصة
// التعليمية: نشاطها المحفوظ، ثم المركون، ثم الجديد. كل نشاط يُستأنف من موضعه.
//
// المرجع هو scheduler.py: كل قرار هنا يطابقه في متجهات app/scheduler_vectors.json (app/test_scheduler_conformance.mjs).
import { OPEN_CHECK } from './engine.mjs';
import { DATA } from './engine_data.mjs';
import { CALC, Activity, GateRun, ShortCheckRun, OpeningRun, EvidenceRun, CheckRun, RetentionRun, DescribeRun, ReadyRun, driveSteps, runSync, gatePlan,
  foldItem, exposure, evidence, indicators, leftOut }
  from './items.mjs';

export const GATES_PER_SEARCH = { older: 2, young: 1 };
export const ITEM_BUDGET = 20;          // بنود البوابات المخططة في جلسة بحث للكبيرين
export const SHORT_FOLLOW = 2;          // تحققان قصيران على الأكثر في جلسة متابعة
export const SHORT_START = 4;           // في جلسة البدء
export const SEARCH_CAP = 4;
export const DONE = ['exempt', 'met'];
export const DIAG = ['gate', 'comp', 'try', 'short'];      // البنود التشخيصية
export const RETENTION_PER_SESSION = 1;
// التثبيت قصير (3.4: 3 إلى 5 بنود): أول 4 بنود من تدريب المهارة. السبب المقيس في المرجع
export const CONSOLIDATION_ITEMS = 4;
export const TEACH_KINDS = ['opening', 'evidence', 'show', 'check'];   // أنشطة الحصة التعليمية
export const EXTRA_KINDS = ['opening', 'evidence', 'show'];            // ما يُستأنف منها في الجلسة الإضافية: لا فحص فيها
// أسباب رفض استئناف نشاط محفوظ (المراجعة 11): النهائية وحدها تُسقطه، والخاصة بالجلسة تُبقيه في saved، وما سواها
// مؤقت يخص المهارة فيُركن بتقدّمه في parked
export const FINAL_REFUSALS = ['check_state', 'no_check', 'version_unavailable', 'already_satisfied', 'unknown_skill',
  'bad_event', 'no_consolidation', 'not_met'];
export const SESSION_REFUSALS = ['date_unconfirmed', 'no_session', 'extra_session'];

export function refusalKind(code) {
  if (FINAL_REFUSALS.includes(code)) return 'final';
  if (SESSION_REFUSALS.includes(code) || code.startsWith('quota_')) return 'session';
  return 'later';
}

// بلغت الجلسة سقف وقتها: تُختم، وما لم يكتمل محفوظ في saved
export class Capped extends Error {
  constructor() {
    super('Capped');
    this.name = 'Capped';
  }
}

// تغيّرت صلاحية النشاط الجاري أثناءه (المراجعة 16): لا يتقدم ولا تُحتسب الإجابة. حُفظ أو رُكن أو أُسقط بقاعدة سبب
// الرفض، وتُختم الجلسة كما تُختم عند السقف
export class Halted extends Capped {
  constructor(code) {
    super();
    this.name = 'Halted';
    this.code = code;
  }
}

// ما ترسله طبقة الخطوات بدل الإجابة حين تجد النشاط الجاري غير صالح. answered: هل حاول الطفل الإجابة الآن؟
// ومعه ما سُجّل في البند قبل تغيّر الصلاحية (R17-01): هل عُرض، وأحداثه الخام، وجوابه الصحيح ونوعه. الحدث الذي كشف
// التغيّر ليس منها
// هل وقع في البند ما يتجاوز رؤية السؤال: إجابة مؤكدة أو طلب دعم؟ (R18-01)
export const exposed = (raw) => raw.some((ev) => ev[0] === 'confirm' || ev[0] === 'support');

export class Void {
  constructor(answered, { shown = false, raw = [], answer = null, assess = false } = {}) {
    this.answered = answered;
    this.shown = shown;
    this.raw = raw.map((x) => [...x]);
    this.answer = answer;
    this.assess = assess;
  }
}

// أنواع البنود كما اختارتها المحاكاة القديمة، لوضع compat
export function oldTypes(types) {
  const plan = gatePlan(types);
  const und = plan.filter((t) => !CALC.includes(t));
  return { short: [...[...und, ...plan].slice(0, 2), plan[0]], try_: [plan[0], (und.length ? und : plan)[0]],
    guided: [...(und.length ? und : plan), ...(und.length ? und : plan), ...(und.length ? und : plan)].slice(0, 3) };
}

const get = (counter, k) => counter[k] || 0;
const sum = (counter) => Object.values(counter).reduce((a, b) => a + b, 0);
// أكبر عنصر بمفتاحه، والأول عند التساوي، كما في max في بايثون
const maxBy = (list, key) => list.reduce((best, x) => (key(x) > key(best) ? x : best));
const isNone = (x) => x === null || x === undefined;

export class Scheduler {
  constructor(engine, types, source, answer, {
    group = 'older', start = null, scope = null, learning = false, tolerant = true, compat = false,
    content_version = 1, records = null, no_short = [], try_from_gate = true, cap = null, item_seconds = null,
    retention = false, content = null, day_cap = null,
  } = {}) {
    this.e = engine;
    this.types = types;
    this.source = source;
    this.answer = answer;
    this.group = group;
    this.start = start;
    this.learning = learning;
    this.tolerant = tolerant;
    this.compat = compat;
    this.ids = engine.ids.filter((s) => scope === null || (scope instanceof Set ? scope.has(s) : scope.includes(s)));
    this.inscope = new Set(this.ids);
    this.pre = engine.pre;
    this.anc = engine.anc;
    this.idx = engine.idx;
    // هوية حزمة المحتوى التي تُربط بها المحاولة (ك1): {version, digest}. تُحفظ مع اللقطة، ولا يُستأنف نشاط جارٍ ببنك
    // آخر بصمت (persist.restore). وبها يصير content_version رقم الحزمة، فتحمله محاولات الفحص في المحرك
    this.content = content === null || content === undefined ? null : { version: content.version, digest: content.digest };
    this.content_version = this.content !== null ? this.content.version : content_version;
    this.records = records;
    this.no_short = new Set(no_short);  // 6.2: قرار المعلم بالتأجيل يُسقط التحقق القصير أيضًا، للمقارنة
    this.try_from_gate = try_from_gate; // 6.2 بقرار الأب (ك4)
    this.cap = cap;
    this.item_seconds = item_seconds || (() => 0);
    this.elapsed = 0;
    this.saved = [];
    this.carried_items = [];
    this.parked = {};                   // مهارة ← نشاط تعليمي محفوظ رُفض استئنافه رفضًا مؤقتًا يخص المهارة
    this.retention = retention;
    // الاستمرار بعد جلسة اليوم (قرار الأب، 19 نوفمبر): day_cap حد وقت يوم الأسرة كله بالثواني، وبلا قيمة لا جلسة
    // إضافية. used زمن جلسات اليوم المختومة، و free ما دُرّب في إضافيات اليوم. يُنشآن عند الحاجة ويُحفظان
    this.day_cap = day_cap;
    this.used = null;
    this.described = null;              // مهارات عُرض فحصها الوصفي، أو null قبل أولها
    this.free = null;
    this.intent = [];
    this.pending = [];
    this.proven = {};
    this.attempt = {};
    this.ev_round = {};                 // جولات دليل الفهم التي عُرضت بنودها لكل مهارة
    this.last_items = [];               // معرّفات بنود آخر نشاط، تُرفق بأحداثه (3.5)
    this.n = {};
    this.gates_run = 0;
    this.searches = 0;
    this.sessions = 0;
    this.day = -1;
    this.cur = null;
    this.log = [];
    this.refused = [];
    this.stalled = 0;                   // جلسة متابعة لم يجرِ فيها شيء: خطأ في السياسة
    this._next = 1;
    this.start_at = null;
    this.items_before = null;
    this.start_w = null;
    this.start_what = null;
    // موضع الجلسة الجارية بين أجزائها (المرحلة 0ج): به تُكمَل الجلسة نفسها بعد إغلاق التطبيق، فلا تُستهلك جلسة
    // ولا حصة ولا يتجدد الوقت. يُحفظ مع الحالة. و live النشاط المعروض الآن، للّقطة، ولا يُحفظ بنفسه.
    // today: يوم الأسرة يضعه التطبيق قبل بدء الجلسة. بلا قيمة يمضي يوم لكل جلسة، كما في المحاكاة
    this.stage = null;
    this.live = null;
    this.today = null;
    this.last = null;                   // آخر بند عُرض في الجلسة المفتوحة (seen)، للتتابع بين الأنشطة (R22-01)
    this.halts = [];                    // توقفات هذا التشغيل لتغيّر الصلاحية: [الجلسة، السبب، المهارة، النوع]. للبالغ
  }

  // ---------------------------------------------------------------- المحرك
  send(payload) {
    const ev = { ...payload, id: 'e' + this._next++ };
    if (['gate_result', 'short_check_result', 'open_lesson', 'resume_lesson', 'lesson_opening_result',
      'understanding_proved', 'check_started', 'independence_result', 'check_resumed', 'check_held',
      'recheck_result', 'retention_result', 'retention_help', 'retention_referred', 'consolidation_started',
      'consolidation_done', 'session_end', 'ready_result'].includes(payload.type) && !('session' in ev)) {
      ev.session = this.cur;
    }
    const r = this.e.apply(ev);
    if (!r.ok) this.refused.push([ev, r]);
    return r;
  }

  // السؤال قبل عرض أول بند. الرفض هنا يعني أن المجدول اقترح ما لا يحق، فيُسجَّل ولا يُعرض شيء
  ask(payload) {
    const v = this.e.preflight({ ...payload, id: 'ask', session: this.cur });
    if (!v.ok) this.refused.push([payload, v]);
    return v.ok;
  }

  begin(kind) {
    this.day = this.today === null ? this.day + 1 : this.today;
    this.sessions += 1;
    this.cur = 'S' + this.sessions;
    this.elapsed = 0;
    this.stage = { kind, recall: false, gate: null, gate_done: false, done: 0, budget: ITEM_BUDGET, shorts: 0,
      shorts_done: false, teach: false, lesson: null, after: null, w: null, what: null };
    this.send({ type: 'session_start', session: this.cur, kind, day: this.day });
    this.drop_ready();
  }

  end() {
    if (this.day_cap !== null) {                   // زمن اليوم: يُجمع عند ختم كل جلسة
      if (this.used === null || this.used.day !== this.day) this.used = { day: this.day, seconds: 0 };
      this.used.seconds += this.elapsed;
    }
    this.send({ type: 'session_end', session: this.cur });
    this.cur = null;
    this.stage = null;
    this.last = null;
  }

  // آخر بند عُرض في الجلسة (R22-01): مهارته ونشاطه ومعرّفه وحقيقته. counts: هل يُحتسب تعرّضًا؟ لا يُحتسب بند انقطع ولم
  // تُقبل قبل انقطاعه إجابة ولم يُقدَّم فيه دعم (R22-02): وصف السجل بأنه منقطع لا يكفي. البنود التي لا تحمل حقيقة
  // (مصادر المحاكاة المجردة) لا تُسجَّل، فلا تتغير الحالة المحفوظة في غير المحتوى الفعلي
  seen(skill, activity, item, got = undefined) {
    const isItem = item !== null && typeof item === 'object' && !Array.isArray(item);
    if (!isItem || item.fact === undefined || item.fact === null) {
      this.last = null;
      return;
    }
    let counts = true;
    if (typeof got === 'string') counts = got !== 'interrupted';
    else if (Array.isArray(got)) {
      const raw = got[0];
      counts = exposed(raw) || !(raw.length && raw[raw.length - 1][0] === 'interrupt');
    }
    this.last = { session: this.cur, skill, activity, item: item.id ?? null, fact: [...item.fact], counts };
  }

  view() {
    const e = this.e;
    const st = e.derive();
    const helped = new Set(e.s.attempts.filter((a) => a.result === 'help' && (a.what === 'gate' || a.what === 'lesson'))
      .map((a) => a.skill));
    const gated = {};
    for (const a of e.s.attempts) {
      if (a.what === 'gate' && a.result !== 'interrupted' && !e.s.sessions[a.session].invalid) {
        gated[a.skill] = get(gated, a.skill) + 1;
      }
    }
    return [st, helped, gated];
  }

  candidate(st, helped) {
    for (const s of this.ids) {
      if (st[s] === 'stumbled' || (helped.has(s) && (isNone(st[s]) || st[s] === 'deferred'))) return s;
    }
    return null;
  }

  blocked(s, st) {
    return this.pre[s].some((p) => st[p] === 'stumbled' || st[p] === 'waiting');
  }

  // 6.1: البوابة الثانية، وكل بوابة بعد فتح الدرس، بعد اختصار الدرس وفي جلسة لاحقة
  regate_ready(s, st, gated) {
    const o = this.e.s.opened[s];
    if (get(gated, s) === 0 && !o) return true;
    if (get(gated, s) >= 2 || !o || o.phase !== 'skipped') return false;
    return st[s] !== 'stumbled' || this.e.s.regate;
  }

  // ---------------------------------------------------------------- الأنشطة
  // ثواني جلسات هذا اليوم المختومة
  spent(day) {
    return this.used && this.used.day === day ? this.used.seconds : 0;
  }

  over() {
    if (this.stage !== null && this.stage.kind === 'extra') {   // الإضافية يحدّها وقت اليوم كله لا سقف الجلسة
      return this.spent(this.day) + this.elapsed >= this.day_cap;
    }
    return this.cap !== null && this.elapsed >= this.cap;
  }

  tick(w) {
    this.elapsed += this.item_seconds(w);
    return this.over();
  }

  // النشاط المحفوظ من هذا النوع، ولهذه المهارة إن ذُكرت، أو null
  entry(kind, skill = null) {
    return this.saved.find((c) => c.kind === kind && (skill === null || skill === c.skill)) ?? null;
  }

  // المهارة التي حُفظ لها نشاط من هذا النوع لم يكتمل، أو null
  carried(kind, skill = null) {
    const c = this.entry(kind, skill);
    return c ? c.skill : null;
  }

  // حفظ نشاط لم يكتمل. لا يُستبدل به نشاط محفوظ: المفتاح نوعه ومهارته، ولا يُحفظ مرتين
  save(c) {
    if (this.entry(c.kind, c.skill) !== null) throw new Error(`نشاط محفوظ بالمفتاح نفسه: ${c.kind} ${c.skill}`);
    this.saved.push(c);
  }

  unsave(c) {
    this.saved = this.saved.filter((x) => x !== c);
  }

  // النشاط المحفوظ لهذه المهارة إن كان، ليُستأنف من حيث توقف
  take(kind, skill) {
    const c = this.entry(kind, skill);
    if (c === null) return null;
    this.unsave(c);
    this.carried_items = c.items;
    return Activity.fromDict(c.act);
  }

  drop_carry(why, c) {
    this.log.push([this.sessions, 'carry_dropped:' + why, c.skill]);
    this.unsave(c);
    this.carried_items = [];
  }

  // حدث استئناف نشاط تعليمي محفوظ: check_resumed للفحص، و resume_lesson لأنشطة الدرس إن لم يكن نشطًا
  // سبب رفض المحرك لاستمرار هذا النشاط في الجلسة الجارية، أو null إن كان صالحًا
  invalid(kind, skill, check_id = null) {
    const v = this.e.may_continue(kind, this.cur, skill, check_id);
    return v.ok ? null : v.code;
  }

  // سبب عدم صلاحية النشاط المعروض الآن، أو null. تسأله طبقة الخطوات قبل العرض وقبل قبول أي حدث
  live_invalid() {
    const v = this.live;
    if (v === null) return null;
    if (v.kind === 'show') return this.invalid(v.consolidate ? 'consolidate' : 'show', v.skill);
    return this.invalid(v.kind, v.act.skill, v.act.check_id ?? null);
  }

  // النشاط الجاري لم يعد صالحًا: لا يتقدم. مصيره بقاعدة سبب الرفض كما عند استئناف نشاط محفوظ: الرفض الخاص بالجلسة
  // يُبقيه محفوظًا، والمؤقت الخاص بالمهارة يركن النشاط التعليمي بتقدّمه، وما عداهما يُسقطه. ما أُنجز منه باقٍ في
  // السجلات. وإجابة جاءت بعد تغيّر الصلاحية لا تُحتسب دليلًا ولا خطأً
  // void و about: البند المعروض عند التوقف وما سُجّل فيه قبل تغيّر الصلاحية (R17-01). تاريخه يُحفظ في سجلات البنود مع
  // سبب استبعاده (void)، ولا يُعطى للنشاط ولا يدخل عدّادًا ولا مؤشرًا: الحفظ غير الاستعمال في التقييم
  // رابطة سجل البند (ك2، وهو P0-04): معرّفه في سجل الطفل، والجلسة التي وقع فيها، وإصدار حزمة المحتوى. بها تُستبعد
  // سجلات جلسة أُبطلت لاحقًا من المؤشرات، والتاريخ باقٍ. الطفل هوية السجل كله (snapshot)
  stamp() {
    return { id: `i${this.records.length}`, session: this.cur, pack: this.content === null ? null : this.content.version };
  }

  _invalid() {
    return Object.entries(this.e.s.sessions).filter(([, x]) => x.invalid).map(([s]) => s);
  }

  // مؤشرات البنود بلا سجلات الجلسات المبطلة في المحرك
  indicators() { return indicators(this.records ?? [], this._invalid()); }

  left_out() { return leftOut(this.records ?? [], this._invalid()); }

  halt(code, entry, started, answered, void_ = null, about = null) {
    if (void_ !== null && void_.shown && about !== null && this.records !== null) {
      const rec = foldItem([...void_.raw, ['interrupt']], void_.answer, void_.assess);
      this.records.push({ ...rec, skill: entry.skill, activity: about.activity, role: about.role, item: about.item,
        void: code, ...this.stamp(), ...evidence(void_.raw, void_.answer, about.v ?? null) });
    }
    this.live = null;
    this.carried_items = [];
    const k = refusalKind(code), skill = entry.skill;
    let what = 'carry_dropped';
    if (k === 'session' && started && entry.kind !== 'describe') {
      this.save(entry);
      what = 'carry_kept';
    } else if (k === 'later' && TEACH_KINDS.includes(entry.kind) && started) {
      this.parked[skill] = entry;
      what = 'carry_parked';
    }
    this.log.push([this.sessions, what + ':' + code, skill]);
    if (answered) this.log.push([this.sessions, 'answer_void:' + code, skill]);
    this.halts.push([this.cur, code, skill, entry.kind]);
    throw new Halted(code);
  }

  // حكم المحرك على استئناف نشاط تعليمي محفوظ. بحدث استئناف: قبول الحدث. وبلا حدث، لأن النشاط من هذه الجلسة نفسها
  // فلا حصة جديدة: صلاحية استمراره الآن. سبق الإذن ليس إذنًا دائمًا (R16-01)
  resume_verdict(c, need) {
    if (need) return this.e.preflight({ ...need, id: 'ask', session: this.cur });
    return this.e.may_continue(c.consolidate ? 'consolidate' : c.kind, this.cur, c.skill,
      c.kind === 'check' ? c.act.check_id : null);
  }

  resume_need(c) {
    const s = c.skill;
    if (c.kind === 'check') {
      const ch = this.e.s.checks[c.act.check_id];
      if (ch && ch.sessions.includes(this.cur)) return null;   // المحاولة بدأت أو استؤنفت في هذه الجلسة نفسها
      return { type: 'check_resumed', skill: s, check_id: c.act.check_id };
    }
    if (c.consolidate) {                        // تثبيت بعد طلب مساعدة في فحص احتفاظ (ت3)
      return this.e.consolidating(s) === this.cur ? null : { type: 'consolidation_started', skill: s };
    }
    return this.e.s.opened[s].active === this.cur ? null : { type: 'resume_lesson', skill: s };
  }

  // السقف: يُحفظ النشاط الذي بدأ. الذي لم يُعرض منه بند لا يُحفظ، إلا الفحص لأن محاولته بدأت في المحرك
  cut(act, kind, items) {
    if ((sum(act.shown) || kind === 'check') && kind !== 'describe') {   // الوصفي لا يُستأنف: ما أُجيب منه مسجَّل
      this.save({ kind, skill: act.skill, act: act.toDict(), items });
    }
    this.carried_items = [];
    this.log.push([this.sessions, 'capped', act.skill]);
    throw new Capped();
  }

  *g_run_act(act, kind = null) {
    const recs = [];
    let seen = { ...act.shown }, done = 0;
    const prior = this.carried_items;
    this.carried_items = [];
    if (this.over()) this.cut(act, kind, prior);   // الجلسة بلغت سقفها: لا يُعرض بند جديد
    this.live = { kind, act, prior, recs };
    // كل بند خُتم يدخل عدّاداته وسجلّه مرة واحدة، في الانتقال نفسه الذي يتقدم فيه النشاط (R16-03). فاللقطة عند أي
    // طلب بند تحمل عدّادات وسجلات متوافقة مع تقدّم النشاط، والاستعادة لا تُسقط احتسابًا ولا تكرره
    const settle = () => {
      for (const [k, v] of Object.entries(act.shown)) {
        const d = v - get(seen, k);
        if (d > 0) this.n[k] = get(this.n, k) + d;
      }
      seen = { ...act.shown };
      if (this.records !== null) {
        for (const r of recs.slice(done)) {       // رابطة السجل بجلسته وحزمته، عند دخوله سجل الطفل (ك2)
          Object.assign(r, this.stamp());
          this.records.push(r);
        }
      }
      done = recs.length;
    };
    // تاريخ التعرّض من السجلات، لا من كائن النشاط: يبقى بعد إسقاط النشاط وإنشاء غيره (R19-01). لدليل الفهم وافتتاح الدرس
    const history = kind === 'evidence' || kind === 'opening' ? (a) => exposure(this.records, a.skill, a.name) : null;
    // آخر بند عُرض للمهارة نفسها في الجلسة نفسها من نشاط آخر، إن كان يُحتسب تعرّضًا (R22-01)
    const prev = () => {
      const x = this.last;
      return x && x.session === this.cur && x.skill === act.skill && x.activity !== act.name && x.counts
        ? [x.item, x.fact] : null;
    };
    const gen = driveSteps(act, this.source, recs, this.cap !== null ? (w) => this.tick(w) : null, history, prev);
    // الصلاحية تُفحص قبل عرض البند، ومرة أخرى قبل تطبيق الإجابة (R16-01). قرار يقع بينهما يوقف النشاط
    const guard = (req, got = undefined) => {
      const code = this.invalid(kind, act.skill, act.check_id ?? null);
      if (code === null) {
        if (got instanceof Void) throw new Error('طبقة الخطوات أبطلت بندًا والمحرك يراه صالحًا');
        return;
      }
      const [item, w] = req;
      const isObj = item !== null && typeof item === 'object' && !Array.isArray(item);
      // التعرّض للبند باقٍ وإن استُبعد من التقييم (R18-01)
      if (got instanceof Void && got.shown) act.voided(isObj ? (item.id ?? null) : null, exposed(got.raw));
      const entry = { kind, skill: act.skill, act: act.toDict(),
        items: [...prior, ...recs.filter((r) => r.item).map((r) => r.item)] };
      this.halt(code, entry, sum(act.shown) > 0 || kind === 'check',
        got !== undefined && !(got instanceof Void && !got.answered), got instanceof Void ? got : null,
        { activity: act.name, role: w.role, item: isObj ? (item.id ?? null) : null, v: isObj ? (item.v ?? null) : null });
    };
    for (let r = gen.next(); !r.done;) {
      guard(r.value);
      const got = yield r.value;
      guard(r.value, got);
      this.seen(act.skill, act.name, r.value[0], got);
      r = gen.next(got);
      settle();
    }
    settle();
    this.live = null;
    const items = [...prior, ...recs.filter((r) => r.item).map((r) => r.item)];
    if (!act.done) this.cut(act, kind, items);
    this.last_items = items;
    return act;
  }

  // أحداث النشاط إلى المحرك، ومعها بنوده إن عُرفت
  emit(act) {
    for (const p of act.events()) this.send(this.last_items.length ? { ...p, items: this.last_items } : p);
  }

  // قبل استئناف نشاط محفوظ: إن لم يعد يحق، يُترك ولا يُعدّ اقتراحًا مرفوضًا. رفض الجلسة لا يُسقطه
  still_ok(payload, kind) {
    const v = this.e.preflight({ ...payload, id: 'ask', session: this.cur });
    if (!v.ok && refusalKind(v.code) !== 'session') this.drop_carry(v.code, this.entry(kind, payload.skill));
    return v.ok;
  }

  *g_gate(s) {
    if (this.carried('gate', s)) {
      if (!this.still_ok({ type: 'gate_result', skill: s, result: 'pass' }, 'gate')) return null;
    } else if (!this.ask({ type: 'gate_result', skill: s, result: 'pass' })) {
      return null;
    }
    const act = this.take('gate', s) || new GateRun({ skill: s, types: this.types[s], tolerant: this.tolerant,
      attempt: this.e.validGates(s) + 1 });
    (yield* this.g_run_act(act, 'gate'));
    this.gates_run += 1;
    this.emit(act);
    return act.result;
  }

  *g_short(s) {
    if (this.carried('short', s)) {
      if (!this.still_ok({ type: 'short_check_result', skill: s, ok: true }, 'short')) return null;
    } else if (!this.ask({ type: 'short_check_result', skill: s, ok: true })) {
      return null;
    }
    let act = this.take('short', s);
    if (act === null) {
      act = new ShortCheckRun({ skill: s, types: this.types[s], stop_early: !this.compat });
      if (this.compat) act.types = oldTypes(this.types[s]).short;
    }
    (yield* this.g_run_act(act, 'short'));
    this.emit(act);
    return act.result;
  }

  last_gate_errors(s) {
    const log = this.e.s.log;
    for (let i = log.length - 1; i >= 0; i--) {
      const x = log[i];
      if (x.type === 'gate_result' && x.skill === s && x.result === 'fail') {
        if (!this.compat && this.e.s.sessions[x.session].invalid) continue;   // بوابة جلسة أُبطلت لا يُبنى عليها
        return x.errors && x.errors.length ? x.errors : null;
      }
    }
    return null;
  }

  // نتيجة افتتاح الدرس. الدرس يجب أن يكون نشطًا في الجلسة (فُتح أو استؤنف فيها)
  *g_opening(s) {
    let act = this.take('opening', s);
    if (act !== null) {
      // نشاط محفوظ يُستأنف
    } else if (this.compat) {
      const o = oldTypes(this.types[s]);
      const errs = this.last_gate_errors(s);
      act = new OpeningRun({ skill: s, types: this.types[s], try_types: errs ? [errs[0], errs[errs.length - 1]] : o.try_,
        try_errors_count: true });
      act.guided = o.guided;
    } else {
      const errs = this.try_from_gate ? this.last_gate_errors(s) : null;
      act = new OpeningRun({ skill: s, types: this.types[s], try_types: errs ? [errs[0], errs[errs.length - 1]] : null,
        typed: true });
    }
    (yield* this.g_run_act(act, 'opening'));
    this.emit(act);
    const kind = act.result === 'skip' ? 'skip' : 'lesson';
    this.log.push([this.sessions, kind, s]);
    if (this.stage !== null) this.stage.what = kind;
    if (kind === 'skip' && this.compat && (this.e.s.regate || this.e.direct(s) !== 'stumbled')) this.pending.push(s);
    if (kind === 'lesson' && this.learning) (yield* this.g_lesson_body(s));
    return kind;
  }

  // وضع دالة الأهلية في الجلسة الجارية: استثناء جلسة البدء فيها وحدها
  mode() {
    return this.cur !== null && this.e.s.sessions[this.cur].kind === 'start' ? 'start' : 'follow';
  }

  // المتطلب الخارجي (5.1): إن كان وحده ما يمنع فتح درس s وبوابة جاهزيته ممكنة الآن، فرمزه. وإلا null. بلا جلسة جارية
  // يكفي ألا يكون أخفق فيها مرتين
  ready_owed(s, mode = null, st = null) {
    const v = this.e.eligible(s, mode || this.mode(), st);
    if (v.ok || v.code !== 'external') return null;
    const x = v.missing;
    if (this.cur === null) {
      return this.e.readyAttempts(x).filter((a) => a.result === 'fail').length < DATA.ready.fails ? x : null;
    }
    const r = this.e.preflight({ type: 'ready_result', id: 'ask', session: this.cur, skill: s, ext: x, result: 'pass' });
    return r.ok ? x : null;
  }

  // دالة الأهلية تجيز الفتح، أو يجيزه اجتياز بوابة الجاهزية التي تُجرى قبله
  openable(s, mode = 'follow', st = null) {
    return this.e.eligible(s, mode, st).ok || this.ready_owed(s, mode, st) !== null;
  }

  // بوابة الجاهزية لمتطلب خارجي قبل فتح الدرس (قرار الأب، 26 نوفمبر). نتيجتها، أو null بلا بنود
  *g_ready(s) {
    const x = this.ready_owed(s);
    const act = this.take('ready', s) || new ReadyRun({ skill: s, ext: x });   // بوابة قطعها السقف تُكمَل من حيث توقفت
    (yield* this.g_run_act(act, 'ready'));
    this.emit(act);
    this.log.push([this.sessions, 'ready_' + (act.result ?? 'none'), s]);
    return act.result;
  }

  // بوابة جاهزية محفوظة لم تعد لازمة (تحقق المتطلب بقرار المعلم، أو لم يعد الدرس يُفتح): تُسقط
  drop_ready() {
    for (const c of this.saved.filter((x) => x.kind === 'ready')) {
      if (this.ready_owed(c.skill) === null) this.drop_carry('ready_not_owed', c);
    }
  }

  *g_open_lesson(s) {
    this.drop_ready();
    if (this.ready_owed(s) !== null && (yield* this.g_ready(s)) !== 'pass') return null;   // الدرس مغلق
    if (!this.send({ type: 'open_lesson', skill: s }).ok) return null;
    return (yield* this.g_opening(s));
  }

  // بنود الدرس أو التدريب: تُعرض ولا تصنع حدثًا للمحرك.
  // consolidate: العرض تثبيت بعد طلب مساعدة في فحص احتفاظ (ت3)، فصلاحيته صلاحية التثبيت الجاري في المحرك لا الدرس
  // النشط. الحقل لا يدخل النشاط المحفوظ ولا المعروض إلا حينها. shown: تُجمع فيها معرّفات ما عُرض
  *g_show(s, activity, k = 0, consolidate = false, shown = null) {
    const mark = consolidate ? { consolidate: true } : {};
    // التدريب الحر في الجلسة الإضافية يمتد إلى بنود التدريب الإضافي (more). غيره: بنود التدريب الستة وحدها
    const free = activity === 'practice' && this.stage !== null && this.stage.free === s ? { more: true } : {};
    const kind = consolidate ? 'consolidate' : 'show';
    for (;;) {
      if (this.over()) {                         // السقف: يُستأنف العرض من موضعه في جلسة لاحقة
        // تثبيت عُرضت بنوده كلها يكتمل الآن: لو حُفظ لأخذ حصة جلسة لاحقة ولا بند فيه، وأخّر الجولة يومًا
        if (consolidate && (k >= CONSOLIDATION_ITEMS || isNone(this.source(s, { activity, pos: k, peek: true })))) return k;
        this.save({ kind: 'show', skill: s, activity, pos: k, items: [], ...mark });
        this.log.push([this.sessions, 'capped', s]);
        throw new Capped();
      }
      const w = { activity, pos: k, role: activity };
      if (consolidate && k >= CONSOLIDATION_ITEMS) return k;
      const item = this.source(s, { activity, pos: k, ...free });
      if (isNone(item)) return k;
      this.live = { kind: 'show', skill: s, activity, pos: k, ...mark };
      const entry = { kind: 'show', skill: s, activity, pos: k, items: [], ...mark };
      let code = this.invalid(kind, s);          // قبل العرض (R16-01)
      if (code !== null) this.halt(code, entry, true, false);
      const got = yield [item, w];        // الإجابة تأتي من الغلاف المتزامن أو من الواجهة
      code = this.invalid(kind, s);              // وقبل احتساب البند معروضًا
      if (code !== null) this.halt(code, entry, true, !(got instanceof Void && !got.answered));
      this.live = null;
      this.n[activity] = get(this.n, activity) + 1;
      this.elapsed += this.item_seconds(w);
      this.seen(s, activity, item);
      if (shown !== null && item !== null && typeof item === 'object' && !Array.isArray(item) && item.id) shown.push(item.id);
      k += 1;
    }
  }

  // التثبيت بعد طلب مساعدة في فحص احتفاظ (ت3، بقرار الأب: نشاط يقرّه المحرك): تدريب المهارة، وهي مستوفاة. يُستدعى
  // بعد قبول consolidation_started في هذه الجلسة. اكتماله حدث consolidation_done، وبعده تعود الجولة مستحقة من اليوم
  // التالي. بنود ما عُرض قبل انقطاع لا تُرفق بحدث الاكتمال: هي في سجل العرض لا في المحرك
  *g_consolidate(s, k = 0) {
    const shown = [];
    (yield* this.g_show(s, 'practice', k, true, shown));
    this.send(shown.length ? { type: 'consolidation_done', skill: s, items: shown }
      : { type: 'consolidation_done', skill: s });
    this.log.push([this.sessions, 'consolidated', s]);
  }

  *g_lesson_body(s, k = 0) {
    (yield* this.g_show(s, 'lesson', k));
    (yield* this.g_evidence(s));
  }

  *g_evidence(s) {
    if (!this.ask({ type: 'understanding_proved', skill: s })) return null;
    const act = this.take('evidence', s) || new EvidenceRun({ skill: s, types: this.types[s],
      proven: this.proven[s] || [], round: get(this.ev_round, s) + 1 });
    (yield* this.g_run_act(act, 'evidence'));
    // الجولة التالية ببنود جديدة. ومنها جولة نفد بديل أول بنودها
    if (get(act.shown, 'evidence') || act.result === 'no_alternate') this.ev_round[s] = act.round;
    this.proven[s] = [...act.proven];
    this.emit(act);
    if (act.result !== 'proven') this.log.push([this.sessions, 'evidence_' + act.result, s]);
    return act.result;
  }

  *g_check(s) {
    let act = this.take('check', s);            // محاولة قطعها السقف: استؤنفت بحدث check_resumed
    if (act === null) {
      const k = get(this.attempt, s);
      act = new CheckRun({ skill: s, check_id: `${s}/check/${k + 1}`, content_version: this.content_version,
        attempt: String.fromCharCode(65 + k) });
      if (!this.send(act.startEvent()).ok) return null;
      this.attempt[s] = k + 1;
    }
    (yield* this.g_run_act(act, 'check'));
    this.emit(act);
    this.log.push([this.sessions, 'check_' + act.result, s]);
    return act.result;
  }

  // فحص احتفاظ مستحق (3.7): 5 بنود جولته، ونتيجته حدث retention_result
  *g_retention_check(s, rnd) {
    if (this.carried('retention', s)) {
      if (!this.still_ok({ type: 'retention_result', skill: s, correct: 0 }, 'retention')) return null;
    } else if (!this.ask({ type: 'retention_result', skill: s, correct: 0 })) {
      return null;
    }
    const act = this.take('retention', s)
      || new RetentionRun({ skill: s, round: rnd, attempt: this.e.retentionAttempt(s) });
    (yield* this.g_run_act(act, 'retention'));
    this.emit(act);
    const tag = act.result === null ? 'cut' : act.result === 'done' ? act.correct : act.result;
    this.log.push([this.sessions, 'retention_' + tag, s]);
    return act.result;
  }

  // «استرجع» في أول الجلسة: فحص احتفاظ قطعه السقف، ثم ما استحق، الأقدم استحقاقًا أولًا
  *g_recall() {
    if (!this.retention) return;
    let done = 0;
    const s = this.carried('retention');
    if (s) {
      (yield* this.g_retention_check(s, null));
      done += 1;
    }
    for (const [x, rnd] of this.e.retentionDue(this.day)) {
      if (done >= RETENTION_PER_SESSION) break;
      (yield* this.g_retention_check(x, rnd));
      done += 1;
    }
  }

  // ---------------------------------------------------------------- سياسة التشخيص (6.2)
  next_gate() {
    const [st, helped, gated] = this.view();
    const freshOk = (x) => isNone(st[x]) && get(gated, x) === 0;
    const c = this.candidate(st, helped);
    if (this.group === 'young') {
      if (c !== null) return null;
      // مع قرار البداية: البحث بالحاجة (needed_gate). بلا قرار: من أسفل النطاق (كما في المرجع)
      if (this.ids.some((x) => this.e.decisions('open', x).length)) return this.needed_gate(st, gated);
      return this.ids.find(freshOk) ?? null;
    }
    if (this.gates_run === 0 && this.inscope.has(this.start) && isNone(st[this.start])) return this.start;
    const inScope = (set) => [...set].filter((a) => this.inscope.has(a)).sort((a, b) => this.idx[a] - this.idx[b]);
    if (c !== null) {
      const v0 = this.e.eligible(c, 'follow', st);
      if (v0.ok || v0.code === 'external') return null;   // نقطة العمل محسومة، والمتطلب الخارجي وحده لا يُبحث له في الأسلاف
      const fresh = inScope(this.anc[c]).filter(freshOk);
      if (fresh.length) {
        const split = (a) => {
          const below = inScope(this.anc[a]).filter((b) => isNone(st[b])).length;
          return Math.min(below + 1, fresh.length - below);
        };
        return maxBy(fresh, split);
      }
      const need = [...this.pre[c]].sort((a, b) => this.idx[a] - this.idx[b])
        .filter((p) => !DONE.includes(st[p]) && this.inscope.has(p));
      return need.length ? need[0] : null;
    }
    if (this.ids.some((x) => this.e.decisions('open', x).length)) return this.needed_gate(st, gated);
    const fresh = this.ids.filter(freshOk);
    if (!fresh.length) return null;
    const desc = {};
    for (const x of fresh) desc[x] = this.ids.filter((d) => this.anc[d].has(x));
    const split = (x) => {
      const below = inScope(this.anc[x]).filter((b) => isNone(st[b])).length;
      const above = desc[x].filter((d) => isNone(st[d])).length;
      return Math.min(below + 1, above + 1);
    };
    return maxBy(fresh, split);
  }

  // بنود البوابة المخططة، أو ما بقي منها إن قطعها السقف (ك9)
  gate_size(x) {
    if (this.carried('gate', x)) {
      const a = this.entry('gate', x).act;
      return a.stage === 'main' ? a.plan.length - a.pos : 2 - a.pos;
    }
    return gatePlan(this.types[x]).length;
  }

  *g_search() {
    while (this.searches < SEARCH_CAP) {
      let x = this.carried('gate') || this.next_gate();   // بوابة قطعها السقف تُستأنف أول الجلسة التالية
      if (x === null) return;
      this.begin('search');
      this.searches += 1;
      yield* this.g_search_body(x);
    }
  }

  *g_search_body(x) {
    const st = this.stage;
    try {
      while (x !== null && st.done < GATES_PER_SEARCH[this.group]) {
        if (st.gate !== x) {                     // بوابة جديدة: تُحسب من الميزانية مرة واحدة
          const size = this.gate_size(x);
          if (st.done && size > st.budget) break;
          st.budget -= size;
          st.gate = x;
        }
        (yield* this.g_gate(x));
        st.gate = null;
        st.done += 1;
        x = this.next_gate();
      }
    } catch (err) {
      if (!(err instanceof Capped)) throw err;
    }
    this.end();
  }

  *g_working_point() {
    const [st, helped] = this.view();
    let w = this.candidate(st, helped);
    if (w === null) w = this.ids.find((x) => isNone(st[x])) ?? null;
    const sg = this.stage !== null ? this.stage : { w: null, shorts: 0 };
    if (sg.w !== null) w = sg.w;                 // جلسة تُكمَل: نقطة العمل التي بلغها البحث قبل الإغلاق
    if (w === null) return null;
    const verified = new Set(this.e.validEvidence(null, 'short_ok').map((x) => x.skill));
    for (;;) {
      let moved = false;
      // متطلب تجاوزه قرار المعلم لهذه المهارة لا يُتحقق منه (كما في المرجع)
      const skip = new Set(this.e.decisions('open', w).flatMap((d) => d.bypass));
      for (const p of [...this.pre[w]].sort((a, b) => this.idx[a] - this.idx[b])) {
        if (DONE.includes(st[p]) || verified.has(p) || !this.inscope.has(p) || skip.has(p)) continue;
        if (sg.shorts === SHORT_START) return w;
        sg.w = w;
        const res = (yield* this.g_short(p));
        sg.shorts += 1;
        if (res === true) {
          verified.add(p);
        } else if (res === false) {
          w = p;
          sg.w = w;
          moved = true;
          break;
        }
      }
      if (!moved) return w;
    }
  }

  *g_start_session() {
    this.begin('start');
    this.start_at = this.sessions;
    yield* this.g_start_body();
  }

  *g_start_body() {
    const sg = this.stage;
    let w = null, what = 'none';
    const diag = () => DIAG.reduce((a, c) => a + get(this.n, c), 0);
    try {
      if (sg.lesson !== null) {                  // جلسة تُكمَل: درسها فُتح قبل الإغلاق
        w = sg.lesson;
        yield* this.g_resume_mine();
        what = sg.what || 'none';
      } else {
        w = (yield* this.g_working_point());
        this.items_before = diag();
      }
      if (w !== null && sg.lesson === null) {
        if (this.openable(w, 'start')) {
          // بوابة الجاهزية قبل أن يُسجَّل الدرس درسَ الجلسة: بعد إخفاقها لا درس يُستأنف عند التكملة
          if (this.ready_owed(w) === null || (yield* this.g_ready(w)) === 'pass') {
            sg.lesson = w;
            what = (yield* this.g_open_lesson(w)) || 'none';
          }
        } else {
          what = 'use';
          const [st, , gated] = this.view();
          if ((isNone(st[w]) || st[w] === 'deferred') && get(gated, w) === 0) {
            const target = this.compat ? this.pending : this.intent;
            if (!target.includes(w)) target.unshift(w);
          }
        }
      }
    } catch (err) {
      if (!(err instanceof Capped)) throw err;
      what = 'capped';                          // السقف قطع جلسة البدء: ما لم يكتمل في saved
      if (this.items_before === null) this.items_before = diag();
    }
    if (what === 'none' || what === 'use') this.log.push([this.sessions, what, w]);
    this.start_w = w;
    this.start_what = what;
    this.end();
  }

  gate_queue() {
    if (this.compat) return [...this.pending];
    return [...this.intent, ...this.e.s.queue.filter((q) => !this.intent.includes(q))];
  }

  drop(x) {
    for (const lst of [this.pending, this.intent]) {
      const i = lst.indexOf(x);
      if (i >= 0) lst.splice(i, 1);
    }
  }

  // البحث حين يوجد قرار بداية (كما في المرجع): مهارات القرارات، ثم التالية لما أثبته الطفل، فإن نقصها متطلب لم يُفحص
  // فُحص هو (الأعمق أولًا). مهارة جانبية لا يتطلبها شيء مما يليه لا تُفحص
  needed_gate(st, gated) {
    const opened = this.e.s.opened;                        // درس مفتوح لا بوابة له هنا (كما في المرجع)
    const freshOk = (x) => isNone(st[x]) && get(gated, x) === 0 && !(x in opened);
    const chosen = this.ids.filter((x) => this.e.decisions('open', x).length);
    const first = chosen.find(freshOk);
    if (first !== undefined) return first;
    const assumed = this.assumed();
    const ok = (p) => DONE.includes(st[p]) || st[p] === 'deferred' || assumed.has(p);
    const byIdx = (xs) => [...xs].sort((a, b) => this.idx[a] - this.idx[b]);
    const need = (x, seen = []) => {
      for (const p of byIdx(this.pre[x])) {
        if (ok(p) || !this.inscope.has(p) || seen.includes(p)) continue;
        if (!freshOk(p)) return null;
        if ([...this.pre[p]].every((q) => ok(q) || !this.inscope.has(q))) return p;
        const r = need(p, [...seen, x]);
        if (r !== null) return r;
      }
      return null;
    };
    const targets = this.ids.filter((t) => freshOk(t) && !assumed.has(t) && !chosen.includes(t)
      && [...this.pre[t]].some((p) => DONE.includes(st[p])));
    for (const t of targets) if ([...this.pre[t]].every((p) => ok(p) || !this.inscope.has(p))) return t;   // التالية مباشرة أولًا
    for (const t of targets) {
      const r = need(t);
      if (r !== null) return r;
    }
    return null;
  }

  // أسلاف مهارات قرارات البداية: لا تدخل البحث الحر ولا البوابة الاحتياطية
  assumed() {
    const chosen = this.ids.filter((x) => this.e.decisions('open', x).length);
    return new Set(chosen.flatMap((x) => [...this.anc[x]]));
  }

  pick_gate() {
    const [st, helped, gated] = this.view();
    const opened = this.e.s.opened;
    for (const x of this.gate_queue()) {
      const o = opened[x];
      if ((o && (o.phase === 'full' || o.phase === 'due')) || get(gated, x) >= 2 || DONE.includes(st[x])) {
        this.drop(x);
      } else if (!this.compat && !this.regate_ready(x, st, gated)) {
        continue;       // تبقى في الطابور: تُعاد بوابتها بعد اختصار درسها
      } else if (!this.blocked(x, st)) {
        this.drop(x);
        return x;
      }
    }
    for (const s of this.ids) {
      if ((st[s] === 'stumbled' || (helped.has(s) && (isNone(st[s]) || st[s] === 'deferred'))) && !(s in opened)) {
        const v = this.e.eligible(s, 'follow', st);
        const p = v.missing;
        if (!v.ok && this.inscope.has(p) && (isNone(st[p]) || st[p] === 'deferred') && !helped.has(p)
          && !(p in opened) && get(gated, p) === 0) {
          return p;
        }
      }
    }
    if (!Object.values(opened).some((o) => o.phase === 'full' || o.phase === 'due')) {
      const g = this.next_gate();
      if (g !== null && !(g in opened) && !helped.has(g) && get(gated, g) === 0 && !this.blocked(g, st)) return g;
    }
    // البوابة الاحتياطية، ومع قرار البداية البحث بالحاجة بدلها (كما في المرجع)
    if (this.ids.some((x) => this.e.decisions('open', x).length)) {
      const g = this.needed_gate(st, gated);       // الدرس المفتوح يبقى «full» بعد إتقانه، فالبحث بالحاجة هنا (كما في المرجع)
      return g !== null && !(g in opened) && !helped.has(g) && !this.blocked(g, st) ? g : null;
    }
    for (const x of this.ids) {
      if (isNone(st[x]) && !(x in opened) && !helped.has(x)) return x;
    }
    return null;
  }

  pick_short() {
    const st = this.e.derive();
    const checked = new Set(this.e.s.checked);
    const assumed = this.assumed();                    // ما تحت قرار البداية لا يُتحقق منه (كما في المرجع)
    return this.ids.find((x) => st[x] === 'deferred' && !checked.has(x) && !this.no_short.has(x) && !assumed.has(x)) ?? null;
  }

  pick_lesson() {
    const [st, helped] = this.view();
    for (const s of this.ids) {
      if ((st[s] === 'stumbled' || (helped.has(s) && (isNone(st[s]) || st[s] === 'deferred')))
        && !(s in this.e.s.opened) && this.openable(s, 'follow', st)) {
        return s;
      }
    }
    return null;
  }

  // جلسة متابعة في وضع التشخيص: بوابة، ثم تحققان قصيران، ثم الحصة التعليمية إن لم تُستهلك
  *g_follow() {
    const g = this.carried('gate') || this.pick_gate();
    if (g === null && !this.saved.length && this.pick_short() === null && this.pick_lesson() === null) return false;
    this.begin('follow');
    const shown = sum(this.n);
    let taught = false, capped = false;
    try {
      if (g !== null) {
        const wasOpen = g in this.e.s.opened;
        const r = (yield* this.g_gate(g));
        if (wasOpen && (r === 'fail' || r === 'help')) {
          taught = true;                        // المحرك أمضى الدرس كاملًا واستهلك الحصة
          this.log.push([this.sessions, 'lesson', g]);
          if (this.learning) (yield* this.g_lesson_body(g));
        }
      }
      for (let i = 0; i < SHORT_FOLLOW; i++) {
        const x = this.carried('short') || this.pick_short();
        if (x === null) break;
        if ((yield* this.g_short(x)) === false && this.compat) this.pending.push(x);
      }
      if (!taught) {
        if (this.learning) {
          taught = (yield* this.g_teach());
        } else if (this.carried('opening')) {   // افتتاح قطعه السقف: يُستأنف درسه ثم يُكمل
          const o = this.carried('opening');
          if (this.still_ok({ type: 'resume_lesson', skill: o }, 'opening')) {
            this.send({ type: 'resume_lesson', skill: o });
            (yield* this.g_opening(o));
          }
        } else {
          const o = this.pick_lesson();
          if (o !== null) (yield* this.g_open_lesson(o));
        }
      }
    } catch (err) {
      if (!(err instanceof Capped)) throw err;
      capped = true;
    }
    this.end();
    if (sum(this.n) === shown && !taught && !capped && !this.compat) {
      this.stalled += 1;                        // لم يُعرض بند: خطأ في السياسة
      return false;
    }
    return true;
  }

  // ---------------------------------------------------------------- مسار التعلّم
  // الحصة التعليمية: درس جارٍ، ثم فحص مستحق أو جلسة تدريب قبله، ثم درس جديد
  // الفحص الوصفي للمقارنة (10.2، وموضعه بقرار الأب في 19 نوفمبر): مرة واحدة، في أول جلسة تلي اجتياز فحص الاستقلال
  // لمهارة لها بنوده، والاستقلال ما زال ساريًا. لا يُشترط لتقدم ولا حدث له في المحرك
  describe_due() {
    const out = [];
    for (const s of this.ids) {
      if ((this.described ?? []).includes(s) || !this.e.progress(s)[2]) continue;
      const passed = this.log.filter((x) => x[1] === 'check_pass' && x[2] === s).map((x) => x[0]);
      if (!passed.length || Math.min(...passed) >= this.sessions) continue;   // اجتاز في هذه الجلسة: الوصفي في التالية
      if (isNone(this.source(s, { activity: 'describe', role: 'descriptive_check', pos: 0, peek: true }))) continue;
      out.push(s);
    }
    return out;
  }

  // يُعدّ معروضًا عند بدئه: إن قطعه السقف أو أُغلق التطبيق فما أُجيب منه مسجَّل، ولا يُعاد
  *g_describe(s) {
    this.described = [...(this.described ?? []), s];
    this.log.push([this.sessions, 'describe', s]);
    const act = new DescribeRun({ skill: s });
    (yield* this.g_run_act(act, 'describe'));
    this.log.push([this.sessions, 'describe_' + act.result, s]);
  }

  *g_teach() {
    for (const c of this.saved.filter((x) => TEACH_KINDS.includes(x.kind))) {
      const r = (yield* this.g_resume(c));                 // نشاط قطعه السقف: يُستأنف أولًا
      if (r !== null) return r;
    }
    const teaching = this.saved.some((x) => TEACH_KINDS.includes(x.kind));
    for (const s of teaching ? [] : this.describe_due()) (yield* this.g_describe(s));
    for (const s of teaching ? [] : this.e.consolidationOwed()) {
      // طُلبت مساعدة في فحص احتفاظ: التثبيت يسبق غيره في الحصة، فالطفل طلب العون ولا يُؤخَّر عنه (ت3)
      if (this.entry('show', s) === null && this.send({ type: 'consolidation_started', skill: s }).ok) {
        (yield* this.g_consolidate(s));
        return true;
      }
    }
    for (const s of teaching ? [] : Object.keys(this.parked)) {   // نشاط رُكن: أول جلسة يُقبل فيها
      const c = this.parked[s];
      const need = this.resume_need(c);
      const v = this.resume_verdict(c, need);
      if (v.ok || refusalKind(v.code) !== 'later') {
        delete this.parked[s];
        this.save(c);
        if (v.ok) this.log.push([this.sessions, 'carry_resumed', s]);
        const r = (yield* this.g_resume(c));
        if (r !== null) return r;
      }
    }
    const st = this.e.derive();
    for (const s of this.ids) {
      const o = this.e.s.opened[s];
      if (!o || s in this.parked || s in this.e.s.suspended || DONE.includes(st[s]) || o.phase === 'skipped') continue;
      if (o.phase === 'due' || !this.e.progress(s)[1]) {
        if (o.active !== this.cur && !this.send({ type: 'resume_lesson', skill: s }).ok) continue;
        if (this.e.s.opened[s].phase === 'opening') (yield* this.g_opening(s));
        else (yield* this.g_lesson_body(s));
        return true;
      }
    }
    for (const s of this.ids) {
      const o = this.e.s.opened[s];
      if (!o || s in this.parked || s in this.e.s.suspended || DONE.includes(st[s]) || !this.e.progress(s)[1]) continue;
      // معلَّق للمراجعة أو يحتاج إعادة بدء: ينتظر المعلم
      if (Object.values(this.e.s.checks).some((x) => x.skill === s && OPEN_CHECK.includes(x.state))) continue;
      const k = get(this.attempt, s);
      const v = this.e.preflight({ type: 'check_started', id: 'ask', session: this.cur, skill: s,
        check_id: `${s}/check/${k + 1}`, content_version: this.content_version });
      if (v.ok) {
        (yield* this.g_check(s));
        return true;
      }
      if (v.code === 'check_needs_practice' && this.send({ type: 'resume_lesson', skill: s }).ok) {
        if (this.stage !== null) this.stage.after = ['practice', s];
        (yield* this.g_show(s, 'practice'));
        this.log.push([this.sessions, 'practice', s]);
        if (this.stage !== null) this.stage.after = null;
        return true;
      }
    }
    const o = this.pick_lesson();
    if (o !== null) {
      (yield* this.g_open_lesson(o));
      return true;
    }
    return false;
  }

  // استئناف النشاط التعليمي المحفوظ في saved. true إن استؤنف، و false إن بقي محفوظًا ولا تعليم في الجلسة،
  // و null إن أُسقط أو رُكن فتمضي الحصة إلى غيره
  *g_resume(c) {
    const s = c.skill, need = this.resume_need(c);
    const v = this.resume_verdict(c, need);
    if (!v.ok) {
      const kind = refusalKind(v.code);
      if (kind === 'session') return false;     // تبقى محفوظة لجلسة فيها الحصة، أو حتى يؤكَّد التاريخ
      if (kind === 'final') {
        this.drop_carry(v.code, c);
      } else {                                  // مؤقت يخص المهارة: يُركن بتقدّمه، وتمضي الجلسة
        this.unsave(c);
        this.parked[s] = c;
        this.carried_items = [];
        this.log.push([this.sessions, 'carry_parked:' + v.code, s]);
      }
      return null;
    }
    if (need) this.send(need);
    if (c.kind === 'check') {
      (yield* this.g_check(s));
    } else if (c.kind === 'opening') {
      (yield* this.g_opening(s));
    } else if (c.kind === 'evidence') {
      (yield* this.g_evidence(s));
    } else {
      this.unsave(c);
      if (c.consolidate) (yield* this.g_consolidate(s, c.pos));
      else if (c.activity === 'lesson') (yield* this.g_lesson_body(s, c.pos));
      else (yield* this.g_show(s, 'practice', c.pos));
    }
    return true;
  }

  satisfied() {
    const st = this.e.derive();
    return this.ids.every((s) => DONE.includes(st[s]));
  }

  // ---------------------------------------------------------------- التشغيل
  *g_run(max_sessions = 200) {
    if (this.cur !== null) yield* this.g_continue();   // بعد استعادة: الجلسة الجارية تُكمَل أولًا
    if (this.start_at === null) {
      (yield* this.g_search());
      (yield* this.g_start_session());
    }
    if (this.learning) {
      while (this.sessions < max_sessions && !(this.satisfied() && !this.saved.length
        && !Object.keys(this.parked).length && !(this.retention && this.e.retentionPending().length))) {
        (yield* this.g_follow_learning());
      }
    } else {
      while ((yield* this.g_follow())) { /* جلسة متابعة بعد أخرى */ }
    }
    return [this.start_w, this.start_what];
  }

  // هل بقيت جلسة متابعة تُعقد في وضع التعلّم؟ شرط حلقة g_run نفسه
  more(max_sessions = 200) {
    return this.sessions < max_sessions && !(this.satisfied() && !this.saved.length
      && !Object.keys(this.parked).length && !(this.retention && this.e.retentionPending().length));
  }

  // جلسة واحدة للواجهة: تُكمل الجلسة الجارية إن وُجدت، وإلا تعقد الجلسة التالية بترتيب g_run نفسه (بحث، ثم بدء، ثم
  // متابعة). تعيد false إن لم تبقَ جلسة تُعقد، ولا تغيّر شيئًا حينها. تكرارها حتى false يساوي g_run
  *g_session(max_sessions = 200) {
    if (this.cur !== null) {
      yield* this.g_continue();
      return true;
    }
    if (this.start_at === null) {
      if (this.searches < SEARCH_CAP) {
        const x = this.carried('gate') || this.next_gate();
        if (x !== null) {
          this.begin('search');
          this.searches += 1;
          yield* this.g_search_body(x);
          return true;
        }
      }
      yield* this.g_start_session();
      return true;
    }
    if (this.learning) {
      if (!this.more(max_sessions)) return false;
      yield* this.g_follow_learning();
      return true;
    }
    return (yield* this.g_follow());
  }

  // ---------------------------------------------------------------- الجلسة الإضافية (قرار الأب، 19 نوفمبر)
  // الطفل الذي يريد أن يستمر بعد جلسة يومه لا يُقطع. الإضافية تعليم وتدريب فقط: يُكمَل فيها ما قطعه السقف، والدرس
  // الجاري، وتدريب المهارة التي تنتظر فحص استقلالها، ودرس جديد إن لم يُفتح اليوم درس. لا بوابة ولا تحقق ولا فحص
  // استقلال ولا فحص احتفاظ: مواعيدها بالأيام، والمحرك يرفضها في الإضافية. ولا تُدرَّب مهارة مستوفاة: تدريبها داخل
  // فاصل الاحتفاظ يجعل جولته «أداء مؤجل» (3.7). والتثبيت المستحق بعد فحص احتفاظ يبقى في حصة الجلسة العادية، ويُكمَل
  // هنا إن قطعه السقف.

  // المهارات التي درسها جارٍ: مفتوح، لم يثبت فهمه، وليس مركونًا ولا معلَّقًا
  extra_lessons(st) {
    const out = [];
    for (const s of this.ids) {
      const o = this.e.s.opened[s];
      if (!o || s in this.parked || s in this.e.s.suspended || DONE.includes(st[s]) || o.phase === 'skipped') continue;
      if (o.phase === 'due' || !this.e.progress(s)[1]) out.push(s);
    }
    return out;
  }

  // المهارات التي تُدرَّب في الإضافية: ثبت فهمها وتنتظر فحص استقلالها، ولا محاولة فحص لها معلَّقة أو مقطوعة، ولم
  // تُدرَّب في إضافية اليوم. مرة واحدة في اليوم: بنود التدريب قليلة، وتكرارها في الجلسة نفسها لا يضيف
  extra_practice(st, day) {
    const done = this.free && this.free.day === day ? this.free.skills : [];
    const out = [];
    for (const s of this.ids) {
      const o = this.e.s.opened[s];
      if (!o || s in this.parked || s in this.e.s.suspended || DONE.includes(st[s]) || !this.e.progress(s)[1]) continue;
      if (!['opening', 'full', 'due'].includes(o.phase) || done.includes(s)) continue;
      if (Object.values(this.e.s.checks).some((c) => c.skill === s && OPEN_CHECK.includes(c.state))) continue;
      if (this.saved.some((c) => c.kind === 'check' && c.skill === s)) continue;
      out.push(s);
    }
    return out;
  }

  // ما تعرضه جلسة إضافية في هذا اليوم، بترتيبه. يُسأل والجلسة مغلقة، فشروطه بنيوية: ما يرفضه المحرك عند التنفيذ
  // يُتخطى. قائمة فارغة: لا شيء يُعرض
  extra_plan(day) {
    const st = this.e.derive();
    const plan = this.saved.filter((c) => EXTRA_KINDS.includes(c.kind)).map((c) => ['resume', c.skill]);
    const has = (kind, s) => plan.some((x) => x[0] === kind && x[1] === s);
    for (const s of this.extra_lessons(st)) if (!has('resume', s)) plan.push(['lesson', s]);
    for (const s of this.extra_practice(st, day)) plan.push(['practice', s]);
    const openedToday = Object.values(this.e.s.opened).some((o) => this.e.s.sessions[o.session].day === day);
    if (!openedToday && this.pick_lesson() !== null) plan.push(['open', this.pick_lesson()]);
    return plan;
  }

  // هل تُعرض على الطفل جلسة إضافية الآن؟ بعد جلسة مختومة في يوم الأسرة نفسه، وفي اليوم وقت باقٍ، وعندنا ما يُعرض،
  // ولم تمضِ اليوم إضافية بلا بند
  can_extra(day) {
    const e = this.e.s;
    if (this.day_cap === null || !this.learning || this.cur !== null || this.start_at === null || !e.order.length) return false;
    if (e.sessions[e.order[e.order.length - 1]].day !== day || this.spent(day) >= this.day_cap) return false;
    if (this.free && this.free.day === day && this.free.dry) return false;
    return this.extra_plan(day).length > 0;
  }

  // جلسة إضافية واحدة. تعيد false ولا تغيّر شيئًا إن لم تكن متاحة (can_extra)
  *g_extra() {
    if (!this.can_extra(this.today === null ? this.day : this.today)) return false;
    this.begin('extra');
    this.stage.seen = [];                          // ما جرى في هذه الجلسة لكل مهارة: مرة واحدة لكلٍّ
    this.stage.free = null;                        // المهارة التي يجري تدريبها الحر الآن
    this.stage.n0 = sum(this.n);                   // عدد البنود المعروضة قبلها: به تُعرف الإضافية بلا بند
    yield* this.g_extra_body();
    return true;
  }

  *g_extra_body() {
    const st = this.stage;
    try {
      yield* this.g_resume_mine();                 // نشاط قطعه إغلاق التطبيق في هذه الجلسة
      if (st.free !== null) {                      // التدريب الحر الذي قطعه الإغلاق اكتمل الآن
        this.log.push([this.sessions, 'extra_practice', st.free]);
        this.practiced(st.free);
        st.free = null;
      }
      while (yield* this.g_extra_step());
    } catch (err) {
      if (!(err instanceof Capped)) throw err;
      // حد اليوم قطع تدريبًا حرًّا: لا يُحفظ، فلا يأخذ غدًا حصة الجلسة من فحص أو درس
      if (st.free !== null) {
        for (const c of this.saved.filter((x) => x.kind === 'show' && x.skill === st.free && x.activity === 'practice')) {
          this.unsave(c);
        }
        this.practiced(st.free);
      }
    }
    if (sum(this.n) === st.n0) this.practiced(null, true);   // لم يُعرض بند: لا تُعرض إضافية أخرى اليوم
    this.end();
  }

  practiced(s, dry = false) {
    if (this.free === null || this.free.day !== this.day) this.free = { day: this.day, skills: [] };
    if (s !== null && !this.free.skills.includes(s)) this.free.skills.push(s);
    if (dry) this.free.dry = true;
  }

  // خطوة واحدة من الإضافية. true إن جرى شيء، و false إن لم يبقَ ما يُعرض
  *g_extra_step() {
    const stage = this.stage;
    for (const c of this.saved.filter((x) => EXTRA_KINDS.includes(x.kind))) {
      const r = (yield* this.g_resume(c));         // نشاط قطعه السقف: يُكمَل الآن بدل الغد
      if (r) return true;                          // null: أُسقط أو رُكن. false: يبقى محفوظًا لجلسة عادية
    }
    const st = this.e.derive();
    for (const s of this.extra_lessons(st)) {
      if (stage.seen.includes(s)) continue;
      const o = this.e.s.opened[s];
      if (o.active !== this.cur && !this.send({ type: 'resume_lesson', skill: s }).ok) continue;
      stage.seen.push(s);
      if (this.e.s.opened[s].phase === 'opening') (yield* this.g_opening(s));
      else (yield* this.g_lesson_body(s));
      return true;
    }
    for (const s of this.extra_practice(st, this.day)) {
      const o = this.e.s.opened[s];
      if (o.active !== this.cur && !this.send({ type: 'resume_lesson', skill: s }).ok) continue;
      stage.free = s;
      (yield* this.g_show(s, 'practice'));
      this.log.push([this.sessions, 'extra_practice', s]);
      this.practiced(s);
      stage.free = null;
      return true;
    }
    const o = this.pick_lesson();
    if (o !== null && !stage.seen.includes(o)) {
      stage.seen.push(o);
      if (this.ready_owed(o) !== null && (yield* this.g_ready(o)) !== 'pass') return true;   // الدرس مغلق
      if (this.send({ type: 'open_lesson', skill: o }).ok) {   // يرفضه المحرك إن فُتح اليوم درس (lesson_today)
        (yield* this.g_opening(o));
        return true;
      }
    }
    return false;
  }

  // جلسة متابعة في وضع التعلّم. تُعقد ولو لم يكن فيها غير «استرجع»، فالأيام تمضي
  *g_follow_learning() {
    this.begin('follow');
    yield* this.g_follow_body();
  }

  // أجزاء جلسة المتابعة بترتيبها. موضعها في stage، فتُكمَل من حيث توقفت بعد إغلاق التطبيق
  *g_follow_body() {
    const st = this.stage;
    try {
      if (!st.recall) {
        (yield* this.g_recall());
        st.recall = true;
      }
      if (!st.gate_done) {
        const g = this.carried('gate') || this.pick_gate();
        if (g !== null) {
          const wasOpen = g in this.e.s.opened;
          const r = (yield* this.g_gate(g));
          st.gate_done = true;
          if (wasOpen && (r === 'fail' || r === 'help')) {
            st.teach = true;
            this.log.push([this.sessions, 'lesson', g]);
            if (this.e.s.opened[g].phase === 'full') {
              st.lesson = g;
              (yield* this.g_lesson_body(g));
              st.lesson = null;
            }
          }
        }
        st.gate_done = true;
      } else if (st.lesson !== null) {           // درس البوابة انقطع بإغلاق التطبيق: يُكمَل قبل ما بعده
        yield* this.g_resume_mine();
        st.lesson = null;
      }
      while (!st.shorts_done && st.shorts < SHORT_FOLLOW) {
        const x = this.carried('short') || this.pick_short();
        if (x === null) break;
        (yield* this.g_short(x));
        st.shorts += 1;
      }
      st.shorts_done = true;
      if (!st.teach) {
        st.teach = true;
        (yield* this.g_teach());
      } else {
        yield* this.g_resume_mine();             // الحصة بدأت قبل الإغلاق: يُكمَل نشاطها إن بقي منه شيء
      }
    } catch (err) {
      if (!(err instanceof Capped)) throw err;
    }
    this.end();
  }

  // هل هذا النشاط المحفوظ من الحصة التعليمية للجلسة الجارية نفسها؟
  mine(c) {
    if (!TEACH_KINDS.includes(c.kind)) return false;
    if (c.kind === 'check') {
      const ch = this.e.s.checks[c.act.check_id];
      return Boolean(ch) && ch.sessions.includes(this.cur);
    }
    if (c.consolidate) return this.e.consolidating(c.skill) === this.cur;
    const o = this.e.s.opened[c.skill];
    return Boolean(o) && o.active === this.cur;
  }

  // يكمل النشاط التعليمي الذي قطعه إغلاق التطبيق في هذه الجلسة، إن وُجد، بلا حدث استئناف ولا حصة جديدة
  *g_resume_mine() {
    const c = this.saved.find((x) => this.mine(x));
    if (c !== undefined) yield* this.g_resume(c);
    const st = this.stage;
    if (st !== null && st.after) {
      this.log.push([this.sessions, st.after[0], st.after[1]]);
      st.after = null;
    }
  }

  // تكملة الجلسة الجارية بعد استعادة: الأجزاء الباقية منها، ثم ختمها. لا تبدأ جلسة ولا تستهلك حصة
  *g_continue() {
    if (this.cur === null) return;
    const kind = this.stage.kind;
    if (kind === 'search') {
      yield* this.g_search_body(this.stage.gate || this.next_gate());
    } else if (kind === 'start') {
      yield* this.g_start_body();
    } else if (kind === 'extra') {
      yield* this.g_extra_body();
    } else if (this.learning) {
      yield* this.g_follow_body();
    } else {
      throw new Error('تكملة جلسة المتابعة في وضع التشخيص وحده غير منفّذة');
    }
  }
}

// ---------------------------------------------------------------- الخطوات والأغلفة المتزامنة
// سلسلة الاستدعاء التي تعرض بنودًا مولّدات (g_*): تعطي [البند، المطلوب] وتستقبل ما كانت answer تعيده. والدوال
// بأسمائها السابقة أغلفة متزامنة تشغّل المولّد بـ this.answer، فلا يتغير شيء لمن يستدعيها. والواجهة تشغّل المولّد
// نفسه خطوة خطوة. حالة المولّد ليست مصدر الاستعادة: المتابعة بعد الإغلاق تُبنى من الحالة المحفوظة.
export const STEPPED = ['ready', 'describe', 'run_act', 'show', 'consolidate', 'lesson_body', 'open_lesson', 'gate', 'short', 'opening', 'evidence', 'check', 'retention_check', 'recall', 'search', 'working_point', 'start_session', 'follow', 'teach', 'resume', 'run', 'follow_learning', 'resume_mine', 'extra', 'extra_body', 'extra_step'];
for (const name of STEPPED) {
  Scheduler.prototype[name] = function sync(...args) {
    return runSync(this['g_' + name](...args), (item, w) => this.answer(item, w));
  };
}
