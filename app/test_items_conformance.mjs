// مطابقة طبقة البنود في التطبيق بطبقة البنود المرجعية: node app/test_items_conformance.mjs
//
// يقرأ item_vectors.json (يولّده export_conformance.py من اختبارات المرجع ومن مسارات عشوائية ببذرة ثابتة)،
// ويعيد على طبقة التطبيق كل ما طُلب من المرجع، ويقارن المخرج وبصمة حالة النشاط بعد كل خطوة.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { canonical, Engine } from './engine.mjs';
import { Activity, CLASSES, ContentSource, classify, correctIndependent, drive, foldItem, indicators } from './items.mjs';

const dir = new URL('.', import.meta.url);
const V = JSON.parse(readFileSync(new URL('item_vectors.json', dir), 'utf8'));
const ITEMS = JSON.parse(readFileSync(new URL('../slice-content.json', dir), 'utf8')).items;
const same = (a, b) => canonical(a) === canonical(b);
const digest = (a) => createHash('sha256').update(canonical(a.toDict()), 'utf8').digest('hex');
const results = [];
function check(name, cond, notes = []) {
  results.push(Boolean(cond));
  console.log(`  ${cond ? 'نجح' : 'أخفق'}  ${results.length}. ${name}`);
  for (const n of notes.slice(0, 5)) console.log('    ' + String(n).slice(0, 500));
}
function thrown(f) {
  try { return [false, f()]; } catch (e) { return [true, null]; }
}

console.log('=== مطابقة طبقة البنود في التطبيق بالمرجع');

// 1) البند الخام إلى الحقول الخمسة، ثم النتيجة
let bad = [];
const seen = { error: 0 };
for (const f of V.folds) {
  const [raw, answer, assess] = f.inp;
  const [err, out] = thrown(() => foldItem(raw, answer, assess));
  if (err !== Boolean(f.error)) bad.push('رفض مختلف: ' + JSON.stringify(f.inp));
  else if (err) seen.error += 1;
  else {
    const c = classify(out);
    seen[c] = (seen[c] || 0) + 1;
    if (!same(out, f.out) || c !== f.cls || correctIndependent(out) !== f.ind) bad.push('ناتج مختلف: ' + JSON.stringify(f.inp));
  }
}
check(`${V.folds.length} بندًا خامًا: الحقول الخمسة والنتيجة و«صحيحة مستقلة» تطابق المرجع، والمرفوض هناك مرفوض هنا `
  + `(${seen.error} مرفوضًا، ${seen.correct} صحيحًا، ${seen.wrong} خطأ، ${seen.supported} مدعومًا، ${seen.help} طلب دعم، `
  + `${seen.interrupted} منقطعًا)`, bad.length === 0, bad);

// 2) المؤشرات الأربعة
bad = V.indicators.filter((x) => !same(indicators(x.records), x.out)).map((x) => JSON.stringify(x.records).slice(0, 200));
check(`${V.indicators.length} حساب للمؤشرات الأربعة يطابق المرجع`, bad.length === 0, bad);

// 3) مصدر البنود من محتوى الشريحة
bad = [];
let none = 0, sameFact = 0;
for (const p of V.picks) {
  const [allow, skill, w] = p.inp;
  const [err, it] = thrown(() => new ContentSource(ITEMS, allow).pick(skill, w));
  if (err !== Boolean(p.error)) bad.push('رفض مختلف: ' + JSON.stringify(p.inp));
  else if (!err && ((it ? it.id : null) !== p.id || Boolean(it && it.reshown_same_fact) !== p.same)) {
    bad.push(`بند مختلف: ${JSON.stringify(p.inp)} → ${it && it.id}، والمرجع ${p.id}`);
  }
  if (!err && !it) none += 1;
  if (p.same) sameFact += 1;
}
check(`${V.picks.length} طلب بند من محتوى الشريحة (${ITEMS.length} بندًا): البند المختار هو بند المرجع. منها ${none} لا بند لها، `
  + `و${sameFact} تعيد الحقيقة نفسها`, bad.length === 0, bad);

// 4) الأنشطة: كل خطوة ومخرجها وبصمة الحالة بعدها
bad = [];
const n = { want: 0, feed: 0, unavailable: 0, events: 0, start_event: 0, state: 0, restore: 0, refused: 0 };
const ends = {};
for (const [ti, t] of V.activities.entries()) {
  if (bad.length >= 5) break;
  let a;
  if (t.restore) { a = Activity.fromDict(t.restore); n.restore += 1; } else a = new CLASSES[t.cls](t.opts);
  for (const [oi, o] of t.ops.entries()) {
    const where = `النشاط ${ti} (${t.cls})، الخطوة ${oi} (${o.op})`;
    n[o.op] += 1;
    if (o.op === 'state') { a = Activity.fromDict(o.state); continue; }
    const call = { want: () => a.want(), feed: () => a.feed(o.arg), unavailable: () => a.unavailable(),
      events: () => a.events(), start_event: () => a.startEvent() }[o.op];
    const [err, out] = thrown(call);
    if (err !== Boolean(o.error)) { bad.push(`${where}: رفض مختلف`); break; }
    if (err) n.refused += 1;
    if (!err && (o.op === 'want' || o.op === 'events' || o.op === 'start_event') && !same(out, o.out)) {
      bad.push(`${where}: ${JSON.stringify(out)} والمرجع ${JSON.stringify(o.out)}`);
      break;
    }
    if (digest(a) !== o.h) { bad.push(`${where}: حالة النشاط تخالف المرجع: ${JSON.stringify(a.toDict())}`); break; }
    if (o.op === 'events') {
      const k = `${t.cls}:${a.done ? (a.result === 'held' ? 'held/' + a.hold : a.result) : 'لم ينتهِ'}`;
      ends[k] = (ends[k] || 0) + 1;
    }
  }
}
check(`${V.activities.length} نشاطًا: ${n.want} طلب بند و${n.feed} نتيجة بند و${n.unavailable} «لا بند» (${n.refused} منها `
  + `مرفوضة في نشاط لا بدائل له) و${n.events + n.start_event} طلب أحداث. منها ${n.restore} نشاطًا استؤنف من نص محفوظ في `
  + 'منتصفه. المخرج وحالة النشاط يطابقان المرجع بعد كل خطوة', bad.length === 0, bad);
const expected = ['GateRun:pass', 'GateRun:fail', 'GateRun:help', 'GateRun:interrupted', 'ShortCheckRun:true',
  'ShortCheckRun:false', 'ShortCheckRun:null', 'OpeningRun:skip', 'OpeningRun:full_error', 'OpeningRun:full_help',
  'EvidenceRun:proven', 'EvidenceRun:not_proven', 'EvidenceRun:no_items', 'CheckRun:pass', 'CheckRun:fail',
  'CheckRun:help', 'CheckRun:held/interruptions', 'CheckRun:held/no_alternate', 'CheckRun:held/no_items',
  'RetentionRun:done', 'RetentionRun:null'];
const lacking = expected.filter((k) => !ends[k]);
check(`كل نهاية لكل نشاط مرّت في المتجهات: ${expected.length} نهاية` + (lacking.length ? '. ينقص ' + lacking.join(' ') : ''),
  lacking.length === 0);

// 5) التشغيل الكامل: البنود وأحداثها الخام كما جرت في مسارات المرجع، ومعها سقف الوقت
bad = [];
let paused = 0, recs = 0;
for (const [di, d] of V.drives.entries()) {
  if (bad.length >= 5) break;
  const a = Activity.fromDict(d.start);
  const steps = [...d.steps], pauses = [...d.pauses], mine = [];
  let cur = null, drift = false;
  const source = (skill, w) => {
    cur = steps.shift();
    if (!cur || !same(w, cur.w)) { drift = true; return null; }
    return cur.item;
  };
  const answer = () => cur.got;
  const [err] = thrown(() => drive(a, source, answer, mine, d.paused ? () => pauses.shift() : null));
  const ev = a.done ? a.events() : null;
  if (err || drift || steps.length || !same(a.toDict(), d.end) || !same(mine, d.records) || !same(ev, d.events)) {
    bad.push(`التشغيل ${di} (${d.start._class} ${d.start.skill}): يخالف المرجع`);
  }
  if (!a.done) paused += 1;
  recs += mine.length;
}
check(`${V.drives.length} تشغيلًا كاملًا من مسارات المرجع بمحتوى الشريحة: الطلبات بترتيبها، وسجلات البنود (${recs})، `
  + `وحالة النشاط في آخره، وأحداث المحرك الناتجة تطابق المرجع. منها ${paused} قطعها سقف الوقت قبل أن تنتهي`,
  bad.length === 0, bad);

// 6) الطبقتان معًا في التطبيق: بوابة تُعرض بنودها من المحتوى، ونتيجتها حدث يقبله محرك التطبيق
{
  const e = new Engine();
  const skill = '3-5-1', types = ['ف1', 'ف2', 'ف3'];
  e.apply({ id: 'e1', type: 'session_start', session: 'S1', kind: 'search', day: 0 });
  const pre = e.preflight({ id: 'ask', type: 'gate_result', session: 'S1', skill, result: 'pass' });
  const src = new ContentSource(ITEMS);
  const records = [];
  const a = drive(new CLASSES.GateRun({ skill, types }), (s, w) => src.pick(s, w),
    (item) => [[['confirm', item.answer]], item.answer, true], records);
  const [ev] = a.events();
  const res = e.apply({ ...ev, id: 'e2', session: 'S1', items: records.map((r) => r.item) });
  check('في التطبيق: بوابة 3-5-1 تُعرض بنودها التسعة من المحتوى، وكل جواب صحيح، فينتج حدث gate_result يقبله محرك '
    + 'التطبيق، وتصير المهارة معفاة ودليلها يحمل بنوده',
    pre.ok && a.result === 'pass' && records.length === 9 && new Set(src.served).size === 9 && res.ok
    && e.derive()[skill] === 'exempt' && e.s.evidence[0].items.length === 9);
}

if (!results.every(Boolean)) {
  console.log('أخفق اختبار.');
  process.exit(1);
}
console.log(`نجحت الاختبارات كلها: ${results.length}`);
