// محرك التطبيق لانتقال الحالات: نقل transition_engine.py إلى JavaScript، دالةً بدالة وبالأسماء نفسها.
//
// المرجع هو المحرك المرجعي بلغة بايثون وجدول انتقالاته في state-transition-spec.md. هذا الملف لا يضيف قاعدة
// ولا يغيّر واحدة. بياناته (الشبكة، المخطط، الحصص، رموز الرفض) في engine_data.mjs المولَّد من المرجع.
// يُتحقق منه بمتجهات المطابقة: node app/test_conformance.mjs
//
// القواعد كما في المرجع: كل تغيير حدث له معرّف؛ المخطط ثم الهوية ثم شروط القبول قبل أي كتابة؛ التنفيذ ذرّي؛
// المحرك لا يُبقي مرجعًا إلى مدخل ولا يعيد مرجعًا إلى حالته؛ حالة المهارة تُشتق ولا تُخزَّن؛ والحالة كلها نص JSON.
// لا يعتمد على المتصفح ولا على Node: يعمل في الاثنين.
import { DATA } from './engine_data.mjs';

const { schema: SCHEMA, reasons: REASONS, quota: QUOTA, search_cap: SEARCH_CAP } = DATA;
const { gaps: RETENTION_GAPS, items: RETENTION_ITEMS, ok: RETENTION_OK } = DATA.retention;
const MIGRATION = DATA.migration;              // نسخة ترحيل الحالة المحفوظة (المراجعة 12)

const EXEMPT = 'exempt', STUMBLE = 'stumble', UNDERSTOOD = 'understood', INDEPENDENT = 'independent',
  SHORT_OK = 'short_ok', RECHECK = 'recheck';
const SATISFIED = ['exempt', 'met'];
const BLOCKING = ['stumbled', 'waiting'];
export const OPEN_CHECK = ['pending', 'held', 'needs_restart'];

const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
const clone = (x) => (x === undefined ? undefined : JSON.parse(JSON.stringify(x)));
const isDict = (x) => x !== null && typeof x === 'object' && !Array.isArray(x);
// مفتاح يأتي من الحدث (معرّف حدث أو جلسة أو محاولة) يُكتب خاصيةً صريحة، فلا يمسّ اسمٌ مثل __proto__ الكائن نفسه
const put = (o, k, v) => Object.defineProperty(o, k, { value: v, writable: true, enumerable: true, configurable: true });

// النص القياسي: مفاتيح مرتبة وفواصل «, » و«: »، كما يكتبه المرجع (json.dumps مع sort_keys). به يُقارن محتوى
// الحدث المكرر، وبه تُحفظ الحالة، فيطابق نص المحركين حرفًا بحرف.
export function canonical(x) {
  if (x === null || x === undefined) return 'null';
  if (typeof x === 'string') return JSON.stringify(x);
  if (typeof x === 'number' || typeof x === 'boolean') return String(x);
  if (Array.isArray(x)) return '[' + x.map(canonical).join(', ') + ']';
  return '{' + Object.keys(x).sort().map((k) => JSON.stringify(k) + ': ' + canonical(x[k])).join(', ') + '}';
}

// حدث ختام كل نشاط: قاعدة قبوله هي قاعدة استمرار النشاط (may_continue)
const CONTINUE = { gate: 'gate_result', short: 'short_check_result', opening: 'lesson_opening_result',
  evidence: 'understanding_proved', check: 'independence_result', retention: 'retention_result' };
const ok = (extra = {}) => ({ ok: true, ...extra });
const no = (code, missing = null) => ({ ok: false, code, reason: REASONS[code], missing });

function fits(v, rule) {
  if (rule === 'str') return typeof v === 'string' && v !== '';
  if (rule === 'bool') return typeof v === 'boolean';
  if (rule === 'int') return typeof v === 'number' && Number.isInteger(v);
  if (Array.isArray(rule)) return typeof v === 'string' && rule.slice(1).includes(v);
  return Array.isArray(v) && v.every((x) => typeof x === 'string' && x !== '');
}

export class Engine {
  constructor(net = DATA.network, { group = 'older', regate = true, versions = null } = {}) {
    this.ids = net.ids;
    this.pre = net.pre;
    this._items = [];
    this.idx = {};
    this.ids.forEach((s, n) => { this.idx[s] = n; });
    this.anc = {};
    for (const s of this.ids) {          // المتطلبات تسبق مهاراتها في الترتيب
      const a = new Set(this.pre[s]);
      for (const p of this.pre[s]) for (const q of this.anc[p]) a.add(q);
      this.anc[s] = a;
    }
    this.versions = versions === null ? null : new Set(versions);
    this.s = {
      group, regate, seq: 0, log: [], applied: {}, evidence: [], decisions: [], attempts: [], sessions: {},
      order: [], current: null, opened: {}, queue: [], gates: {}, checked: [], checks: {}, suspended: {},
      history: [], retention: [], migration: MIGRATION,
    };
  }

  _byIdx(list) {
    return [...list].sort((a, b) => this.idx[a] - this.idx[b]);
  }

  _hasVersion(v) {
    return this.versions === null || this.versions.has(v);
  }

  // ---------------------------------------------------------------- حفظ واستئناف
  dump() {
    return canonical(this.s);
  }

  static restore(net, text, contentVersions = null) {
    const st = JSON.parse(text);
    const e = new Engine(net, { group: st.group, regate: st.regate, versions: contentVersions });
    e.s = st;
    if (!has(st, 'retention')) st.retention = [];
    if ((st.migration ?? 0) < MIGRATION) {
      e._migrateChecks();
      st.migration = MIGRATION;
    }
    for (const [cid, c] of Object.entries(st.checks)) {
      if (c.state === 'pending' && !e._hasVersion(c.content_version)) {
        c.state = 'needs_restart';
        st.history.push({ seq: st.seq, what: 'check_needs_restart', check: cid });
      }
    }
    return e;
  }

  // ترحيل حالة نسختها أقل من MIGRATION (المراجعتان 11 و12). وجود قائمة الجلسات المساهمة لا يثبت شيئًا: تُستكمل
  // القائمة من أحداث السجل ومن حقول المحاولة، مرتبةً بترتيب الجلسات، ثم يُطبَّق أثر كل جلسة مساهمة أُبطلت، ولا يتكرر.
  // وإن خلا السجل من بدء المحاولة، فجلسة مبطلة في مداها، من البدء إلى الختم أو آخر جلسة، تُعامل كأنها مساهمة،
  // بسبب migration_unverified
  _migrateChecks() {
    const st = this.s;
    const pos = new Map(st.order.map((x, n) => [x, n]));
    const at = (x) => this._invalidatedAt(x);
    let hit = false;
    for (const [cid, c] of Object.entries(st.checks)) {
      const logged = st.log.filter((ev) => (ev.type === 'check_started' || ev.type === 'check_resumed')
        && ev.check_id === cid).map((ev) => ev.session);
      const known = st.log.some((ev) => ev.type === 'check_started' && ev.check_id === cid);
      const have = new Set([...(c.sessions || []), ...logged,
        ...[c.session, c.active, c.held_session, c.closed_session].filter((x) => x)]);
      c.sessions = [...have].sort((x, y) => pos.get(x) - pos.get(y));
      let bad = c.sessions.filter((x) => st.sessions[x].invalid);
      let reason = 'session_invalidated';
      if (!bad.length && !known) {
        const a = pos.get(c.session);
        const b = c.closed_session ? pos.get(c.closed_session) : st.order.length - 1;
        bad = st.order.slice(a, b + 1).filter((x) => st.sessions[x].invalid);
        reason = 'migration_unverified';
      }
      if (bad.length) {                       // أقدم إبطال أولًا: هو الذي يحدد أسبق الختمَ أم لا
        const key = (x) => (at(x) === null ? [1, 0] : [0, at(x)]);
        const first = bad.reduce((m, x) => {
          const [p, q] = key(x), [r, t] = key(m);
          return p < r || (p === r && q < t) ? x : m;
        });
        hit = this._taintCheck(cid, first, reason, true) || hit;
      }
    }
    if (hit) this._reconcile();
  }

  _invalidatedAt(session) {
    const h = this.s.history.find((x) => x.what === 'session_invalidated' && x.session === session);
    return h ? h.seq : null;
  }

  // أثر إبطال جلسة أسهمت في محاولة فحص. غير المكتملة تحتاج إعادة بدء. والمكتملة يسقط دليلها، وإن كان الإبطال قبل
  // ختمها (حالة قديمة قبِل محركها النتيجة بعده) فحكمها حكم غير المكتملة، كما في إعادة تشغيل سجلها
  _taintCheck(cid, session, reason, migrated = false) {
    const c = this.s.checks[cid];
    const extra = migrated ? { reason, migrated: true } : {};
    const when = this._invalidatedAt(session);
    const reopen = migrated && c.state === 'closed' && !c.invalid && when !== null && when < c.closed_seq;
    if (c.state === 'closed' && !c.invalid && !reopen) {
      c.invalid = true;                       // اكتملت: يسقط دليلها، وتبقى بنودها في السجل
      this._dropCheckEvidence(cid);
      this.s.history.push({ seq: this.s.seq, what: 'check_invalidated', check: cid, session, ...extra });
      return true;
    }
    if (c.state === 'pending' || c.state === 'held' || reopen) {   // لم تكتمل: لا تُستأنف ولا تُقبل نتيجتها
      if (reopen) {
        c.migrated_result = c.result;
        delete c.result;
        delete c.closed_session;
        delete c.closed_seq;
        this._dropCheckEvidence(cid);
      }
      c.restart_reason = reason;
      c.state = 'needs_restart';
      this.s.history.push({ seq: this.s.seq, what: 'check_needs_restart', check: cid, session, ...extra });
      return true;
    }
    return false;                             // طُبّق الأثر من قبل، أو المحاولة متروكة
  }

  _dropCheckEvidence(cid) {
    for (const e of this.s.evidence) if (e.check === cid && e.valid) e.valid = false;
  }

  static replay(net, log, opts = {}) {
    const e = new Engine(net, opts);
    for (const ev of log) e.apply(ev);
    return e;
  }

  // ---------------------------------------------------------------- الاشتقاق
  _add(skill, kind, source, session, extra = {}) {
    this.s.evidence.push({
      id: 'E' + (this.s.evidence.length + 1), skill, kind, source, session, seq: this.s.seq, valid: true,
      items: [...this._items], ...extra,
    });
  }

  _attempt(fields) {
    this.s.attempts.push({ seq: this.s.seq, items: [...this._items], ...fields });
  }

  validEvidence(skill = null, kind = null) {
    return this.s.evidence.filter((e) => e.valid && (skill === null || e.skill === skill)
      && (kind === null || e.kind === kind));
  }

  decisions(kind, skill = null) {
    return this.s.decisions.filter((d) => d.standing && d.kind === kind
      && (skill === null || d.skills.includes(skill)));
  }

  // الحالة المباشرة، والفهم الساري، والاستقلال الساري: من تسلسل واحد للأدلة الصالحة
  progress(skill) {
    return Engine._fold(this.validEvidence(skill));
  }

  static _fold(evidence) {
    let status = null, und = false, ind = false;
    for (const e of evidence) {
      if (e.kind === EXEMPT || e.kind === RECHECK) status = 'exempt';
      else if (e.kind === STUMBLE) { status = 'stumbled'; und = false; ind = false; }
      else if (e.kind === UNDERSTOOD) und = true;
      else if (e.kind === INDEPENDENT) ind = true;
      if (und && ind) status = 'met';
    }
    return [status, und, ind];
  }

  direct(skill) {
    return this.progress(skill)[0];
  }

  // حالة كل مهارة. لا تُخزَّن: تُحسب من الأدلة الصالحة وقرارات المعلم السارية
  derive() {
    const by = {};
    for (const e of this.s.evidence) if (e.valid) (by[e.skill] ||= []).push(e);
    const direct = {};
    for (const s of this.ids) direct[s] = Engine._fold(by[s] || [])[0];
    const deferred = new Set();
    for (const s of this.ids) {
      if (direct[s] === 'exempt' && (by[s] || []).some((e) => e.kind === EXEMPT)) {
        for (const a of this.anc[s]) deferred.add(a);
      }
    }
    for (const d of this.decisions('defer')) for (const x of d.skills) deferred.add(x);
    const st = {};
    for (const s of this.ids) {
      if (direct[s]) st[s] = direct[s];
      else if (this.pre[s].some((p) => BLOCKING.includes(st[p]))) st[s] = 'waiting';
      else if (deferred.has(s)) st[s] = 'deferred';
      else st[s] = null;
    }
    return st;
  }

  blockers(skill, st = null) {
    st = st || this.derive();
    const out = new Set(), stack = [...this.pre[skill]];
    while (stack.length) {
      const p = stack.pop();
      if (st[p] === 'stumbled') out.add(p);
      else if (st[p] === 'waiting') stack.push(...this.pre[p]);
    }
    return this._byIdx(out);
  }

  // دالة الأهلية الواحدة لفتح درس (3.4)
  eligible(skill, mode = 'follow', st = null) {
    st = st || this.derive();
    const bypass = new Set();
    for (const d of this.decisions('open', skill)) for (const b of d.bypass) bypass.add(b);
    for (const p of this._byIdx(this.pre[skill])) {
      if (bypass.has(p) || SATISFIED.includes(st[p])) continue;
      if (BLOCKING.includes(st[p])) return no('prerequisite', p);
      if (mode === 'start' && this.validEvidence(p, SHORT_OK).length) continue;   // استثناء جلسة البدء وحدها
      return no('prerequisite', p);
    }
    return ok();
  }

  // بعد كل حدث مقبول: الدرس المفتوح الذي فقد مسوّغه يُعلَّق، والذي عاد مسوّغه يُستأنف
  _reconcile() {
    const st = this.derive();
    for (const [skill, o] of Object.entries(this.s.opened)) {
      if (SATISFIED.includes(st[skill])) {
        delete this.s.suspended[skill];
        continue;
      }
      const e = this.eligible(skill, o.mode, st);
      const was = has(this.s.suspended, skill);
      if (!e.ok && !was) {
        this.s.suspended[skill] = { missing: e.missing, seq: this.s.seq };
        this.s.history.push({ seq: this.s.seq, what: 'access_suspended', skill, missing: e.missing });
      } else if (!e.ok) {
        this.s.suspended[skill].missing = e.missing;
      } else if (was) {
        delete this.s.suspended[skill];
        this.s.history.push({ seq: this.s.seq, what: 'access_resumed', skill });
      }
    }
  }

  // ---------------------------------------------------------------- التطبيق
  _schema(ev) {
    if (!isDict(ev)) return { ...no('bad_event'), field: null };
    if (!fits(ev.id, 'str')) return { ...no('bad_event'), field: 'id' };
    const spec = typeof ev.type === 'string' && has(SCHEMA, ev.type) ? SCHEMA[ev.type] : null;
    if (spec === null) return { ...no('bad_event'), field: 'type' };
    const names = new Set();
    for (const [f, rule] of Object.entries(spec)) {
      const optional = f.endsWith('?');
      const name = optional ? f.slice(0, -1) : f;
      names.add(name);
      if (!has(ev, name)) {
        if (optional) continue;
        return { ...no('bad_event'), field: name };
      }
      if (!fits(ev[name], rule)) return { ...no('bad_event'), field: name };
    }
    const extra = Object.keys(ev).filter((k) => !names.has(k) && k !== 'id' && k !== 'type').sort();
    return extra.length ? { ...no('bad_event'), field: extra[0] } : null;
  }

  // هل يُقبل الحدث الآن؟ لا يكتب شيئًا ولا يحجز معرّفه
  preflight(ev) {
    const bad = this._schema(ev);
    if (bad) return bad;
    ev = clone(ev);
    const seen = has(this.s.applied, ev.id) ? this.s.applied[ev.id] : null;
    if (seen) {
      if (seen.key !== canonical(ev)) return no('event_id_conflict');
      return { ...clone(seen.result), duplicate: true };
    }
    return this['can_' + ev.type](ev);
  }

  // المدخل الوحيد. مخطط، ثم هوية، ثم شروط القبول، ثم تنفيذ ذرّي على نسخة مستقلة من الحدث
  apply(ev) {
    const bad = this._schema(ev);
    if (bad) return bad;
    ev = clone(ev);
    const key = canonical(ev);
    const seen = has(this.s.applied, ev.id) ? this.s.applied[ev.id] : null;
    if (seen) {
      if (seen.key !== key) return no('event_id_conflict');
      return { ...clone(seen.result), duplicate: true };
    }
    const verdict = this['can_' + ev.type](ev);
    if (!verdict.ok) return verdict;          // لم يُكتب شيء
    const before = this.derive();
    const snapshot = JSON.stringify(this.s);
    let res;
    try {
      this.s.seq += 1;
      this._items = has(ev, 'items') ? ev.items : [];
      this['do_' + ev.type](ev);
      this.s.log.push(ev);
      this._reconcile();
      const after = this.derive();
      const changed = {};
      for (const s of this.ids) if (before[s] !== after[s]) changed[s] = [before[s], after[s]];
      res = ok({ seq: this.s.seq, changed, suspended: this._byIdx(Object.keys(this.s.suspended)) });
      put(this.s.applied, ev.id, { key, result: res });
    } catch (err) {                           // ذرّية: تعود الحالة كما كانت قبل الطلب
      this.s = JSON.parse(snapshot);
      return { ...no('internal_error'), detail: String(err) };
    }
    return clone(res);
  }

  // ---------------------------------------------------------------- فحوص مشتركة
  _session(ev) {
    const cur = this.s.current;
    if (cur === null || cur !== ev.session) return null;
    return this.s.sessions[cur];
  }

  _need(ev, quota = null, skill = true) {
    if (skill && !has(this.idx, ev.skill)) return no('unknown_skill');
    const ses = this._session(ev);
    if (ses === null) return no('no_session');
    if (quota) {
      let limit = QUOTA[ses.kind][quota];
      if (isDict(limit)) limit = limit[this.s.group];
      if (ses[quota] >= limit) return no('quota_' + quota);
    }
    return null;
  }

  _blocked(skill, st) {
    for (const p of this._byIdx(this.pre[skill])) if (BLOCKING.includes(st[p])) return no('blocked', p);
    return null;
  }

  // نشاط على درس: مفتوح، غير معلَّق، لا ينتظر حصة، ونشط في هذه الجلسة إن كان النشاط تعليميًا
  _lesson(ev, phases, active = true) {
    const bad = this._need(ev);
    if (bad) return bad;
    const o = this.s.opened[ev.skill];
    if (!o || !(phases.includes(o.phase) || o.phase === 'due')) return no('not_open');
    if (has(this.s.suspended, ev.skill)) return no('suspended', this.s.suspended[ev.skill].missing);
    if (o.phase === 'due' || (active && o.active !== ev.session)) return no('lesson_idle');
    return null;
  }

  _teachLeft(ses) {
    return ses.teach < QUOTA[ses.kind].teach;
  }

  // ---------------------------------------------------------------- الجلسات
  can_session_start(ev) {
    if (ev.day < 0) return { ...no('bad_event'), field: 'day' };
    if (this.s.current !== null) return no('session_open');
    const kinds = this.s.order.map((x) => this.s.sessions[x].kind);
    const k = ev.kind;
    const fine = (k === 'search' && !kinds.includes('start') && kinds.filter((x) => x === 'search').length < SEARCH_CAP)
      || (k === 'start' && !kinds.includes('start')) || (k === 'follow' && kinds.includes('start'));
    return fine && !has(this.s.sessions, ev.session) ? ok() : no('session_order');
  }

  // مرجع التاريخ (9.1): يوم آخر جلسة، بترتيب الجلسات، تاريخها موثوق، أي لم تُعلَّم بتنبيه أو أكّد الوالد تاريخها.
  // التاريخ المعلَّم غير المؤكد لا يصير مرجعًا. الجلسة المبطلة تبقى مرجعًا: الإبطال يخص الطفل لا الساعة.
  dateReference() {
    for (let k = this.s.order.length - 1; k >= 0; k -= 1) {
      const ses = this.s.sessions[this.s.order[k]];
      if (!ses.clock) return ses.day;
    }
    return null;
  }

  do_session_start(ev) {
    const last = this.dateReference();
    const flag = last !== null && (ev.day < last || ev.day > last + 30);
    put(this.s.sessions, ev.session, {
      kind: ev.kind, day: ev.day, clock: flag, gate: 0, short: 0, teach: 0, ended: false, invalid: false,
    });
    this.s.order.push(ev.session);
    this.s.current = ev.session;
    if (flag) {                               // 9.1: يُحفظ بتنبيه، ولا يُحذف
      this.s.history.push({ seq: this.s.seq, what: 'clock_flag', session: ev.session, day: ev.day, last_day: last });
    }
  }

  can_date_confirmed(ev) {
    const t = has(this.s.sessions, ev.target) ? this.s.sessions[ev.target] : null;
    return t && t.clock ? ok() : no('not_flagged');
  }

  do_date_confirmed(ev) {
    this.s.sessions[ev.target].clock = false;
    this.s.history.push({ seq: this.s.seq, what: 'date_confirmed', session: ev.target });
  }

  can_session_end(ev) {
    return this._session(ev) ? ok() : no('no_session');
  }

  do_session_end(ev) {
    this.s.sessions[ev.session].ended = true;
    this.s.current = null;
  }

  // ---------------------------------------------------------------- البوابة والتحقق القصير
  // بوابات المهارة في دورة التحقق الحالية: ما وقع في جلسات غير مبطلة
  validGates(skill) {
    return this.s.attempts.filter((a) => a.skill === skill && a.what === 'gate' && a.result !== 'interrupted'
      && !this.s.sessions[a.session].invalid).length;
  }

  can_gate_result(ev) {
    let bad = this._need(ev, 'gate');
    if (bad) return bad;
    const skill = ev.skill, st = this.derive();
    bad = this._blocked(skill, st);
    if (bad) return bad;
    if (SATISFIED.includes(st[skill])) return no('already_satisfied');
    const n = this.validGates(skill);
    if (n >= 2) return no('gate_limit');
    const o = this.s.opened[skill];
    if (n === 1 || o) {
      // بوابة بعد فتح الدرس: بعد اختصاره، وفي جلسة لاحقة، والإعادة لمتعثَّر فيها تحتاج السماح
      if (!o || o.phase !== 'skipped' || o.session === ev.session) return no('regate_not_allowed');
      if (st[skill] === 'stumbled' && !this.s.regate) return no('regate_not_allowed');
    }
    return ok();
  }

  do_gate_result(ev) {
    const skill = ev.skill, res = ev.result, ses = this.s.sessions[ev.session];
    this._attempt({ skill, what: 'gate', result: res, session: ev.session });
    if (res === 'interrupted') return;        // بلا نتيجة، ولا تُعدّ بوابة
    ses.gate += 1;
    this.s.gates[skill] = (has(this.s.gates, skill) ? this.s.gates[skill] : 0) + 1;
    this._unqueue(skill);
    if (res === 'pass') {
      this._add(skill, EXEMPT, 'gate', ev.session);
    } else if (res === 'fail') {
      const errs = has(ev, 'errors') ? ev.errors : [];
      const calc = errs.some((t) => t === 'ف3' || t === 'ف4');
      const hasCalc = has(ev, 'has_calc') ? ev.has_calc : true;
      this._add(skill, STUMBLE, 'gate', ev.session, { treatment: calc || !hasCalc ? 'regular' : 'structure' });
    }
    const o = this.s.opened[skill];
    if (o && (res === 'fail' || res === 'help')) {    // يمضي الدرس كاملًا. طلب الدعم بلا دليل
      if (this._teachLeft(ses)) {
        ses.teach += 1;
        o.phase = 'full';
        o.active = ev.session;
        o.taught.push(ev.session);
      } else {
        o.phase = 'due';                      // ينتظر حصة: يُستأنف بحدث resume_lesson
      }
    }
  }

  _unqueue(skill) {
    const k = this.s.queue.indexOf(skill);
    if (k >= 0) this.s.queue.splice(k, 1);
  }

  can_short_check_result(ev) {
    let bad = this._need(ev, 'short');
    if (bad) return bad;
    const skill = ev.skill, st = this.derive();
    bad = this._blocked(skill, st);
    if (bad) return bad;
    if (!(st[skill] === null || st[skill] === 'deferred') || this.s.checked.includes(skill)) return no('not_checkable');
    return ok();
  }

  do_short_check_result(ev) {
    this.s.sessions[ev.session].short += 1;
    this.s.checked.push(ev.skill);
    if (ev.ok) this._add(ev.skill, SHORT_OK, 'short', ev.session);
    else if (!this.s.queue.includes(ev.skill)) this.s.queue.push(ev.skill);
  }

  // ---------------------------------------------------------------- الدرس
  can_open_lesson(ev) {
    const bad = this._need(ev, 'teach');
    if (bad) return bad;
    const skill = ev.skill, st = this.derive();
    if (has(this.s.suspended, skill)) return no('suspended', this.s.suspended[skill].missing);
    if (has(this.s.opened, skill)) return no('already_open');
    if (SATISFIED.includes(st[skill])) return no('already_satisfied');
    return this.eligible(skill, this.s.sessions[ev.session].kind, st);
  }

  do_open_lesson(ev) {
    const ses = this.s.sessions[ev.session];
    ses.teach += 1;
    this.s.opened[ev.skill] = {
      session: ev.session, mode: ses.kind, phase: 'opening', active: ev.session, taught: [ev.session],
    };
  }

  can_resume_lesson(ev) {
    const bad = this._need(ev, 'teach');
    if (bad) return bad;
    const skill = ev.skill;
    const o = this.s.opened[skill];
    if (!o || !['opening', 'full', 'due'].includes(o.phase)) return no('not_open');
    if (has(this.s.suspended, skill)) return no('suspended', this.s.suspended[skill].missing);
    if (o.phase !== 'due' && o.active === ev.session) return no('already_active');
    return this.eligible(skill, o.mode);
  }

  do_resume_lesson(ev) {
    const o = this.s.opened[ev.skill];
    this.s.sessions[ev.session].teach += 1;
    if (o.phase === 'due') o.phase = 'full';
    o.active = ev.session;
    o.taught.push(ev.session);
  }

  // هل يستمر نشاط جارٍ في هذه الجلسة؟ يسأله المجدول قبل عرض كل بند وقبل تطبيق كل إجابة (المراجعة 16)، فقرار يقع
  // أثناء النشاط، كإبطال جلسة أو ترك محاولة، يوقفه قبل أن يُعرض بند أو تُحتسب إجابة. لا يكتب شيئًا ولا يستهلك حصة.
  // القاعدة هي قاعدة قبول حدث ختام النشاط نفسها، وهي لا تقرأ نتيجته (تفحصه الحالة 13 في tests/test_phase0).
  // وبنود الدرس والتدريب (show) لا حدث لها، فشرطها شرط الدرس النشط في الجلسة
  may_continue(kind, session, skill, check_id = null) {
    const ev = { session, skill, check_id, correct: 0 };
    if (kind === 'show') return this._lesson(ev, ['opening', 'skipped', 'full']) || ok();
    return this['can_' + CONTINUE[kind]](ev);
  }

  can_lesson_opening_result(ev) {
    return this._lesson(ev, ['opening']) || ok();
  }

  do_lesson_opening_result(ev) {
    const skill = ev.skill, o = this.s.opened[skill];
    if (ev.outcome === 'skip') {
      o.phase = 'skipped';                    // قاعدة الاختصار لا تتغير بخيار الإعادة
      const stumbled = this.direct(skill) === 'stumbled';
      if ((this.s.regate || !stumbled) && !this.s.queue.includes(skill)) this.s.queue.push(skill);
      return;
    }
    o.phase = 'full';
    if (ev.outcome === 'full_error') {
      // المعالجة تحددها البوابة (6.1): خطأ البنود الموجَّهة يُبقي معالجة آخر تعثّر صالح، والمسار العادي إن لم يكن
      const prev = this.validEvidence(skill, STUMBLE).filter((x) => x.treatment);
      this._add(skill, STUMBLE, 'lesson', ev.session,
        { treatment: prev.length ? prev[prev.length - 1].treatment : 'regular' });
    } else {
      this._attempt({ skill, what: 'lesson', result: 'help', session: ev.session });
    }
  }

  can_understanding_proved(ev) {
    return this._lesson(ev, ['opening', 'full']) || ok();
  }

  do_understanding_proved(ev) {
    this._add(ev.skill, UNDERSTOOD, 'lesson', ev.session);
  }

  // ---------------------------------------------------------------- محاولات فحص الاستقلال
  // درس مفتوح غير معلَّق ولا ينتظر حصة، وفهم سارٍ من التسلسل نفسه الذي يحسب حالة المهارة
  _checkReady(ev) {
    const bad = this._lesson(ev, ['opening', 'skipped', 'full'], false);
    if (bad) return bad;
    return this.progress(ev.skill)[1] ? null : no('understanding_first');
  }

  _checksOf(skill) {
    return Object.values(this.s.checks).filter((c) => c.skill === skill);
  }

  can_check_started(ev) {
    let bad = this._checkReady(ev);
    if (bad) return bad;
    const skill = ev.skill, ses = this.s.sessions[ev.session];
    if (SATISFIED.includes(this.direct(skill))) return no('already_satisfied');
    if (has(this.s.checks, ev.check_id)) return no('check_state');
    if (this._checksOf(skill).some((c) => OPEN_CHECK.includes(c.state))) return no('check_pending');
    if (!this._hasVersion(ev.content_version)) return no('version_unavailable');
    if (ses.clock) return no('date_unconfirmed');
    bad = this._checkTiming(skill, ses.day);
    if (bad) return bad;
    return this._teachLeft(ses) ? ok() : no('quota_teach');
  }

  // 3.6: في يوم بعد يوم الدرس، والإعادة في يوم لاحق، وبعد الإخفاق جلسة تدريب. الأيام أيام الأسرة. تُطبَّق على البدء
  // والاستئناف والنتيجة. المحاولة المكتملة التي أُبطلت جلسة أسهمت فيها لا تُعدّ
  _checkTiming(skill, day) {
    const und = this.validEvidence(skill, UNDERSTOOD);
    if (und.length && day <= this.s.sessions[und[und.length - 1].session].day) return no('check_same_day');
    const closed = this._checksOf(skill).filter((c) => c.state === 'closed' && !c.invalid);
    if (closed.length) {
      let last = closed[0];
      for (const c of closed) if (c.closed_seq > last.closed_seq) last = c;
      if (day <= this.s.sessions[last.closed_session].day) return no('check_same_day');
      if (last.result === 'fail') {
        const at = this.s.order.indexOf(last.closed_session);
        if (!this.s.opened[skill].taught.some((x) => this.s.order.indexOf(x) > at)) return no('check_needs_practice');
      }
    }
    return null;
  }

  do_check_started(ev) {
    this.s.sessions[ev.session].teach += 1;
    put(this.s.checks, ev.check_id, {
      skill: ev.skill, content_version: ev.content_version, session: ev.session, active: ev.session,
      state: 'pending', seq: this.s.seq, sessions: [ev.session],
    });
  }

  _ownCheck(ev) {
    const c = has(this.s.checks, ev.check_id) ? this.s.checks[ev.check_id] : null;
    return c && c.skill === ev.skill ? c : null;
  }

  can_check_resumed(ev) {
    const bad = this._checkReady(ev);
    if (bad) return bad;
    const c = this._ownCheck(ev);
    if (!c) return no('no_check');
    if (c.state !== 'pending') return no('check_state');
    if (c.active === ev.session) return no('already_active');
    if (!this._hasVersion(c.content_version)) return no('version_unavailable');
    const ses = this.s.sessions[ev.session];
    if (ses.clock) return no('date_unconfirmed');     // 9.1: لا يُعتمد عمل فحص في يوم غير مؤكد
    const bad2 = this._checkTiming(ev.skill, ses.day);
    if (bad2) return bad2;
    return this._teachLeft(ses) ? ok() : no('quota_teach');
  }

  do_check_resumed(ev) {
    this.s.sessions[ev.session].teach += 1;
    const c = this.s.checks[ev.check_id];
    c.active = ev.session;
    if (!c.sessions.includes(ev.session)) c.sessions.push(ev.session);   // كل جلسة عُرضت فيها بنود المحاولة
  }

  can_check_held(ev) {
    const bad = this._need(ev);
    if (bad) return bad;
    const c = this._ownCheck(ev);
    if (!c) return no('no_check');
    if (c.state !== 'pending') return no('check_state');
    return c.active === ev.session ? ok() : no('check_idle');
  }

  do_check_held(ev) {
    const c = this.s.checks[ev.check_id];
    c.state = 'held';
    c.hold_reason = ev.reason;                // يبقى بعد الترك
    c.held_session = ev.session;
    c.held_items = has(ev, 'items') ? [...ev.items] : [];   // ما عُرض قبل التعليق، ليراجعه المعلم
  }

  can_check_abandoned(ev) {
    const c = has(this.s.checks, ev.check_id) ? this.s.checks[ev.check_id] : null;
    if (!c) return no('no_check');
    return OPEN_CHECK.includes(c.state) ? ok() : no('check_state');
  }

  do_check_abandoned(ev) {
    const c = this.s.checks[ev.check_id];
    c.state = 'abandoned';
    c.reason = ev.reason;
  }

  can_independence_result(ev) {
    const bad = this._checkReady(ev);
    if (bad) return bad;
    const c = this._ownCheck(ev);
    if (!c) return no('no_check');
    if (c.state !== 'pending') return no('check_state');
    const ses = this.s.sessions[ev.session];
    if (ses.clock) return no('date_unconfirmed');
    if (c.active !== ev.session) return no('check_idle');
    const bad2 = this._checkTiming(ev.skill, ses.day);
    if (bad2) return bad2;
    return this._hasVersion(c.content_version) ? ok() : no('version_unavailable');
  }

  do_independence_result(ev) {
    const c = this.s.checks[ev.check_id];
    c.state = 'closed';
    c.result = ev.result;
    c.closed_session = ev.session;
    c.closed_seq = this.s.seq;
    this._attempt({ skill: ev.skill, what: 'independence', result: ev.result, session: ev.session, check: ev.check_id });
    if (ev.result === 'pass') this._add(ev.skill, INDEPENDENT, 'check', ev.session, { check: ev.check_id });
  }

  // ---------------------------------------------------------------- قرارات المعلم
  can_teacher_open(ev) {
    const skill = ev.skill;
    if (!has(this.idx, skill)) return no('unknown_skill');
    const st = this.derive(), by = new Set(ev.bypass);
    if (!ev.reason || [...by].some((p) => !this.pre[skill].includes(p))) return no('bad_decision');
    for (const p of this._byIdx(this.pre[skill])) {
      if (!SATISFIED.includes(st[p]) && !by.has(p)) return no('bad_decision', p);
    }
    return ok();
  }

  do_teacher_open(ev) {
    this.s.decisions.push({
      id: ev.id, kind: 'open', skills: [ev.skill], standing: true, bypass: [...ev.bypass].sort(),
      reason: ev.reason, seq: this.s.seq,
    });
  }

  can_teacher_defer(ev) {
    if (!ev.skills.length || ev.skills.some((x) => !has(this.idx, x))) return no('unknown_skill');
    if (!ev.reason) return no('bad_decision');
    for (const x of ev.skills) if (this.direct(x)) return no('not_deferrable', x);
    return ok();
  }

  do_teacher_defer(ev) {
    this.s.decisions.push({
      id: ev.id, kind: 'defer', skills: [...ev.skills], standing: true, reason: ev.reason, seq: this.s.seq,
    });
  }

  can_teacher_revoke(ev) {
    return this.s.decisions.some((d) => d.id === ev.decision && d.standing) ? ok() : no('no_decision');
  }

  do_teacher_revoke(ev) {
    for (const d of this.s.decisions) if (d.id === ev.decision) d.standing = false;
  }

  // ---------------------------------------------------------------- إعادة التحقق والإبطال
  // دليل استيفاء أُبطل والمهارة بلا دليل مباشر الآن: دورة تحققها تُعاد بلا إلزام بدرس
  _rebuildable(skill) {
    return this.direct(skill) === null && this.s.evidence.some((e) => !e.valid && e.skill === skill
      && [EXEMPT, RECHECK, INDEPENDENT].includes(e.kind));
  }

  can_recheck_result(ev) {
    const bad = this._need(ev);
    if (bad) return bad;
    const waited = Object.values(this.s.suspended).some((v) => v.missing === ev.skill);
    if (!waited && !this._rebuildable(ev.skill)) return no('no_recheck');
    return this._blocked(ev.skill, this.derive()) || ok();
  }

  do_recheck_result(ev) {
    this._attempt({ skill: ev.skill, what: 'recheck', result: ev.ok ? 'pass' : 'fail', session: ev.session });
    if (ev.ok) this._add(ev.skill, RECHECK, 'recheck', ev.session);
  }

  can_invalidate_session(ev) {
    const t = has(this.s.sessions, ev.target) ? this.s.sessions[ev.target] : null;
    return t && t.ended && !t.invalid ? ok() : no('bad_target');
  }

  do_invalidate_session(ev) {
    this.s.sessions[ev.target].invalid = true;
    const hit = [];
    for (const e of this.s.evidence) {
      if (e.session === ev.target && e.valid) {
        e.valid = false;                      // الدليل يبقى في السجل، غير صالح
        hit.push(e.id);
      }
    }
    this.s.history.push({ seq: this.s.seq, what: 'session_invalidated', session: ev.target, evidence: hit });
    for (const [cid, c] of Object.entries(this.s.checks)) {   // محاولة فحص أسهمت فيها الجلسة
      if (c.sessions.includes(ev.target)) this._taintCheck(cid, ev.target, 'session_invalidated');
    }
    for (const r of this.s.retention) {       // فحص الاحتفاظ في الجلسة المبطلة لا يُعدّ، ويبقى في السجل
      if (r.session === ev.target && r.valid) {
        r.valid = false;
        this.s.history.push({ seq: this.s.seq, what: 'retention_invalidated', retention: r.id });
      }
    }
    for (const [skill, o] of Object.entries(this.s.opened)) {   // الدرس المفتوح فيها: يبقى، ويعود إلى الافتتاح
      if (o.session === ev.target && o.phase !== 'opening') {
        this.s.history.push({ seq: this.s.seq, what: 'opening_reset', skill, phase: o.phase });
        o.phase = 'opening';
        o.active = null;
        this._unqueue(skill);
      }
    }
  }

  // ---------------------------------------------------------------- فحوص الاحتفاظ (3.7)
  // فحص الاحتفاظ التالي للمهارة: [الجولة، يوم الموعد، يوم المرجع، جلسة المرجع]، أو null
  retentionNext(skill) {
    if (this.direct(skill) !== 'met') return null;
    const inds = this.validEvidence(skill, INDEPENDENT);
    const ind = inds[inds.length - 1];
    const done = this.s.retention.filter((r) => r.skill === skill && r.valid && r.seq > ind.seq);
    if (done.length >= RETENTION_GAPS.length) return null;
    const ref = (done.length ? done[done.length - 1] : ind).session;
    const day = this.s.sessions[ref].day;
    return [done.length + 1, day + RETENTION_GAPS[done.length], day, ref];
  }

  // ما استحق من فحوص الاحتفاظ حتى هذا اليوم، الأقدم استحقاقًا أولًا
  retentionDue(day) {
    const out = [];
    for (const s of this.ids) {
      const nxt = this.retentionNext(s);
      if (nxt && nxt[1] <= day) out.push([s, nxt[0], nxt[1]]);
    }
    return out.sort((a, b) => a[2] - b[2] || this.idx[a[0]] - this.idx[b[0]]);
  }

  retentionPending() {
    return this.ids.filter((s) => this.retentionNext(s));
  }

  can_retention_result(ev) {
    const bad = this._need(ev);
    if (bad) return bad;
    if (!(ev.correct >= 0 && ev.correct <= RETENTION_ITEMS)) return { ...no('bad_event'), field: 'correct' };
    if (this.direct(ev.skill) !== 'met') return no('not_met');
    const nxt = this.retentionNext(ev.skill);
    if (nxt === null) return no('retention_done');
    const ses = this.s.sessions[ev.session];
    if (ses.clock) return no('date_unconfirmed');
    return ses.day >= nxt[1] ? ok() : no('retention_early');
  }

  do_retention_result(ev) {
    const skill = ev.skill;
    const [rnd, due, refDay, ref] = this.retentionNext(skill);
    const day = this.s.sessions[ev.session].day, at = this.s.order.indexOf(ref);
    const o = this.s.opened[skill];
    const practised = (has(ev, 'exposed') ? ev.exposed : false)
      || Boolean(o && o.taught.some((x) => this.s.order.indexOf(x) > at));
    const low = ev.correct < RETENTION_OK;
    this.s.retention.push({
      id: 'R' + (this.s.retention.length + 1), skill, round: rnd, session: ev.session, day, due_day: due,
      days_since: day - refDay, correct: ev.correct, of: RETENTION_ITEMS,
      label: practised ? 'deferred_performance' : 'retention', consolidate: low, valid: true, seq: this.s.seq,
      items: [...this._items],
    });
    if (low) {                                // 3.7: تثبيت قصير، ولا يُغلق ما فُتح
      this.s.history.push({ seq: this.s.seq, what: 'retention_consolidate', skill, round: rnd });
    }
  }
}

// قبل التشغيل: لكل حدث في المخطط دالتا فحص وتنفيذ، ولا دالة لحدث خارج المخطط
export function checkEngine() {
  const names = Object.keys(SCHEMA);
  const own = Object.getOwnPropertyNames(Engine.prototype);
  const missing = names.filter((n) => !own.includes('can_' + n) || !own.includes('do_' + n));
  const extra = own.filter((m) => /^(can|do)_/.test(m) && !names.includes(m.replace(/^(can|do)_/, '')));
  if (missing.length || extra.length || names.length !== DATA.events.length) {
    throw new Error('المحرك لا يطابق المخطط: ينقص ' + missing.join(' ') + ' | يزيد ' + extra.join(' '));
  }
  return names.length;
}
