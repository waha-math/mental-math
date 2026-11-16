// المجدول بلغة التطبيق: نقل scheduler.py دالةً بدالة. يختار نشاط الجلسة، ويشغّله عبر طبقة البنود، ويرسل أحداثه
// إلى المحرك (6.2 و7.1 في الخريطة).
//
// لا يحمل المجدول حالة تقدّم. كل ما يقرّر به يقرؤه من المحرك، ويسأله (preflight) قبل عرض أول بند من أي نشاط.
// حالته الخاصة تخطيطية: بوابات نواها في جلسة البدء، وأنواع دليل الفهم التي ثبتت، وعدد محاولات الفحص، والنشاط
// المحفوظ الذي قطعه سقف الوقت (carry)، والنشاط المركون بعد رفض مؤقت (parked).
//
// المرجع هو scheduler.py: كل قرار هنا يطابقه في متجهات app/scheduler_vectors.json (app/test_scheduler_conformance.mjs).
import { OPEN_CHECK } from './engine.mjs';
import { CALC, Activity, GateRun, ShortCheckRun, OpeningRun, EvidenceRun, CheckRun, RetentionRun, drive, gatePlan }
  from './items.mjs';

export const GATES_PER_SEARCH = { older: 2, young: 1 };
export const ITEM_BUDGET = 20;          // بنود البوابات المخططة في جلسة بحث للكبيرين
export const SHORT_FOLLOW = 2;          // تحققان قصيران على الأكثر في جلسة متابعة
export const SHORT_START = 4;           // في جلسة البدء
export const SEARCH_CAP = 4;
export const DONE = ['exempt', 'met'];
export const DIAG = ['gate', 'comp', 'try', 'short'];      // البنود التشخيصية
export const RETENTION_PER_SESSION = 1;
// أسباب رفض استئناف نشاط محفوظ (المراجعة 11): النهائية وحدها تُسقطه، والخاصة بالجلسة تُبقيه في carry، وما سواها
// مؤقت يخص المهارة فيُركن بتقدّمه في parked
export const FINAL_REFUSALS = ['check_state', 'no_check', 'version_unavailable', 'already_satisfied', 'unknown_skill',
  'bad_event'];
export const SESSION_REFUSALS = ['date_unconfirmed', 'no_session'];

export function refusalKind(code) {
  if (FINAL_REFUSALS.includes(code)) return 'final';
  if (SESSION_REFUSALS.includes(code) || code.startsWith('quota_')) return 'session';
  return 'later';
}

// بلغت الجلسة سقف وقتها: تُختم، وما لم يكتمل محفوظ في carry
export class Capped extends Error {
  constructor() {
    super('Capped');
    this.name = 'Capped';
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
    retention = false,
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
    this.content_version = content_version;
    this.records = records;
    this.no_short = new Set(no_short);  // 6.2: قرار المعلم بالتأجيل يُسقط التحقق القصير أيضًا، للمقارنة
    this.try_from_gate = try_from_gate; // 6.2 بقرار الأب (ك4)
    this.cap = cap;
    this.item_seconds = item_seconds || (() => 0);
    this.elapsed = 0;
    this.carry = null;
    this.carried_items = [];
    this.parked = {};                   // مهارة ← نشاط تعليمي محفوظ رُفض استئنافه رفضًا مؤقتًا يخص المهارة
    this.retention = retention;
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
  }

  // ---------------------------------------------------------------- المحرك
  send(payload) {
    const ev = { ...payload, id: 'e' + this._next++ };
    if (['gate_result', 'short_check_result', 'open_lesson', 'resume_lesson', 'lesson_opening_result',
      'understanding_proved', 'check_started', 'independence_result', 'check_resumed', 'check_held',
      'recheck_result', 'retention_result', 'session_end'].includes(payload.type) && !('session' in ev)) {
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
    this.day += 1;
    this.sessions += 1;
    this.cur = 'S' + this.sessions;
    this.elapsed = 0;
    this.send({ type: 'session_start', session: this.cur, kind, day: this.day });
  }

  end() {
    this.send({ type: 'session_end', session: this.cur });
    this.cur = null;
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
  over() {
    return this.cap !== null && this.elapsed >= this.cap;
  }

  tick(w) {
    this.elapsed += this.item_seconds(w);
    return this.over();
  }

  // المهارة التي حُفظ لها نشاط من هذا النوع لم يكتمل، أو null
  carried(kind, skill = null) {
    const c = this.carry;
    return c && c.kind === kind && (skill === null || skill === c.skill) ? c.skill : null;
  }

  // النشاط المحفوظ لهذه المهارة إن كان، ليُستأنف من حيث توقف
  take(kind, skill) {
    if (!this.carried(kind, skill)) return null;
    const c = this.carry;
    this.carry = null;
    this.carried_items = c.items;
    return Activity.fromDict(c.act);
  }

  drop_carry(why) {
    this.log.push([this.sessions, 'carry_dropped:' + why, this.carry.skill]);
    this.carry = null;
    this.carried_items = [];
  }

  // حدث استئناف نشاط تعليمي محفوظ: check_resumed للفحص، و resume_lesson لأنشطة الدرس إن لم يكن نشطًا
  resume_need(c) {
    const s = c.skill;
    if (c.kind === 'check') return { type: 'check_resumed', skill: s, check_id: c.act.check_id };
    return this.e.s.opened[s].active === this.cur ? null : { type: 'resume_lesson', skill: s };
  }

  // السقف: يُحفظ النشاط الذي بدأ. الذي لم يُعرض منه بند لا يُحفظ، إلا الفحص لأن محاولته بدأت في المحرك
  cut(act, kind, items) {
    if (sum(act.shown) || kind === 'check') {
      this.carry = { kind, skill: act.skill, act: act.toDict(), items };
    }
    this.carried_items = [];
    this.log.push([this.sessions, 'capped', act.skill]);
    throw new Capped();
  }

  run_act(act, kind = null) {
    const recs = [], before = { ...act.shown };
    const prior = this.carried_items;
    this.carried_items = [];
    if (this.over()) this.cut(act, kind, prior);   // الجلسة بلغت سقفها: لا يُعرض بند جديد
    drive(act, this.source, this.answer, recs, this.cap !== null ? (w) => this.tick(w) : null);
    if (this.records !== null) this.records.push(...recs);
    const items = [...prior, ...recs.filter((r) => r.item).map((r) => r.item)];
    for (const [k, v] of Object.entries(act.shown)) {
      const d = v - get(before, k);
      if (d > 0) this.n[k] = get(this.n, k) + d;
    }
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
    if (!v.ok && refusalKind(v.code) !== 'session') this.drop_carry(v.code);
    return v.ok;
  }

  gate(s) {
    if (this.carried('gate', s)) {
      if (!this.still_ok({ type: 'gate_result', skill: s, result: 'pass' }, 'gate')) return null;
    } else if (!this.ask({ type: 'gate_result', skill: s, result: 'pass' })) {
      return null;
    }
    const act = this.take('gate', s) || new GateRun({ skill: s, types: this.types[s], tolerant: this.tolerant,
      attempt: this.e.validGates(s) + 1 });
    this.run_act(act, 'gate');
    this.gates_run += 1;
    this.emit(act);
    return act.result;
  }

  short(s) {
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
    this.run_act(act, 'short');
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
  opening(s) {
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
    this.run_act(act, 'opening');
    this.emit(act);
    const kind = act.result === 'skip' ? 'skip' : 'lesson';
    this.log.push([this.sessions, kind, s]);
    if (kind === 'skip' && this.compat && (this.e.s.regate || this.e.direct(s) !== 'stumbled')) this.pending.push(s);
    if (kind === 'lesson' && this.learning) this.lesson_body(s);
    return kind;
  }

  open_lesson(s) {
    if (!this.send({ type: 'open_lesson', skill: s }).ok) return null;
    return this.opening(s);
  }

  // بنود الدرس أو التدريب: تُعرض ولا تصنع حدثًا للمحرك
  show(s, activity, k = 0) {
    for (;;) {
      if (this.over()) {                         // السقف: يُستأنف العرض من موضعه في جلسة لاحقة
        this.carry = { kind: 'show', skill: s, activity, pos: k, items: [] };
        this.log.push([this.sessions, 'capped', s]);
        throw new Capped();
      }
      const w = { activity, pos: k, role: activity };
      const item = this.source(s, { activity, pos: k });
      if (isNone(item)) return k;
      this.answer(item, w);
      this.n[activity] = get(this.n, activity) + 1;
      this.elapsed += this.item_seconds(w);
      k += 1;
    }
  }

  lesson_body(s, k = 0) {
    this.show(s, 'lesson', k);
    this.evidence(s);
  }

  evidence(s) {
    if (!this.ask({ type: 'understanding_proved', skill: s })) return null;
    const act = this.take('evidence', s) || new EvidenceRun({ skill: s, types: this.types[s],
      proven: this.proven[s] || [], round: get(this.ev_round, s) + 1 });
    this.run_act(act, 'evidence');
    if (get(act.shown, 'evidence')) this.ev_round[s] = act.round;   // الجولة التالية ببنود جديدة
    this.proven[s] = [...act.proven];
    this.emit(act);
    if (act.result !== 'proven') this.log.push([this.sessions, 'evidence_' + act.result, s]);
    return act.result;
  }

  check(s) {
    let act = this.take('check', s);            // محاولة قطعها السقف: استؤنفت بحدث check_resumed
    if (act === null) {
      const k = get(this.attempt, s);
      act = new CheckRun({ skill: s, check_id: `${s}/check/${k + 1}`, content_version: this.content_version,
        attempt: String.fromCharCode(65 + k) });
      if (!this.send(act.startEvent()).ok) return null;
      this.attempt[s] = k + 1;
    }
    this.run_act(act, 'check');
    this.emit(act);
    this.log.push([this.sessions, 'check_' + act.result, s]);
    return act.result;
  }

  // فحص احتفاظ مستحق (3.7): 5 بنود جولته، ونتيجته حدث retention_result
  retention_check(s, rnd) {
    if (this.carried('retention', s)) {
      if (!this.still_ok({ type: 'retention_result', skill: s, correct: 0 }, 'retention')) return null;
    } else if (!this.ask({ type: 'retention_result', skill: s, correct: 0 })) {
      return null;
    }
    const act = this.take('retention', s) || new RetentionRun({ skill: s, round: rnd });
    this.run_act(act, 'retention');
    this.emit(act);
    this.log.push([this.sessions, 'retention_' + (act.result ? act.correct : 'cut'), s]);
    return act.result;
  }

  // «استرجع» في أول الجلسة: فحص احتفاظ قطعه السقف، ثم ما استحق، الأقدم استحقاقًا أولًا
  recall() {
    if (!this.retention) return;
    let done = 0;
    const s = this.carried('retention');
    if (s) {
      this.retention_check(s, null);
      done += 1;
    }
    for (const [x, rnd] of this.e.retentionDue(this.day)) {
      if (done >= RETENTION_PER_SESSION) break;
      this.retention_check(x, rnd);
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
      return this.ids.find(freshOk) ?? null;
    }
    if (this.gates_run === 0 && this.inscope.has(this.start) && isNone(st[this.start])) return this.start;
    const inScope = (set) => [...set].filter((a) => this.inscope.has(a)).sort((a, b) => this.idx[a] - this.idx[b]);
    if (c !== null) {
      if (this.e.eligible(c, 'follow', st).ok) return null;   // نقطة العمل محسومة
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
      const a = this.carry.act;
      return a.stage === 'main' ? a.plan.length - a.pos : 2 - a.pos;
    }
    return gatePlan(this.types[x]).length;
  }

  search() {
    while (this.searches < SEARCH_CAP) {
      let x = this.carried('gate') || this.next_gate();   // بوابة قطعها السقف تُستأنف أول الجلسة التالية
      if (x === null) return;
      this.begin('search');
      this.searches += 1;
      let budget = ITEM_BUDGET, done = 0;
      try {
        while (x !== null && done < GATES_PER_SEARCH[this.group]) {
          const size = this.gate_size(x);
          if (done && size > budget) break;
          budget -= size;
          this.gate(x);
          done += 1;
          x = this.next_gate();
        }
      } catch (err) {
        if (!(err instanceof Capped)) throw err;
      }
      this.end();
    }
  }

  working_point() {
    const [st, helped] = this.view();
    let w = this.candidate(st, helped);
    if (w === null) w = this.ids.find((x) => isNone(st[x])) ?? null;
    if (w === null) return null;
    const verified = new Set(this.e.validEvidence(null, 'short_ok').map((x) => x.skill));
    let k = 0;
    for (;;) {
      let moved = false;
      for (const p of [...this.pre[w]].sort((a, b) => this.idx[a] - this.idx[b])) {
        if (DONE.includes(st[p]) || verified.has(p) || !this.inscope.has(p)) continue;
        if (k === SHORT_START) return w;
        k += 1;
        const res = this.short(p);
        if (res === true) {
          verified.add(p);
        } else if (res === false) {
          w = p;
          moved = true;
          break;
        }
      }
      if (!moved) return w;
    }
  }

  start_session() {
    this.begin('start');
    this.start_at = this.sessions;
    let w = null, what = 'none';
    const diag = () => DIAG.reduce((a, c) => a + get(this.n, c), 0);
    try {
      w = this.working_point();
      this.items_before = diag();
      if (w !== null) {
        if (this.e.eligible(w, 'start').ok) {
          what = this.open_lesson(w) || 'none';
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
      what = 'capped';                          // السقف قطع جلسة البدء: ما لم يكتمل في carry
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
    for (const x of this.ids) {
      if (isNone(st[x]) && !(x in opened) && !helped.has(x)) return x;
    }
    return null;
  }

  pick_short() {
    const st = this.e.derive();
    const checked = new Set(this.e.s.checked);
    return this.ids.find((x) => st[x] === 'deferred' && !checked.has(x) && !this.no_short.has(x)) ?? null;
  }

  pick_lesson() {
    const [st, helped] = this.view();
    for (const s of this.ids) {
      if ((st[s] === 'stumbled' || (helped.has(s) && (isNone(st[s]) || st[s] === 'deferred')))
        && !(s in this.e.s.opened) && this.e.eligible(s, 'follow', st).ok) {
        return s;
      }
    }
    return null;
  }

  // جلسة متابعة في وضع التشخيص: بوابة، ثم تحققان قصيران، ثم الحصة التعليمية إن لم تُستهلك
  follow() {
    const g = this.carried('gate') || this.pick_gate();
    if (g === null && this.carry === null && this.pick_short() === null && this.pick_lesson() === null) return false;
    this.begin('follow');
    const shown = sum(this.n);
    let taught = false, capped = false;
    try {
      if (g !== null) {
        const wasOpen = g in this.e.s.opened;
        const r = this.gate(g);
        if (wasOpen && (r === 'fail' || r === 'help')) {
          taught = true;                        // المحرك أمضى الدرس كاملًا واستهلك الحصة
          this.log.push([this.sessions, 'lesson', g]);
          if (this.learning) this.lesson_body(g);
        }
      }
      for (let i = 0; i < SHORT_FOLLOW; i++) {
        const x = this.carried('short') || this.pick_short();
        if (x === null) break;
        if (this.short(x) === false && this.compat) this.pending.push(x);
      }
      if (!taught) {
        if (this.learning) {
          taught = this.teach();
        } else if (this.carried('opening')) {   // افتتاح قطعه السقف: يُستأنف درسه ثم يُكمل
          const o = this.carried('opening');
          if (this.still_ok({ type: 'resume_lesson', skill: o }, 'opening')) {
            this.send({ type: 'resume_lesson', skill: o });
            this.opening(o);
          }
        } else {
          const o = this.pick_lesson();
          if (o !== null) this.open_lesson(o);
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
  teach() {
    let c = this.carry;
    if (c && ['opening', 'evidence', 'show', 'check'].includes(c.kind)) {
      const r = this.resume(c);                 // نشاط قطعه السقف: يُستأنف أولًا
      if (r !== null) return r;
    }
    for (const s of this.carry === null ? Object.keys(this.parked) : []) {   // نشاط رُكن: أول جلسة يُقبل فيها
      c = this.parked[s];
      const need = this.resume_need(c);
      const v = need ? this.e.preflight({ ...need, id: 'ask', session: this.cur }) : { ok: true };
      if (v.ok || refusalKind(v.code) !== 'later') {
        this.carry = this.parked[s];
        delete this.parked[s];
        if (v.ok) this.log.push([this.sessions, 'carry_resumed', s]);
        const r = this.resume(this.carry);
        if (r !== null) return r;
      }
    }
    const st = this.e.derive();
    for (const s of this.ids) {
      const o = this.e.s.opened[s];
      if (!o || s in this.parked || s in this.e.s.suspended || DONE.includes(st[s]) || o.phase === 'skipped') continue;
      if (o.phase === 'due' || !this.e.progress(s)[1]) {
        if (o.active !== this.cur && !this.send({ type: 'resume_lesson', skill: s }).ok) continue;
        if (this.e.s.opened[s].phase === 'opening') this.opening(s);
        else this.lesson_body(s);
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
        this.check(s);
        return true;
      }
      if (v.code === 'check_needs_practice' && this.send({ type: 'resume_lesson', skill: s }).ok) {
        this.show(s, 'practice');
        this.log.push([this.sessions, 'practice', s]);
        return true;
      }
    }
    const o = this.pick_lesson();
    if (o !== null) {
      this.open_lesson(o);
      return true;
    }
    return false;
  }

  // استئناف النشاط التعليمي المحفوظ في carry. true إن استؤنف، و false إن بقي محفوظًا ولا تعليم في الجلسة،
  // و null إن أُسقط أو رُكن فتمضي الحصة إلى غيره
  resume(c) {
    const s = c.skill, need = this.resume_need(c);
    const v = need ? this.e.preflight({ ...need, id: 'ask', session: this.cur }) : { ok: true };
    if (!v.ok) {
      const kind = refusalKind(v.code);
      if (kind === 'session') return false;     // تبقى محفوظة لجلسة فيها الحصة، أو حتى يؤكَّد التاريخ
      if (kind === 'final') {
        this.drop_carry(v.code);
      } else {                                  // مؤقت يخص المهارة: يُركن بتقدّمه، وتمضي الجلسة
        this.parked[s] = c;
        this.carry = null;
        this.carried_items = [];
        this.log.push([this.sessions, 'carry_parked:' + v.code, s]);
      }
      return null;
    }
    if (need) this.send(need);
    if (c.kind === 'check') {
      this.check(s);
    } else if (c.kind === 'opening') {
      this.opening(s);
    } else if (c.kind === 'evidence') {
      this.evidence(s);
    } else {
      this.carry = null;
      if (c.activity === 'lesson') this.lesson_body(s, c.pos);
      else this.show(s, 'practice', c.pos);
    }
    return true;
  }

  satisfied() {
    const st = this.e.derive();
    return this.ids.every((s) => DONE.includes(st[s]));
  }

  // ---------------------------------------------------------------- التشغيل
  run(max_sessions = 200) {
    this.search();
    this.start_session();
    if (this.learning) {
      while (this.sessions < max_sessions && !(this.satisfied() && this.carry === null
        && !Object.keys(this.parked).length && !(this.retention && this.e.retentionPending().length))) {
        this.follow_learning();
      }
    } else {
      while (this.follow()) { /* جلسة متابعة بعد أخرى */ }
    }
    return [this.start_w, this.start_what];
  }

  // جلسة متابعة في وضع التعلّم. تُعقد ولو لم يكن فيها غير «استرجع»، فالأيام تمضي
  follow_learning() {
    this.begin('follow');
    let taught = false;
    try {
      this.recall();
      const g = this.carried('gate') || this.pick_gate();
      if (g !== null) {
        const wasOpen = g in this.e.s.opened;
        const r = this.gate(g);
        if (wasOpen && (r === 'fail' || r === 'help')) {
          taught = true;
          this.log.push([this.sessions, 'lesson', g]);
          if (this.e.s.opened[g].phase === 'full') this.lesson_body(g);
        }
      }
      for (let i = 0; i < SHORT_FOLLOW; i++) {
        const x = this.carried('short') || this.pick_short();
        if (x === null) break;
        this.short(x);
      }
      if (!taught) this.teach();
    } catch (err) {
      if (!(err instanceof Capped)) throw err;
    }
    this.end();
  }
}
