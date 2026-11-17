// حالات المراجعة الرابعة عشرة على التطبيق بلغة JavaScript: سجل محاولات البنود في اللقطة، وتسوية قرار المعلم.
//
//     node tests/test_r14.mjs [مجلد app]
//
// الحالات والنتائج المتوقعة نفسها في tests/test_r14.py، مكتوبة يدويًا. الملاحظة الثالثة (Saver) في اختبار المتصفح.
// المجلد الاختياري يشغّلها على نسخة أخرى من التطبيق (مثلًا الالتزام 11419f8).
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

function reopen(rec) {
  const src = new ContentSource(ITEMS), child = new Child(['1-4-1']);
  return persist.restore(JSON.parse(JSON.stringify(rec)), { types: TYPES, source: (s, w) => src.pick(s, w),
    answer: (i, w) => child.call(i, w), item_seconds: secs, records: [], today: 10 ** 6 });
}

function crafted() {
  return [[[['confirm', 6]], 7, true],
    [[['confirm', 6], ['support', 'hint'], ['confirm', 7], ['end']], 7, false],
    [[['support', 'extra_model'], ['interrupt']], 7, false],
    [[['support', 'someone'], ['confirm', 7], ['end']], 7, false]]
    .map(([raw, ans, assess]) => ({ ...foldItem(raw, ans, assess), skill: '1-4-1', activity: 'evidence', role: 'evidence',
      item: 'x' }));
}

function case01a() {
  const { e, sc } = setup();
  sc.records.push(...crafted());
  const before = structuredClone(sc.records);
  const r2 = reopen(persist.snapshot(e, sc));
  const r3 = reopen(persist.snapshot(r2.engine, r2.scheduler));
  const bad = [];
  const wrong = before.filter((r) => r.first === false).length;
  const sup = before.filter((r) => r.support_before.length && r.final === 'correct').length;
  const cut = before.filter((r) => r.status === 'interrupted' && r.support_before.length).length;
  if (!(wrong && sup && cut)) bad.push('الإعداد لا يحمل الأنواع المطلوبة');
  for (const [label, recs] of [['بعد الاستعادة', r2.scheduler.records], ['بعد الحفظ والاستعادة مرة ثانية', r3.scheduler.records]]) {
    if (!same(recs, before)) bad.push(`${label}: ${(recs || []).length} سجل بند، والمتوقع ${before.length} كما قبل الحفظ`);
    else if (!same(indicators(recs), indicators(before))) bad.push(`${label}: المؤشرات تغيّرت`);
  }
  return bad;
}

function case01b() {
  const { e, sc } = setup();
  sc.begin('follow');
  sc.send({ type: 'check_resumed', skill: '1-4-1', check_id: '1-4-1/check/1' });
  const act = sc.take('check', '1-4-1');
  const items = [...sc.carried_items];
  const src = new ContentSource(ITEMS);
  const w = act.want();
  const it = src.pick('1-4-1', w);
  const before = structuredClone(sc.records);
  const cur = { kind: 'check', skill: '1-4-1', act: act.toDict(), items,
    journal: { item: it.id, want: w, answer: it.answer, assess: true, raw: [['support', 'hint']] } };
  const r2 = reopen(persist.snapshot(e, sc, cur));
  const first = structuredClone(r2.scheduler.records);
  const r3 = reopen(persist.snapshot(r2.engine, r2.scheduler));
  const bad = [];
  if (first.length !== before.length + 1 || !same(first.slice(0, -1), before)) {
    bad.push(`الاستعادة الأولى: ${first.length} سجل، والمتوقع ما قبل الإغلاق (${before.length}) وسجل البند الجاري`);
  } else {
    const u = first[first.length - 1];
    if (!(u.unsettled && u.status === 'interrupted' && same(u.support_before, ['hint']) && u.item === it.id)) {
      bad.push('سجل البند غير المحسوم ليس كما يُتوقع');
    }
  }
  if (!same(r3.scheduler.records, first)) {
    bad.push(`الاستعادة الثانية: ${(r3.scheduler.records || []).length} سجل، والمتوقع ${first.length} بلا فقد ولا تكرار`);
  }
  if (r3.notes.length) bad.push('الاستعادة الثانية أعادت معالجة');
  return bad;
}

function case02a(extra = false) {
  const { e, sc } = setup();
  const cid = '1-4-1/check/1';
  let other = null;
  if (extra) {
    const ret = new RetentionRun({ skill: '1-4-1', round: 1 });
    ret.shown.retention = 1;
    other = { kind: 'retention', skill: '1-4-1', act: ret.toDict(), items: ['1-4-1/deferred/01'] };
    sc.saved.push(other);
  }
  const r = e.apply({ id: 't1', type: 'check_abandoned', check_id: cid, reason: 'قرار المعلم' });
  if (!r.ok) return [`الإعداد: رُفض ترك المحاولة (${r.code})`];
  let back;
  try { back = reopen(persist.snapshot(e, sc)); } catch (x) { return [`رُفض السجل: ${x.message}`]; }
  const bad = [];
  if (!same(back.scheduler.saved, extra ? [other] : [])) bad.push('المخزن بعد الاستعادة ليس كما يُتوقع');
  const last = back.scheduler.log[back.scheduler.log.length - 1];
  if (!same(last, [3, 'carry_dropped:check_abandoned', '1-4-1'])
    || !back.notes.some((n) => same(n, ['reconciled', cid, 'check_abandoned']))) {
    bad.push('لم تُكتب التسوية في سجل المجدول والملاحظات');
  }
  if (back.engine.s.checks[cid].state !== 'abandoned') bad.push('المحاولة في المحرك ليست متروكة');
  if (!extra) {
    back.scheduler.follow_learning();
    const started = back.engine.s.log.filter((x) => x.type === 'check_started').map((x) => x.check_id);
    if (!same(started, [cid, '1-4-1/check/2'])) bad.push(`الجلسة التالية: محاولات ${canonical(started)}`);
  }
  return bad;
}

function case02b() {
  const { e, sc } = setup();
  const cid = '1-4-1/check/1';
  const r = e.apply({ id: 't1', type: 'invalidate_session', target: 'S3' });
  if (!r.ok || e.s.checks[cid].state !== 'needs_restart') return ['الإعداد: إبطال S3 لم يجعل المحاولة تحتاج إعادة بدء'];
  let back;
  try { back = reopen(persist.snapshot(e, sc)); } catch (x) { return [`رُفض السجل: ${x.message}`]; }
  back.scheduler.follow_learning();
  const bad = [];
  const dropped = back.scheduler.log.filter((x) => x[1].startsWith('carry_dropped')).map((x) => x[1]);
  if (!same(dropped, ['carry_dropped:check_state'])) bad.push('النشاط المحفوظ لم يُسقط عند استئنافه');
  if (back.engine.s.checks[cid].state !== 'needs_restart' || back.scheduler.saved.length) bad.push('الحالة بعد الجلسة التالية');
  if (back.engine.s.log.some((x) => x.type === 'check_started' && x.check_id !== cid)) bad.push('بدأت محاولة جديدة قبل الترك');
  return bad;
}

// النشاط الجاري نفسه (لا المحفوظ) هو المحاولة التي تركها المعلم قبل الحفظ
function case02e() {
  const { e, sc } = setup();
  const cid = '1-4-1/check/1';
  sc.begin('follow');
  sc.send({ type: 'check_resumed', skill: '1-4-1', check_id: cid });
  const act = sc.take('check', '1-4-1');
  const items = [...sc.carried_items];
  const w = act.want();
  const it = new ContentSource(ITEMS).pick('1-4-1', w);
  const cur = { kind: 'check', skill: '1-4-1', act: act.toDict(), items,
    journal: { item: it.id, want: w, answer: it.answer, assess: true, raw: [] } };
  e.apply({ id: 't1', type: 'check_abandoned', check_id: cid, reason: 'قرار المعلم' });
  let r2, r3;
  try {
    r2 = reopen(persist.snapshot(e, sc, cur));
    r3 = reopen(persist.snapshot(r2.engine, r2.scheduler));
  } catch (x) { return [`رُفض السجل: ${x.message}`]; }
  const bad = [];
  // R17-01: المحاولة تُركت قبل الاستعادة، فبندها الجاري تاريخ مستبعد (void_item) لا يُعطى للنشاط ولا يدخل العدّاد.
  // قبل R17-01 كان يُختم «غير محسوم» ويُعطى للنشاط المتروك ثم يُسوّى
  if (!same(r2.notes.map((n) => n[0]), ['void_item', 'current_saved', 'reconciled', 'session_closed'])
    || r2.scheduler.saved.length) bad.push('الاستعادة الأولى ليست كما يُتوقع');
  if (r3.notes.length || !same(persist.snapshot(r3.engine, r3.scheduler), persist.snapshot(r2.engine, r2.scheduler))) {
    bad.push('الاستعادة الثانية غيّرت اللقطة');
  }
  return bad;
}

function case02d() {
  const { e, sc } = setup();
  const cid = '1-4-1/check/1';
  const rec = JSON.parse(JSON.stringify(persist.snapshot(e, sc)));
  const out = [];
  for (const state of ['abandoned', 'closed']) {
    const r = structuredClone(rec);
    const eng = JSON.parse(r.engine);
    eng.checks[cid].state = state;
    r.engine = canonical(eng);
    try {
      reopen(r);
      out.push(`سجل فيه محاولة ${state} بلا حدث يفسّرها قُبل`);
    } catch (x) {
      if (!(x instanceof persist.Inconsistent)) out.push(`استثناء غير متوقع: ${x.message}`);
    }
  }
  return out;
}

const CASES = [
  ['R14-01-a', true, 'سجل محاولات البنود في اللقطة: إجابة خاطئة، ونجاح بمساعدة، وانقطاع بعد طلب دعم. السجلات والمؤشرات '
    + 'بعد الاستعادة، وبعد حفظ المستعادة واستعادتها، هي نفسها قبل الحفظ', case01a],
  ['R14-01-b', true, 'بند «غير محسوم» بعد طلب دعم: يُنشأ سجله في الاستعادة الأولى، ويبقى في الثانية مرة واحدة، ولا تُعاد '
    + 'معالجته', case01b],
  ['R14-02-a', true, 'المعلم ترك المحاولة المحفوظة ثم حُفظ فورًا: الاستعادة تُسقط النشاط المتروك وتكتب إسقاطه، والمحاولة '
    + 'متروكة في المحرك، والجلسة التالية تبدأ المحاولة الثانية', () => case02a()],
  ['R14-02-b', false, 'إبطال جلسة أسهمت في المحاولة المحفوظة ثم الحفظ: يُستعاد السجل، ويُسقط النشاط عند استئنافه، ولا '
    + 'تبدأ محاولة جديدة قبل ترك المعلم', case02b],
  ['R14-02-c', false, 'الترك لا يمسّ نشاطًا محفوظًا آخر: فحص احتفاظ محفوظ يبقى كما هو', () => case02a(true)],
  ['R14-02-e', false, 'النشاط الجاري نفسه هو المحاولة التي تركها المعلم قبل الحفظ: يُضم إلى المخزن ثم يُسوّى في '
    + 'الاستعادة الأولى، والاستعادة الثانية لا تغيّر اللقطة', case02e],
  ['R14-02-d', false, 'سجل فيه محاولة متروكة أو مختومة لا يفسّرها حدث في سجل المحرك يبقى مرفوضًا', case02d],
];

console.log(`=== حالات المراجعة الرابعة عشرة، بلغة JavaScript، على التطبيق في ${appDir}`);
for (const [id, rep, title, fn] of CASES) {
  let bad;
  try { bad = fn(); } catch (x) { bad = ['استثناء: ' + x]; }
  results.push(!bad.length);
  console.log(`  ${bad.length ? 'أخفق' : 'نجح'}  ${id} ${title}${rep ? ' [أعاد المراجع إنتاجه]' : ''}`);
  for (const b of bad.slice(0, 3)) console.log('        ' + b);
}
console.log(`النتيجة: نجح ${results.filter(Boolean).length} من ${results.length}`);
process.exit(results.every(Boolean) ? 0 : 1);
