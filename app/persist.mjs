// سياسة الحفظ والاستعادة (9.2) بلغة التطبيق: نقل persist.py. ما يُحفظ، وكيف تُستعاد منه حالة كاملة متسقة.
// الكتابة نفسها في app/store.mjs، معاملة واحدة لسجل الطفل كله.
//
// السجل: engine (نص المحرك)، و scheduler (خياراته وحالته كلها، ومنها saved و parked)، و records (سجل محاولات البنود
// الذي تُشتق منه المؤشرات، المراجعة 14)، و current (النشاط الجاري
// وبنوده المعروضة و journal: البند المعروض الآن وأحداثه الخام حتى الآن). الحدث الذي يُنهي البند لا يُحفظ في
// journal: يُطوى البند ويُعطى للنشاط ويُفرَّغ journal في الحفظ نفسه.
//
// الاستعادة: النشاط الجاري يُضم إلى المخزن، ثم يُسوّى ما فسّره حدث مشروع محفوظ (فحص محفوظ تركه المعلم يُسقط
// من المخزن)، والبند الجاري يُختم بانقطاع ويُعلَّم «غير محسوم»، والنشاط الجاري يُحفظ في saved، والجلسة التي لم تُختم
// تُختم، ولا يُقبل سجل يخالف فيه المجدولُ المحرك.
import { Engine } from './engine.mjs';
import { Activity, foldItem, classify, evidence } from './items.mjs';
import { Scheduler, exposed } from './scheduler.mjs';

export const SCHEMA = 5;                // 2: سجل محاولات البنود (المراجعة 14). 3: موضع الجلسة الجارية (المرحلة 0). 4: هوية المحتوى (ك1).
                                        // 5: سجل البند يحمل جلسته وإصدار حزمته وقيم إجاباته (ك2)
export const STATE = ['saved', 'parked', 'carried_items', 'intent', 'pending', 'proven', 'attempt', 'ev_round',
  'last_items', 'n', 'gates_run', 'searches', 'sessions', 'day', 'cur', 'log', 'refused', 'stalled', 'elapsed',
  'start_at', 'items_before', 'start_w', 'start_what', 'stage'];
const TERMINAL = ['end', 'interrupt'];

// اللقطة فيها نشاط جارٍ بدأ بحزمة محتوى غير المتاحة الآن (ك1). لا يُستأنف ببنك آخر بصمت: إما أن تُتاح الحزمة القديمة
// (packs)، أو تُطلب إعادة بدء صريحة (restart) تحفظ ما وقع وتُسقط الأنشطة الجارية.
// bound: هوية الحزمة التي رُبطت بها المحاولة. offered: هوية المتاحة. pending: [النوع، المهارة] لكل نشاط جارٍ
export class ContentChanged extends Error {
  constructor(bound, offered, pending) {
    super(`نشاط جارٍ بدأ بإصدار المحتوى ${bound === null ? null : bound.version}، والمتاح ${offered.version}`);
    this.name = 'ContentChanged';
    this.bound = bound;
    this.offered = offered;
    this.pending = pending;
  }
}

export class Inconsistent extends Error {
  constructor(msg) {
    super(msg);
    this.name = 'Inconsistent';
  }
}

const clone = (x) => JSON.parse(JSON.stringify(x, (k, v) => (v instanceof Set ? [...v].sort() : v)));

export function options(sc) {
  return { group: sc.group, start: sc.start, scope: sc.ids.length === sc.e.ids.length ? null : [...sc.ids],
    learning: sc.learning, tolerant: sc.tolerant, compat: sc.compat, content_version: sc.content_version,
    no_short: [...sc.no_short].sort(), try_from_gate: sc.try_from_gate, cap: sc.cap, retention: sc.retention,
    content: sc.content === null ? null : { ...sc.content },
    // حد وقت اليوم: يُحفظ حين يُضبط، فلا تتغير اللقطات القائمة
    ...(sc.day_cap !== null && sc.day_cap !== undefined ? { day_cap: sc.day_cap } : {}) };
}

export function stateOf(sc) {
  const d = {};
  for (const k of STATE) d[k] = clone(sc[k] === undefined ? null : sc[k]);
  d.n = Object.fromEntries(Object.entries(d.n).filter(([, v]) => v));
  d.next_id = sc._next;
  if (sc.last !== null && sc.last !== undefined) d.last = clone(sc.last);   // آخر بند عُرض في الجلسة المفتوحة (R22-01)
  for (const k of ['used', 'free']) {             // وقت اليوم وما دُرّب في إضافياته: حين وُجدا
    if (sc[k] !== null && sc[k] !== undefined) d[k] = clone(sc[k]);
  }
  return d;
}

// هل تُنهي هذه الأحداث البند؟ بند التقييم ينتهي بأول تأكيد
export function itemEnds(raw, assess) {
  if (!raw.length) return false;
  if (TERMINAL.includes(raw[raw.length - 1][0])) return true;
  return assess && raw.some((ev) => ev[0] === 'confirm');
}

export function snapshot(engine, sc, current = null, child = '') {
  if (current && current.journal && itemEnds(current.journal.raw, current.journal.assess)) {
    throw new Error('البند المنتهي يُطوى ويُعطى للنشاط قبل الحفظ، ولا يُحفظ في journal');
  }
  return { schema: SCHEMA, child, engine: engine.dump(), scheduler: { opts: options(sc), state: stateOf(sc) },
    records: sc.records === null ? null : clone(sc.records), current: current === null ? null : clone(current) };
}

// تسوية النشاط المحفوظ الذي أنهى صلاحيتَه حدثٌ مشروع في سجل المحرك: ترك المعلم لمحاولة الفحص
export function reconcile(engine, st) {
  const notes = [];
  const abandoned = new Set(engine.s.log.filter((ev) => ev.type === 'check_abandoned').map((ev) => ev.check_id));
  const stale = (c) => {
    if (c.kind !== 'check') return false;
    const ch = engine.s.checks[c.act.check_id];
    return Boolean(ch) && ch.state === 'abandoned' && abandoned.has(c.act.check_id);
  };
  const drop = [...st.saved.filter(stale), ...Object.values(st.parked).filter(stale)];
  for (const c of drop) {
    if (st.saved.includes(c)) st.saved.splice(st.saved.indexOf(c), 1);
    else delete st.parked[c.skill];
    st.log.push([st.sessions, 'carry_dropped:check_abandoned', c.skill]);
    notes.push(['reconciled', c.act.check_id, 'check_abandoned']);
  }
  return notes;
}

export function checkConsistent(engine, st) {
  const bad = [];
  if (st.sessions !== engine.s.order.length) {
    bad.push(`عدد الجلسات في المجدول ${st.sessions} وفي المحرك ${engine.s.order.length}`);
  }
  for (const c of [...st.saved, ...Object.values(st.parked)]) {
    if (c.kind === 'check') {
      const ch = engine.s.checks[c.act.check_id];
      if (!ch || !['pending', 'needs_restart'].includes(ch.state)) bad.push(`فحص محفوظ ${c.act.check_id} ليس معلّقًا في المحرك`);
    }
  }
  const keys = st.saved.map((c) => c.kind + '|' + c.skill);
  if (keys.length !== new Set(keys).size) bad.push('مفتاح محفوظ مرتين');
  if (st.cur !== null && engine.s.current !== st.cur) {
    bad.push(`الجلسة الجارية في المجدول ${st.cur} وفي المحرك ${engine.s.current}`);
  }
  return bad;
}

// يعيد { engine, scheduler, notes }. يرفع Inconsistent إن خالف المجدولُ المحرك
export function restore(record, { types, source, answer, item_seconds = null, records = null, contentVersions = null,
  net = undefined, today = null, content = null, packs = null, restart = false } = {}) {
  if (record.schema !== SCHEMA) throw new Inconsistent(`نسخة سجل غير معروفة: ${record.schema}`);
  const o = { ...record.scheduler.opts };
  // هوية المحتوى (ك1)، كما في persist.restore المرجعي: content هوية الحزمة التي منها source. واحدة: لا شيء. مختلفة
  // ولا نشاط جارٍ: تُربط المحاولة بالمتاحة. مختلفة ونشاط جارٍ: يُستأنف من الحزمة القديمة إن كانت في packs ببصمتها،
  // وإلا يُرفع ContentChanged، وبـrestart تُعاد البداية صراحةً
  const bound = o.content ?? null;
  const sameId = (a, b) => a !== null && b !== null && a.version === b.version && a.digest === b.digest;
  let fresh = false;
  if (content !== null) {
    content = { version: content.version, digest: content.digest };
    const stx = record.scheduler.state;
    const pending = [...(record.current ? [[record.current.kind, record.current.skill]] : []),
      ...[...stx.saved, ...Object.values(stx.parked)].map((c) => [c.kind, c.skill])];
    if (sameId(bound, content)) {
      // لا شيء
    } else if (!pending.length) {
      o.content = content;
      o.content_version = content.version;
    } else if (bound !== null && packs && Object.prototype.hasOwnProperty.call(packs, bound.digest)) {
      source = packs[bound.digest];               // الحزمة التي بدأ بها النشاط: تعريفات بنودها كما كانت
    } else if (restart) {
      fresh = true;
      o.content = content;
      o.content_version = content.version;
      contentVersions = [content.version];        // فحص معلّق بإصدار آخر: needs_restart في المحرك
    } else {
      throw new ContentChanged(bound, content, pending);
    }
  }
  const e = Engine.restore(net, record.engine, contentVersions);
  // الحالة المرشحة تُبنى في نسخ مستقلة، ولا يتغير شيء مما مرّره المستدعي إلا بعد نجاح كل المراحل (R15-01)
  const local = (record.records !== null && record.records !== undefined) ? clone(record.records)   // كما حُفظ
    : (records === null ? null : clone(records));
  const sc = new Scheduler(e, types, source, answer, { ...o, records: local, item_seconds });
  const st = clone(record.scheduler.state);
  const notes = [];
  // رابطة السجل الذي تكتبه الاستعادة وما وقع فيه، كما يكتبهما المجدول في الجلسة (Scheduler.stamp، ك2)
  const linked = (j) => ({ id: `i${sc.records.length}`, session: st.cur,
    pack: (o.content ?? null) === null ? null : o.content.version, ...evidence(j.raw, j.answer, j.v ?? null) });
  if (content !== null && !sameId(bound, content) && sameId(o.content ?? null, content) && !fresh) {
    notes.push(['content_upgraded', bound === null ? null : bound.version, content.version]);
  }
  let cur = record.current ? clone(record.current) : null;
  if (fresh) {                                  // إعادة بدء صريحة بعد تغيّر المحتوى (ك1)
    if (cur && cur.kind !== 'show' && cur.journal) {
      const j = cur.journal;                    // ما وقع في البند المعروض يبقى، مستبعدًا من التقييم
      const rec = foldItem([...j.raw, ['interrupt']], j.answer, j.assess);
      if (sc.records !== null) {
        sc.records.push({ ...rec, ...linked(j), skill: cur.skill, activity: Activity.fromDict(cur.act).name, role: j.want.role ?? null,
          item: j.item ?? null, unsettled: true, void: 'content_changed' });
      }
      notes.push(['void_item', cur.skill, j.item ?? null, 'content_changed']);
    }
    for (const c of [...(cur ? [cur] : []), ...st.saved, ...Object.values(st.parked)]) {
      st.log.push([st.sessions, 'carry_dropped:content_changed', c.skill]);
      notes.push(['content_restart', c.kind, c.skill]);
    }
    st.saved = [];
    st.parked = {};
    st.carried_items = [];
    cur = null;
    notes.push(['content_changed', bound === null ? null : bound.version, content.version]);
  }
  if (cur) {                                    // النشاط الجاري يُضم إلى المخزن قبل التسوية والفحص
    let entry;
    if (cur.kind === 'show') {
      entry = { kind: 'show', skill: cur.skill, activity: cur.activity, pos: cur.pos, items: [] };
      if (cur.consolidate) entry.consolidate = true;   // عرض التثبيت بعد طلب مساعدة في فحص احتفاظ (ت3)
    } else {
      const act = Activity.fromDict(cur.act);
      const items = [...cur.items];
      const j = cur.journal;
      if (j) {                                  // البند الجاري: يُختم بانقطاع، «غير محسوم»
        const rec = foldItem([...j.raw, ['interrupt']], j.answer, j.assess);
        // إن تغيّرت صلاحية النشاط قبل الاستعادة فالبند تاريخ يُحفظ مع سبب استبعاده، ولا يُعطى للنشاط ولا يدخل عدّادًا
        // (R17-01). الحكم حكم المحرك في الجلسة المفتوحة، كما في الجلسة الحية
        const v = e.s.current !== null ? e.may_continue(cur.kind, e.s.current, act.skill, act.check_id ?? null)
          : { ok: true };
        const more = { skill: act.skill, activity: act.name, role: j.want.role ?? null, item: j.item ?? null,
          unsettled: true };
        // ما حمله طلب البند من وسوم يبقى في سجله كما يبقى لو خُتم في الجلسة (driveSteps)
        if (j.want.fact_just_seen) more.fact_just_seen = j.want.fact_just_seen;
        if (j.want.ahead_of) more.ahead_of = [...j.want.ahead_of];
        if (j.want.repeated) more.repeated_after_void = true;
        if (j.want.replaces) more.replaces = j.want.replaces;
        if (v.ok) {
          const shown = { ...act.shown };
          act.feed(classify(rec));
          for (const [k, n] of Object.entries(act.shown)) {   // البند المختوم هنا يدخل العدّاد كما لو خُتم في الجلسة (R16-03)
            const d = n - (shown[k] ?? 0);
            if (d > 0) st.n[k] = (st.n[k] ?? 0) + d;
          }
          if (j.item) items.push(j.item);
          notes.push(['unsettled_item', act.skill, j.item ?? null, classify(rec)]);
        } else {
          act.voided(j.item ?? null, exposed(j.raw));   // التعرّض باقٍ وإن استُبعد البند (R18-01)
          more.void = v.code;
          notes.push(['void_item', act.skill, j.item ?? null, v.code]);
        }
        if (sc.records !== null) sc.records.push({ ...rec, ...linked(j), ...more });
        // البند خُتم هنا، فهو آخر بند عُرض في الجلسة (R23-01)، بقاعدة التعرّض نفسها في Scheduler.seen: خُتم بانقطاع،
        // فيُحتسب تعرّضًا إن أُكدت فيه إجابة أو طُلب فيه دعم. لقطة قديمة بلا حقيقة البند: لا يُعرف
        st.last = j.fact === undefined || j.fact === null || st.cur === null ? null
          : { session: st.cur, skill: act.skill, activity: act.name, item: j.item ?? null, fact: [...j.fact],
            counts: exposed(j.raw) };
      }
      entry = { kind: cur.kind, skill: act.skill, act: act.toDict(), items };
    }
    st.saved.push(entry);
    notes.push(['current_saved', cur.kind, cur.skill]);
  }
  notes.push(...reconcile(e, st));
  const bad = checkConsistent(e, st);
  if (bad.length) throw new Inconsistent(bad.join('؛ '));
  for (const k of STATE) sc[k] = st[k];
  sc.last = st.cur !== null && st.last !== undefined && st.last !== null ? st.last : null;
  sc.used = st.used ?? null;
  sc.free = st.free ?? null;
  sc._next = st.next_id;
  // الجلسة التعليمية غير فتح التطبيق: إغلاقه لا يختمها، فتُكمَل بهويتها ووقتها وحصصها (المرحلة 0ج). تُختم هنا
  // فقط إن انتقل يوم الأسرة: today يوم الأسرة عند الفتح، وبلا قيمة تبقى الجلسة مفتوحة
  if (e.s.current !== null && today !== null && today !== e.s.sessions[e.s.current].day) {
    const ses = e.s.current;
    const r = e.apply({ id: `restore-end-${ses}`, type: 'session_end', session: ses });
    if (!r.ok) throw new Inconsistent(`تعذر ختم الجلسة ${ses}: ${r.code}`);
    if (sc.stage !== null && sc.stage.free) {      // تدريب حر قطعه انتهاء اليوم: لا يأخذ حصة جلسة لاحقة
      for (const c of sc.saved.filter((x) => x.kind === 'show' && x.skill === sc.stage.free && x.activity === 'practice')) {
        sc.saved.splice(sc.saved.indexOf(c), 1);
        notes.push(['free_practice_dropped', c.skill]);
      }
    }
    sc.cur = null;
    sc.stage = null;
    sc.last = null;                               // الجلسة خُتمت: لا «آخر بند» لها بعد (R23-01)
    notes.push(['session_closed', ses]);
  }
  if (records !== null && local !== null) {     // نجحت الاستعادة: تُحدَّث مصفوفة المستدعي بهويتها
    records.splice(0, records.length, ...local);
    sc.records = records;
  }
  return { engine: e, scheduler: sc, notes };
}
