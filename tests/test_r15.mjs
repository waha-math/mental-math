// حالات المراجعة الخامسة عشرة على التطبيق بلغة JavaScript: الاستعادة المرفوضة لا تغيّر بيانات المستدعي.
//
//     node tests/test_r15.mjs [مجلد app]
//
// الحالات والنتائج المتوقعة نفسها في tests/test_r15.py، مكتوبة يدويًا.
// المجلد الاختياري يشغّلها على نسخة أخرى من التطبيق (مثلًا الالتزام a0c363e).
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const here = new URL('.', import.meta.url);
const appDir = resolve(process.argv[2] || new URL('../app', here).pathname);
const load = (f) => import(pathToFileURL(resolve(appDir, f)).href);
const { Engine, canonical } = await load('engine.mjs');
const { Scheduler } = await load('scheduler.mjs');
const { ContentSource, foldItem, indicators, RetentionRun } = await load('items.mjs');
const persist = await load('persist.mjs');
const ITEMS = JSON.parse(readFileSync(new URL('../slice-content.json', here), 'utf8')).items;
const TYPES = { '1-4-1': ['ف1', 'ف3'] };
const same = (a, b) => canonical(a ?? null) === canonical(b ?? null);
const results = [];
const secs = (w) => (w.activity === 'check' ? 60 : 0);

class Child {
  constructor(known = []) { this.known = new Set(known); }
  call(item, want) {
    const a = want.activity;
    if (a === 'lesson' || a === 'practice') {
      if (a === 'lesson') this.known.add(item.skill);
      return 'correct';
    }
    const assess = ['gate', 'short', 'check', 'retention'].includes(a);
    const ans = this.known.has(item.skill) ? item.answer : item.answer + 1;
    return [[['confirm', ans], ...(assess ? [] : [['end']])], item.answer, assess];
  }
}

function setup() {
  const e = new Engine(undefined, { group: 'young' });
  e.apply({ id: 'd0', type: 'teacher_open', skill: '1-4-1', bypass: ['1-3-3'], reason: 'قرار الشريحة' });
  const src = new ContentSource(ITEMS), child = new Child();
  const sc = new Scheduler(e, TYPES, (s, w) => src.pick(s, w), (i, w) => child.call(i, w), {
    group: 'young', scope: ['1-4-1'], learning: true, cap: 240, item_seconds: secs, records: [] });
  sc.search();
  sc.start_session();
  sc.follow_learning();
  return { e, sc };
}

const dump = (x) => canonical(x ?? null);

function live() {
  const { e, sc } = setup();
  sc.begin('follow');
  sc.send({ type: 'check_resumed', skill: '1-4-1', check_id: '1-4-1/check/1' });
  const act = sc.take('check', '1-4-1');
  const items = [...sc.carried_items];
  const w = act.want();
  const it = new ContentSource(ITEMS).pick('1-4-1', w);
  const cur = { kind: 'check', skill: '1-4-1', act: act.toDict(), items,
    journal: { item: it.id, want: w, answer: it.answer, assess: true, raw: [['support', 'hint']] } };
  return { e, sc, cur };
}

function openInto(rec, arr) {
  const src = new ContentSource(ITEMS), child = new Child(['1-4-1']);
  return persist.restore(rec, { types: TYPES, source: (s, w) => src.pick(s, w), answer: (i, w) => child.call(i, w),
    item_seconds: secs, records: arr, today: 10 ** 6 });   // يوم جديد يختم الجلسة المفتوحة (المرحلة 0ج)
}

function refused(mutate, label, anyError = false) {
  const { e, sc, cur } = live();
  const rec = JSON.parse(JSON.stringify(persist.snapshot(e, sc, cur)));
  mutate(rec);
  const arr = sc.records;
  const before = dump(arr), recBefore = dump(rec);
  if (arr.length !== 13) return [`الإعداد: ${arr.length} سجل بند، والمتوقع 13`];
  const bad = [];
  try {
    openInto(rec, arr);
    bad.push(`${label}: قُبل السجل، والمتوقع الرفض`);
  } catch (x) {
    if (!anyError && !(x instanceof persist.Inconsistent)) bad.push(`${label}: استثناء غير متوقع ${x}`);
  }
  if (arr !== sc.records || dump(arr) !== before) {
    bad.push(`${label}: سجلات الطفل الحالية صارت ${arr.length} بعد الرفض، والمتوقع 13 كما كانت حرفًا بحرف`);
  }
  if (dump(rec) !== recBefore) bad.push(`${label}: تغيّر السجل الممرَّر للاستعادة`);
  return bad;
}

const sessionsOff = (rec) => { rec.scheduler.state.sessions += 1; rec.records = []; };
const unexplained = (rec) => {
  const eng = JSON.parse(rec.engine);
  eng.checks['1-4-1/check/1'].state = 'closed';
  rec.engine = canonical(eng);
};
const noRecords = (rec) => { rec.records = null; unexplained(rec); };
const brokenCurrent = (rec) => { delete rec.current.act.check_id; };

function caseD() {
  const { e, sc, cur } = live();
  const before = structuredClone(sc.records);
  const rec = JSON.parse(JSON.stringify(persist.snapshot(e, sc, cur)));
  const arr = ['قديم'];
  const r2 = openInto(rec, arr);
  const bad = [];
  if (r2.scheduler.records !== arr) bad.push('مصفوفة المستدعي ليست مصفوفة المجدول المستعاد');
  if (arr.length !== 14 || dump(arr.slice(0, 13)) !== dump(before) || !arr[13].unsettled) {
    bad.push(`بعد الاستعادة: ${arr.length} سجل، والمتوقع 13 كما حُفظت وسجل البند غير المحسوم`);
  }
  const arr2 = [];
  const r3 = openInto(JSON.parse(JSON.stringify(persist.snapshot(r2.engine, r2.scheduler))), arr2);
  if (dump(arr2) !== dump(arr) || r3.notes.length) {
    bad.push(`الحفظ والاستعادة ثانية: ${arr2.length} سجل، والمتوقع ${arr.length} بلا فقد ولا تكرار`);
  }
  return bad;
}

const CASES = [
  ['R15-01-a', true, 'استعادة مرفوضة لاختلاف عدد الجلسات وسجلاتها فارغة: سجلات الطفل الحالية الـ13 تبقى حرفًا بحرف، '
    + 'والسجل الممرَّر لا يتغير', () => [...refused(sessionsOff, 'عدد الجلسات'),
    ...refused((r) => { sessionsOff(r); r.current = null; }, 'عدد الجلسات بلا نشاط جارٍ كما أعاده المراجع')]],
  ['R15-01-b', false, 'رفض لمحاولة غير مفسَّرة والبند الجاري عليه دعم، بسجلات في اللقطة وبدونها: الضمان نفسه',
    () => [...refused(unexplained, 'محاولة غير مفسَّرة'), ...refused(noRecords, 'سجل بلا records')]],
  ['R15-01-c', false, 'نشاط جارٍ تالف يرمي استثناءً: الضمان نفسه', () => refused(brokenCurrent, 'نشاط جارٍ تالف', true)],
  ['R15-01-d', false, 'استعادة ناجحة: تُنقل السجلات إلى مصفوفة المستدعي بهويتها ويُضاف البند غير المحسوم مرة واحدة، '
    + 'وحفظها واستعادتها لا يفقد ولا يكرر', caseD],
];

console.log(`=== حالات المراجعة الخامسة عشرة، بلغة JavaScript، على التطبيق في ${appDir}`);
for (const [id, rep, title, fn] of CASES) {
  let bad;
  try { bad = fn(); } catch (x) { bad = ['استثناء: ' + x]; }
  results.push(!bad.length);
  console.log(`  ${bad.length ? 'أخفق' : 'نجح'}  ${id} ${title}${rep ? ' [أعاد المراجع إنتاجه]' : ''}`);
  for (const b of bad.slice(0, 4)) console.log('        ' + b);
}
console.log(`النتيجة: نجح ${results.filter(Boolean).length} من ${results.length}`);
process.exit(results.every(Boolean) ? 0 : 1);
