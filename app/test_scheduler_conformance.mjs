// مطابقة المجدول في التطبيق (app/scheduler.mjs) بالمجدول المرجعي (scheduler.py).
//
//     python3 export_scheduler.py <ملف الخريطة>     (يكتب app/scheduler_vectors.json)
//     node app/test_scheduler_conformance.mjs
//
// لكل مجدول مسجّل: محرك التطبيق بحالة المحرك المرجعي عند إنشاء المجدول، ومجدول التطبيق بالخيارات نفسها، ومصدر
// البنود والطفل ومدة البند من الشريط المسجّل بترتيبه. كل نداء من الخارج يُعاد، ويطابق إن أعاد النتيجة نفسها وترك
// حالة المجدول نفسها وبصمة المحرك نفسها، وإن طلب من الشريط ما طلبه المرجع بالترتيب نفسه.
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { Engine, canonical } from './engine.mjs';
import { Scheduler, Capped } from './scheduler.mjs';
import { CLASSES } from './items.mjs';

const V = JSON.parse(readFileSync(new URL('scheduler_vectors.json', import.meta.url), 'utf8'));
const digest = (e) => createHash('sha256').update(canonical({ s: e.s, d: e.derive() }), 'utf8').digest('hex');
const same = (a, b) => canonical(a) === canonical(b);
const STATE = ['carry', 'parked', 'carried_items', 'intent', 'pending', 'proven', 'attempt', 'ev_round', 'last_items',
  'n', 'gates_run', 'searches', 'sessions', 'day', 'cur', 'log', 'refused', 'stalled', 'elapsed', 'start_at',
  'items_before', 'start_w', 'start_what'];
const results = [];

function check(name, cond) {
  results.push(Boolean(cond));
  console.log(`  ${cond ? 'نجح' : 'أخفق'}  ${results.length}. ${name}`);
}

// القيمة كما يسجّلها المرجع: المجموعات مرتبة، والعدّادات بلا أصفار، والنشاط بصيغة حفظه
function plain(x) {
  if (x instanceof Set) return [...x].map(plain).sort();
  if (Array.isArray(x)) return x.map(plain);
  if (x && typeof x === 'object') {
    if (Object.values(CLASSES).some((c) => x instanceof c)) return x.toDict();
    const o = {};
    for (const [k, v] of Object.entries(x)) o[k] = plain(v);
    return o;
  }
  return x === undefined ? null : x;
}

const nonzero = (o) => Object.fromEntries(Object.entries(o).filter(([, v]) => v));

function snapshot(sc) {
  const d = {};
  for (const k of STATE) d[k] = plain(sc[k]);
  d.n = nonzero(d.n);
  for (const k of ['log', 'refused']) {         // تطول مع الجلسات: طولها وبصمتها، وآخرها للتشخيص
    const v = d[k];
    d[k] = { n: v.length, h: createHash('sha256').update(canonical(v), 'utf8').digest('hex'), last: v.slice(-3) };
  }
  d.next_id = sc._next;
  d.records = sc.records === null ? null
    : createHash('sha256').update(canonical(sc.records.map(plain)), 'utf8').digest('hex');
  return d;
}

function setState(sc, snap) {
  for (const k of STATE) if (k !== 'log' && k !== 'refused') sc[k] = structuredClone(snap[k]);
  sc._next = snap.next_id;
}

class TapeError extends Error {}

function runTrace(tr, stats) {
  const eng = Engine.restore(undefined, tr.engine.text, tr.engine.versions);
  if (eng.s.group !== tr.engine.group || eng.s.regate !== tr.engine.regate) throw new TapeError('إعداد المحرك');
  let pos = 0;
  const next = (kind, ...args) => {
    const x = tr.tape[pos++];
    if (!x || x[0] !== kind) throw new TapeError(`الشريط ${pos}: طُلب ${kind} والمسجّل ${x ? x[0] : 'لا شيء'}`);
    for (let i = 0; i < args.length; i++) {
      if (!same(args[i], x[i + 1])) {
        throw new TapeError(`الشريط ${pos} (${kind}): المدخل ${canonical(args[i])} والمسجّل ${canonical(x[i + 1])}`);
      }
    }
    return x[args.length + 1];
  };
  const item = (i) => (i === null ? null : structuredClone(V.tables.items[i]));
  const source = (skill, want) => item(next('src', skill, want));
  const itemIndex = (it) => {
    const key = canonical(it);
    if (!itemIndex.map) itemIndex.map = new Map(V.tables.items.map((x, i) => [canonical(x), i]));
    return itemIndex.map.get(key) ?? -1;
  };
  const records = tr.opts.records ? [] : null;
  const opts = { ...tr.opts, records, item_seconds: tr.timed ? (want) => next('sec', want) : null };
  const sc = new Scheduler(eng, V.tables.types[tr.types], source, (it, want) => next('ans', itemIndex(it), want), opts);
  for (const [k, op] of tr.ops.entries()) {
    const where = `العملية ${k + 1} (${op.op})`;
    if (op.pre) setState(sc, op.pre);
    if (op.pre_engine) eng.s = Engine.restore(undefined, op.pre_engine, tr.engine.versions).s;
    let ret, raised = null;
    try {
      ret = op.op === 'engine_apply' ? sc.e.apply(op.args[0]) : sc[op.op](...op.args);
    } catch (err) {
      if (err instanceof TapeError) throw new TapeError(`${where}: ${err.message}`);
      if (!(err instanceof Capped)) throw new Error(`${where}: ${err.stack}`);
      raised = 'Capped';
    }
    stats.ops[op.op] = (stats.ops[op.op] || 0) + 1;
    if ((op.raise || null) !== raised) return `${where}: الاستثناء ${raised}، والمرجع ${op.raise || 'لا شيء'}`;
    if (!raised && !same(plain(ret === undefined ? null : ret), op.ret === undefined ? null : op.ret)) {
      return `${where}: أعاد ${canonical(plain(ret))}، والمرجع ${canonical(op.ret)}`;
    }
    const snap = snapshot(sc);
    for (const key of Object.keys(op.post)) {
      if (!same(snap[key], op.post[key])) {
        return `${where}: ${key} = ${canonical(snap[key]).slice(0, 300)}، والمرجع ${canonical(op.post[key]).slice(0, 300)}`;
      }
    }
    if (digest(sc.e) !== op.h) return `${where}: بصمة المحرك تخالف المرجع`;
  }
  if (pos !== tr.tape.length) return `بقي في الشريط ${tr.tape.length - pos} نداء لم يطلبه المجدول`;
  stats.tape += pos;
  for (const x of sc.log) stats.logs.add(String(x[1]).split(':')[0]);
  return null;
}

console.log('=== مطابقة المجدول في التطبيق بالمجدول المرجعي');
const stats = { ops: {}, tape: 0, logs: new Set() };
const bad = [];
for (const [i, tr] of V.traces.entries()) {
  let msg;
  try { msg = runTrace(tr, stats); } catch (err) { msg = err.message; }
  if (msg) bad.push(`المجدول ${i + 1}: ${msg}`);
}
const src = Object.entries(V.sources).filter(([k]) => k !== 'مستبعد').map(([k, v]) => `${k} ${v}`).join('، ');
const nops = Object.values(stats.ops).reduce((a, b) => a + b, 0);
check(`${V.traces.length} مجدولًا (${src}، واستُبعد ${V.sources['مستبعد']} بدّل فيه الاختبار دالة من دوال المجدول): ${nops} نداءً من الخارج و${stats.tape} نداءً للشريط. النتيجة وحالة `
  + 'المجدول وبصمة المحرك تطابق المرجع بعد كل نداء، والشريط يُطلب بترتيبه كاملًا', !bad.length);
for (const b of bad.slice(0, 5)) console.log('        ' + b);
const kinds = new Set(V.traces.flatMap((t) => t.ops.map((o) => o.op)));
check(`الدوال المنادَاة من الخارج موجودة كلها في مجدول التطبيق: ${[...kinds].sort().join('، ')}`,
  [...kinds].every((k) => k === 'engine_apply' || typeof Scheduler.prototype[k] === 'function'));
const logs = new Set(stats.logs);
check(`مداخل سجل المجدول التي ظهرت: ${[...logs].sort().join('، ')}`,
  ['capped', 'carry_dropped', 'carry_parked', 'carry_resumed', 'check_pass', 'lesson', 'skip'].every((x) => logs.has(x)));
console.log(results.every(Boolean) ? `نجحت الاختبارات كلها: ${results.length}` : 'أخفق اختبار');
process.exit(results.every(Boolean) ? 0 : 1);
