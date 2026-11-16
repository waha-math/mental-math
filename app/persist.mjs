// سياسة الحفظ والاستعادة (9.2) بلغة التطبيق: نقل persist.py. ما يُحفظ، وكيف تُستعاد منه حالة كاملة متسقة.
// الكتابة نفسها في app/store.mjs، معاملة واحدة لسجل الطفل كله.
//
// السجل: engine (نص المحرك)، و scheduler (خياراته وحالته كلها، ومنها saved و parked)، و current (النشاط الجاري
// وبنوده المعروضة و journal: البند المعروض الآن وأحداثه الخام حتى الآن). الحدث الذي يُنهي البند لا يُحفظ في
// journal: يُطوى البند ويُعطى للنشاط ويُفرَّغ journal في الحفظ نفسه.
//
// الاستعادة: البند الجاري يُختم بانقطاع ويُعلَّم «غير محسوم»، والنشاط الجاري يُحفظ في saved، والجلسة التي لم تُختم
// تُختم، ولا يُقبل سجل يخالف فيه المجدولُ المحرك.
import { Engine } from './engine.mjs';
import { Activity, foldItem, classify } from './items.mjs';
import { Scheduler } from './scheduler.mjs';

export const SCHEMA = 1;
export const STATE = ['saved', 'parked', 'carried_items', 'intent', 'pending', 'proven', 'attempt', 'ev_round',
  'last_items', 'n', 'gates_run', 'searches', 'sessions', 'day', 'cur', 'log', 'refused', 'stalled', 'elapsed',
  'start_at', 'items_before', 'start_w', 'start_what'];
const TERMINAL = ['end', 'interrupt'];

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
    no_short: [...sc.no_short].sort(), try_from_gate: sc.try_from_gate, cap: sc.cap, retention: sc.retention };
}

export function stateOf(sc) {
  const d = {};
  for (const k of STATE) d[k] = clone(sc[k] === undefined ? null : sc[k]);
  d.n = Object.fromEntries(Object.entries(d.n).filter(([, v]) => v));
  d.next_id = sc._next;
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
    current: current === null ? null : clone(current) };
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
  net = undefined } = {}) {
  if (record.schema !== SCHEMA) throw new Inconsistent(`نسخة سجل غير معروفة: ${record.schema}`);
  const e = Engine.restore(net, record.engine, contentVersions);
  const o = { ...record.scheduler.opts };
  const sc = new Scheduler(e, types, source, answer, { ...o, records, item_seconds });
  const st = clone(record.scheduler.state);
  const bad = checkConsistent(e, st);
  if (bad.length) throw new Inconsistent(bad.join('؛ '));
  for (const k of STATE) sc[k] = st[k];
  sc._next = st.next_id;
  const notes = [];
  const cur = record.current ? clone(record.current) : null;
  if (cur) {
    let entry;
    if (cur.kind === 'show') {
      entry = { kind: 'show', skill: cur.skill, activity: cur.activity, pos: cur.pos, items: [] };
    } else {
      const act = Activity.fromDict(cur.act);
      const items = [...cur.items];
      const j = cur.journal;
      if (j) {                                  // البند الجاري: يُختم بانقطاع، «غير محسوم»
        const rec = foldItem([...j.raw, ['interrupt']], j.answer, j.assess);
        act.feed(classify(rec));
        if (j.item) items.push(j.item);
        if (sc.records !== null) {
          sc.records.push({ ...rec, skill: act.skill, activity: act.name, role: j.want.role ?? null, item: j.item ?? null,
            unsettled: true });
        }
        notes.push(['unsettled_item', act.skill, j.item ?? null, classify(rec)]);
      }
      entry = { kind: cur.kind, skill: act.skill, act: act.toDict(), items };
    }
    sc.save(entry);
    notes.push(['current_saved', cur.kind, cur.skill]);
  }
  if (e.s.current !== null) {                   // التطبيق أُغلق في جلسة لم تُختم
    const ses = e.s.current;
    const r = e.apply({ id: `restore-end-${ses}`, type: 'session_end', session: ses });
    if (!r.ok) throw new Inconsistent(`تعذر ختم الجلسة ${ses}: ${r.code}`);
    sc.cur = null;
    notes.push(['session_closed', ses]);
  }
  return { engine: e, scheduler: sc, notes };
}
