// بطاقة «كيف حسبتها؟» وبند المقارنة في درس 3-5-3، من الشاشة في Chrome. المتوقع، مكتوبًا قبل التشغيل:
//  1. بند الخانة 8 في فحص 3-5-3: بعد كتابة الجواب و«تأكيد» تظهر البطاقات الثلاث بنصوصها من المحتوى، ولا يُختم البند.
//  2. اختيار بطاقة يختم البند بالجواب المكتوب، وفي سجله evidence.how بالبطاقة المختارة، ولا تصحيح ولا «التالي».
//  3. المحفوظ بعدها يطابق الإعادة في Node بالأحداث نفسها حرفًا بحرف.
//  4. بند فحص بلا البطاقة (الخانة 9) يُختم بالتأكيد وحده.
// الحالة قبل الخانة 8 تُبنى في Node بوحدات التطبيق (طفل يتعلّم، يومًا بعد يوم)، وتُكتب في IndexedDB كما يكتبها التطبيق.
//
//     node tests/browser/test_how_browser.mjs [مسار Chrome]
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { readFileSync } from 'node:fs';
import { extname, join, normalize, resolve } from 'node:path';
import { chromium } from 'playwright-core';
import { Engine, canonical } from '../../app/engine.mjs';
import { Scheduler } from '../../app/scheduler.mjs';
import { ContentSource } from '../../app/items.mjs';
import { Stepper } from '../../app/stepper.mjs';
import * as persist from '../../app/persist.mjs';
import { spoken } from '../../app/ui/speech.mjs';

const ROOT = resolve(new URL('../..', import.meta.url).pathname);
const CHROME = process.argv[2] || '/usr/bin/google-chrome';
const PACK = JSON.parse(readFileSync(join(ROOT, 'slice-content.json'), 'utf8'));
const IDENT = { version: PACK.version, digest: PACK.digest };
const TYPES = { '3-5-1': ['ف1', 'ف2', 'ف3'], '3-5-2': ['ف1', 'ف2', 'ف3', 'ف4'], '3-5-3': ['ف3'] };
const DAY0 = Date.UTC(2026, 10, 19, 8, 0, 0);
const DAYNUM = Math.floor(Date.UTC(2026, 10, 19) / 86400000);
const results = [];
function check(name, got, want) {
  const ok = canonical(got) === canonical(want);
  results.push(ok);
  console.log(`  ${ok ? 'نجح' : 'أخفق'}  ${results.length}. ${name}`);
  if (!ok) console.log(`        المتوقع ${JSON.stringify(want).slice(0, 600)}\n        الناتج  ${JSON.stringify(got).slice(0, 600)}`);
}

// ---------------------------------------------------------------- الحالة في Node حتى يُطلب بند الخانة 8
let secs = 0;
const src = () => { const s = new ContentSource(PACK.items, true, IDENT); return (k, w) => s.pick(k, w); };
// طفل يتعلّم يمضي يومًا بعد يوم حتى يُطلب بند يحقق stop. يعيد اللقطة قبل عرضه، وطبقة الخطوات واقفة عنده، ويومه
function build(child, stop, untilDay = null) {
  const e = new Engine(undefined, { group: 'older' });
  [['3-5-1', ['3-3-2', '3-2-3']], ['3-5-2', ['3-2-1', '3-3-1', '2-5-2']]].forEach(([skill, bypass], k) =>
    e.apply({ id: 'd' + k, type: 'teacher_open', skill, bypass, reason: 'قرار الشريحة في 10.2' }));
  const sc = new Scheduler(e, TYPES, src(), null, { group: 'older', scope: ['3-5-1', '3-5-2', '3-5-3'], learning: true, cap: 600,
    item_seconds: () => { const x = secs; secs = 0; return x; }, records: [], retention: true, content: IDENT, day_cap: 3000 });
  const known = new Set();
  const events = (item, w) => {
    const a = w.activity;
    if (a === 'lesson' || a === 'practice') { if (a === 'lesson') known.add(item.skill); return [['end']]; }
    const ans = known.has(item.skill) ? item.answer : (item.answer < 99 ? item.answer + 1 : item.answer - 1);
    return [['confirm', ans], ...(['gate', 'short', 'check', 'retention', 'describe'].includes(a) ? [] : [['end']])];
  };
  for (let d = 0; d < 60; d++) {
    const day = DAYNUM + d, now = DAY0 + d * 86400000;
    if (day === untilDay) return { rec: persist.snapshot(e, sc, null, child), day };   // قبل جلسة ذلك اليوم
    sc.today = day;
    const st = new Stepper(e, sc, () => now);
    st.open(sc.g_session());
    while (st.pending !== null) {
      const [item, w] = st.pending;
      if (stop(item)) return { rec: st.snapshot(child), st, day };
      st.show(st.seq);
      for (const ev of events(item, w)) { secs = 10; st.event(st.seq, ev); }
    }
  }
  throw new Error('لم يُطلب البند');
}
const H = build('older1', (it) => Boolean(it.how));
// الفحص الوصفي يُعرض داخل جلسة ولا يُستأنف بعد إعادة فتح: فالحالة تُبنى إلى ما قبل جلسة يومه، والجلسة تبدأ من الشاشة
const D = build('older1', () => false, build('older1', (it) => it.role === 'descriptive_check').day);
const C = build('older2', (it) => it.role === 'lesson.compare');
let { st } = H;
const { rec, day } = H;
const howItem = st.pending[0];

// ---------------------------------------------------------------- الصفحة
const MIME = { '.html': 'text/html; charset=utf-8', '.mjs': 'text/javascript', '.json': 'application/json', '.css': 'text/css' };
const server = createServer(async (rq, rs) => {
  const path = normalize(join(ROOT, decodeURIComponent(new URL(rq.url, 'http://x').pathname)));
  try {
    if (!path.startsWith(ROOT)) throw new Error('خارج المستودع');
    rs.writeHead(200, { 'content-type': MIME[extname(path)] || 'application/octet-stream' }).end(await readFile(path));
  } catch { rs.writeHead(404).end(); }
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const browser = await chromium.launch({ executablePath: CHROME, headless: true });
const context = await browser.newContext({ viewport: { width: 1180, height: 820 }, hasTouch: true });
const errors = [];
const now = DAY0 + (day - DAYNUM) * 86400000;
if (C.day !== H.day) console.log(`  (يوم المقارنة ${C.day - DAYNUM} ويوم البطاقة ${day - DAYNUM}: الساعة تُضبط لكلٍّ قبل فتحه)`);
await context.addInitScript((t) => {
  const T = { spoken: [], clock: { now: t, mono: 0 }, noWorker: true };
  T.now = () => T.clock.now; T.mono = () => T.clock.mono;
  T.speaker = { available: async () => true, say: (x) => T.spoken.push(x) };
  window.MM_TEST = T;
}, now);
const page = await context.newPage();
page.on('pageerror', (x) => errors.push(x.message));
page.on('console', (m) => { if (m.type() === 'error' && !m.text().includes('404')) errors.push(m.text()); });
await page.goto(`http://127.0.0.1:${server.address().port}/app/index.html`);
await page.waitForSelector('[data-screen="who"]');
const putRec = (r) => page.evaluate(async (r) => {
  const s = await import('/app/store.mjs');
  const db = await s.openDB();
  const out = await s.commit(db, r, 0);
  db.close();
  return out;
}, r);
const put = await putRec(rec);
await putRec(C.rec);
const dbRec = (child = 'older1') => page.evaluate(async (c) => {
  const s = await import('/app/store.mjs'); const db = await s.openDB(); const r = await s.load(db, c); db.close(); return r;
}, child);
console.log(`=== بطاقة «كيف حسبتها؟» في Chrome ${browser.version()}`);
await page.click('[data-child="older1"]');
await page.waitForSelector('[data-screen="workshop"]');
await page.click('#start');
await page.waitForSelector('.task[data-ready="true"]');
const shown = await page.getAttribute('.task', 'data-item');
st.show(st.seq);
for (const d of String(howItem.answer)) await page.click(`[data-key="${d}"]`);
await page.click('[data-key="ok"]');
await page.waitForSelector('#how');
const cards = await page.$$eval('#how [data-how]', (b) => b.map((x) => [x.dataset.how, x.textContent]));
const before = await dbRec();
check('بند الخانة 8: بعد «تأكيد» تظهر البطاقات الثلاث بنصوصها من المحتوى، والبند لم يُختم',
  [put.ok, shown, cards, before.current?.journal?.item ?? null, (before.current?.journal?.raw ?? []).length],
  [true, howItem.id, Object.entries(PACK.cards.how).map(([k, c]) => [k, c.ar]), howItem.id, 0]);
await page.evaluate(() => { window.MM_TEST.clock.mono += 10000; });
await page.click('[data-how="up"]');
await page.waitForFunction((id) => document.querySelector('.task')?.dataset.item !== id, howItem.id);
secs = 10;
st.event(st.seq, ['how', 'up']);
secs = 10;
st.event(st.seq, ['confirm', howItem.answer]);
await page.waitForSelector('.task[data-ready="true"]');            // الخانة 9 عُرضت وحُفظت معروضة
st.show(st.seq);
const after = await dbRec();
const mine = after.records.filter((r) => r.item === howItem.id);
const { rev, written_at, ...plain } = after;
check('اختيار بطاقة يختم البند بجوابه، وفي سجله how، والمحفوظ يطابق الإعادة في Node',
  [mine.length, mine[0]?.how, mine[0]?.values, canonical(plain) === canonical(st.snapshot('older1'))],
  [1, 'up', [howItem.answer], true]);
// الخانة التالية بلا بطاقة: «تأكيد» يختمها
const id9 = await page.getAttribute('.task', 'data-item');
const it9 = PACK.items.find((i) => i.id === id9);
for (const d of String(it9.answer)) await page.click(`[data-key="${d}"]`);
await page.click('[data-key="ok"]');
await page.waitForFunction((id) => document.querySelector('.task')?.dataset.item !== id
  || document.getElementById('app').dataset.screen !== 'item', id9);
st.event(st.seq, ['confirm', it9.answer]);
const r9 = (await dbRec()).records.filter((r) => r.item === id9);
check('بند فحص بلا البطاقة يُختم بالتأكيد وحده، وسجله بلا how', [Boolean(it9.how), await page.$('#how'), r9.length, 'how' in (r9[0] ?? {})],
  [false, null, 1, false]);
// ---------------------------------------------------------------- المقارنة في درس 3-5-3
await page.click('#exit').catch(() => {});
await page.goto(page.url());
await page.evaluate((t) => { window.MM_TEST.clock.now = t; }, DAY0 + (C.day - DAYNUM) * 86400000);
await page.waitForSelector('[data-screen="who"]');
await page.click('[data-child="older2"]');
await page.waitForSelector('[data-screen="workshop"]');
await page.click('#start');
await page.waitForSelector('.task[data-ready="true"]');
const cmp = C.st.pending[0];
C.st.show(C.st.seq);
const view = await page.evaluate(() => ({
  id: document.querySelector('.task').dataset.item,
  rows: [...document.querySelectorAll('#model .pair-row')].map((r) => [r.dataset.card, r.querySelector('.pair-name').textContent,
    JSON.parse(r.querySelector('svg.line').dataset.shown)]),
  cards: [...document.querySelectorAll('#cards [data-card]')].map((b) => [b.dataset.card, b.textContent]),
  pad: Boolean(document.querySelector('[data-key="ok"]')), next: Boolean(document.getElementById('next')),
  help: Boolean(document.getElementById('help')) }));
const [A, B] = cmp.model.pair;
check('بند المقارنة في الدرس: الحلان على خطين باسم بطاقتيهما، بقفزات المحتوى ومحطاته كلها، وبطاقات المحتوى الثلاث بدل لوحة الأرقام',
  view, { id: cmp.id, rows: [['A', PACK.cards.compare.A.ar, { stations: [A.start, ...A.stations].map(String), jumps: A.jumps.map((j) => '−' + j) }],
    ['B', PACK.cards.compare.B.ar, { stations: [B.start, ...B.stations].map(String), jumps: B.jumps.map((j) => '+' + j) }]],
  cards: cmp.cards.map((k) => [k, PACK.cards.compare[k].ar]), pad: false, next: false, help: false });
// الإنجليزية بزر الطفل (قرار الأب): النص والصوت والبطاقات من حقول en في المحتوى، والصفحة من اليسار، وتُحفظ لملفه
const langView = () => page.evaluate(() => ({ dir: document.getElementById('app').dir,
  prompt: document.getElementById('prompt').textContent.replace(/\s/g, ''),
  names: [...document.querySelectorAll('.pair-name')].map((x) => x.textContent),
  cards: [...document.querySelectorAll('#cards [data-card]')].map((b) => b.textContent),
  said: window.MM_TEST.spoken.at(-1), button: document.getElementById('lang')?.textContent ?? null }));
// المعادلة تُعرض مقصوصة الأطراف في <bdi>، فالمسافة قبل النقطة تزول: يُقارن النص بلا مسافات، كما في تجربة الشريحة
const plainText = (t) => t.replace(/[⁦-⁩\s]/g, '');
await page.click('#lang');
await page.waitForFunction(() => document.getElementById('app').dir === 'ltr');
const en = await langView();
if (process.env.SHOTS) await page.screenshot({ path: process.env.SHOTS + '/compare-en.png' });
const devEn = await dbRec('@device');
check('زر اللغة: النص والصوت والبطاقات بالإنجليزية من المحتوى، والصفحة من اليسار، واللغة محفوظة لملف الطفل',
  [en, devEn.lang], [{ dir: 'ltr', prompt: plainText(cmp.text_en), names: [PACK.cards.compare.A.en, PACK.cards.compare.B.en],
    cards: cmp.cards.map((k) => PACK.cards.compare[k].en), said: spoken(cmp.audio_en, 'en'), button: 'عربي' }, { older2: 'en' }]);
await page.click('#lang');
await page.waitForFunction(() => document.getElementById('app').dir === 'rtl');
const ar = await langView();
check('والعودة إلى العربية', [ar.dir, ar.prompt, ar.said, ar.button],
  ['rtl', plainText(cmp.text_ar), spoken(cmp.audio_ar, 'ar'), 'English']);
const wrongCard = cmp.cards.find((k) => k !== cmp.answer);
await page.click(`#cards [data-card="${wrongCard}"]`);          // لا [data-card] وحده: صفّا الرسم يحملانه أيضًا
await page.waitForSelector('#next');
const shownAnswer = await page.evaluate(() => [...document.querySelectorAll('#cards button.right')].map((b) => b.dataset.card));
const said = await page.evaluate(() => window.MM_TEST.spoken.at(-1));
await page.click('#next');
await page.waitForFunction((id) => document.querySelector('.task')?.dataset.item !== id, cmp.id);
C.st.event(C.st.seq, ['end']);
await page.waitForSelector('.task[data-ready="true"]');
C.st.show(C.st.seq);
const after2 = await dbRec('older2');
const { rev: r2, written_at: w2, ...plain2 } = after2;
check('اختيار بطاقة يعرض الجواب بعلامته ويقوله، ثم «التالي». والمحفوظ يطابق الإعادة في Node (بند عرض بلا سجل)',
  [shownAnswer, said, canonical(plain2) === canonical(C.st.snapshot('older2'))],
  [[cmp.answer], PACK.cards.compare[cmp.answer].ar, true]);
if (process.env.SHOTS) await page.screenshot({ path: process.env.SHOTS + '/compare.png' });
// ---------------------------------------------------------------- اللوحة (قرار الأب)
// المتوقع من سجل الإعادة في Node مباشرة: لكل مهارة عدد سجلات بنودها غير المستبعدة، وطلبات المساعدة، واختيار البطاقة
await page.goto(page.url());
await page.waitForSelector('[data-screen="who"]');
await page.click('#adult');
await page.fill('#pin', '2468');
await page.fill('#pin2', '2468');
await page.click('#pin-ok');
await page.waitForSelector('#board[data-ready="true"]');
if (st.pending !== null) st.show(st.seq);   // الخانة 10 عُرضت قبل إعادة الفتح
const board = await page.evaluate(() => [...document.querySelectorAll('#board .board-child')].map((c) => [c.dataset.child,
  [...c.querySelectorAll('tr[data-skill]')].map((r) => [r.dataset.skill, r.dataset.state, ...[...r.cells].slice(4, 8).map((x) => x.textContent)])]));
// اللوحة تقرأ الملف كما يُفتح: البند المعروض بلا إجابة يُختم منقطعًا. فالمتوقع من استعادة اللقطة في Node، بعد أن
// يُعرض فيها ما عرضته الشاشة (الخانة 10 للطفل الأول). كتبتُ المتوقع أول مرة من سجلات الإعادة بلا استعادة، فنقص بندًا
const want = (st0, child) => [child, ['3-5-1', '3-5-2', '3-5-3'].map((k) => {
  const r = persist.restore(JSON.parse(JSON.stringify(st0.snapshot(child))), { types: TYPES, source: src(), answer: null,
    item_seconds: () => 0, records: [], today: null, content: IDENT });
  const st = { e: r.engine, sc: r.scheduler };
  const recs = st.sc.records.filter((r) => r.skill === k && !r.void);
  const [status, und] = st.e.progress(k);
  const state = status === 'met' ? 'met' : status === 'stumbled' ? 'stumbled' : status === 'exempt' ? 'exempt' : und ? 'understood' : 'none';
  const how = recs.filter((r) => r.how).length;
  return [k, state, String(recs.length), String(recs.filter((r) => (r.support ?? []).includes('requested')).length),
    how ? `أكمل من الأصغر: ${how}` : '—', '—'];
})];
check('اللوحة: لكل طفل ملفه، ولكل مهارة حالتها وعدد بنودها وطلبات المساعدة واختيار «كيف حسبتها؟»، كما في الإعادة في Node',
  board, [['young', []], want(st, 'older1'), want(C.st, 'older2')]);
// دليل الطريقة (قرار الأب، 25 نوفمبر): لـ3-5-1 و3-5-2 (فيهما ف2) عدد بنود دليل الفهم من ف2 الصحيحة من أول مرة بلا دعم
// وحقيقتها لم تُعرض قبلها، و3-5-3 (بلا ف2) لا عمود. المتوقع من سجلات الإعادة في Node، بالقاعدة مكتوبة هنا
const methodWant = (st0, child) => ['3-5-1', '3-5-2', '3-5-3'].map((k) => {
  if (k === '3-5-3') return '';
  const r = persist.restore(JSON.parse(JSON.stringify(st0.snapshot(child))), { types: TYPES, source: src(), answer: null,
    item_seconds: () => 0, records: [], today: null, content: IDENT });
  return String(r.scheduler.records.filter((x) => x.skill === k && !x.void && x.activity === 'evidence'
    && PACK.items.find((i) => i.id === x.item).evidence === 'ف2' && x.first === true && x.final === 'correct'
    && !(x.support ?? []).length && !PACK.items.find((i) => i.id === x.item).fact_seen_before && !x.fact_just_seen).length);
});
const methodGot = await page.evaluate(() => ['older1', 'older2'].map((c) => [...document.querySelectorAll(
  `#board .board-child[data-child="${c}"] tr[data-skill]`)].map((r) => r.lastChild.dataset.method)));
console.log('        الطريقة: ' + JSON.stringify(methodGot));
check('اللوحة: «استطاع تنفيذ الطريقة عند طلبها» بعدد بنود ف2 في دليل الفهم، منفصلًا عن نتيجة الفحص', methodGot,
  [methodWant(st, 'older1'), methodWant(C.st, 'older2')]);
// ما تحت قرار البداية بلا دليل: سطر «تُخطيت بقرار تحديد نقطة البداية»، والمهارات فيه أسلاف 3-5-1 و3-5-2 في نطاق الملف
// إلا ما له صف. المتوقع من شبكة المحرك ونطاق الملف في إعداد التطبيق
const { PROFILES: PR } = await import('../../app/ui/config.mjs');
const skippedWant = (child, rows) => {
  const e0 = new Engine(undefined, { group: 'older' });
  const below = new Set(['3-5-1', '3-5-2'].flatMap((x) => [...e0.anc[x]]));
  return PR[child].scope.filter((x) => below.has(x) && !rows.includes(x)).join(' ');
};
const skippedGot = await page.evaluate(() => [...document.querySelectorAll('#board .board-child')].map((c) =>
  [c.dataset.child, c.querySelector('.skipped')?.dataset.skipped ?? null]));
const skipLtr = await page.evaluate(() => [...document.querySelectorAll('#board .skipped bdi')].map((b) => {
  const t = b.firstChild;
  const at = (k) => { const r = document.createRange(); r.setStart(t, k); r.setEnd(t, k + 1); return r.getBoundingClientRect().left; };
  return t.length < 2 || at(0) < at(t.length - 1);
}));
check('سطر «تُخطيت»: كل رمز مهارة فيه من اليسار (أول محرف يسار آخره، مقيسًا لا من الصورة)',
  [skipLtr.length > 10, skipLtr.every(Boolean)], [true, true]);
check('اللوحة: ما تحت قرار البداية بلا دليل في سطر «تُخطيت بقرار تحديد نقطة البداية»، لا صفًّا ولا إتقانًا',
  skippedGot, [['young', null], ['older1', skippedWant('older1', board[1][1].map((r) => r[0]))],
    ['older2', skippedWant('older2', board[2][1].map((r) => r[0]))]]);
if (process.env.SHOTS) await page.screenshot({ path: process.env.SHOTS + '/board.png', fullPage: true });

// ---------------------------------------------------------------- الفحص الوصفي (17.27)، في جهاز آخر
// المتوقع: البطاقات بدل لوحة الأرقام، و«أحتاج مساعدة» ظاهر لأنه بند تقييم، والاختيار يختم البند بلا جواب يُعرض.
// يُجاب الثالث خطأً: اللوحة «3 من 4»، والمحفوظ يطابق الإعادة في Node
const ctx2 = await browser.newContext({ viewport: { width: 1180, height: 820 }, hasTouch: true });
await ctx2.addInitScript((t) => {
  const T = { spoken: [], clock: { now: t, mono: 0 }, noWorker: true };
  T.now = () => T.clock.now; T.mono = () => T.clock.mono;
  T.speaker = { available: async () => true, say: (x) => T.spoken.push(x) };
  window.MM_TEST = T;
}, DAY0 + (D.day - DAYNUM) * 86400000);
const p2 = await ctx2.newPage();
p2.on('pageerror', (x) => errors.push(x.message));
await p2.goto(page.url().replace(/#.*$/, ''));
await p2.waitForSelector('[data-screen="who"]');
await p2.evaluate(async (r) => { const s = await import('/app/store.mjs'); const db = await s.openDB(); await s.commit(db, r, 0); db.close(); }, D.rec);
await p2.click('[data-child="older1"]');
await p2.waitForSelector('[data-screen="workshop"]');
await p2.click('#start');
{
  const r = persist.restore(JSON.parse(JSON.stringify(D.rec)), { types: TYPES, source: src(), answer: null,
    item_seconds: () => { const x = secs; secs = 0; return x; }, records: [], today: D.day, content: IDENT });
  r.scheduler.today = D.day;
  D.st = new Stepper(r.engine, r.scheduler, () => DAY0 + (D.day - DAYNUM) * 86400000);
  D.st.open(r.scheduler.g_session());
}
const seenD = [], feedback = [];
for (let k = 0; k < 4; k++) {
  await p2.waitForSelector('.task[data-ready="true"]');
  const [id, kind, cardsD, help, pad] = await p2.evaluate(() => [document.querySelector('.task').dataset.item,
    document.querySelector('.task').dataset.kind, [...document.querySelectorAll('#cards [data-card]')].map((b) => b.dataset.card),
    Boolean(document.getElementById('help')), Boolean(document.querySelector('[data-key="ok"]'))]);
  const it = PACK.items.find((i) => i.id === id);
  seenD.push([id, kind, canonical(cardsD) === canonical(it.cards), help, pad]);
  D.st.show(D.st.seq);
  const pickD = k === 2 ? it.cards.find((c) => c !== it.answer) : it.answer;
  await p2.click(`#cards [data-card="${pickD}"]`);
  feedback.push(await p2.evaluate(() => Boolean(document.querySelector('#cards .right, #next, #ok'))));
  await p2.waitForFunction((x) => document.querySelector('.task')?.dataset.item !== x || document.getElementById('app').dataset.screen !== 'item', id);
  secs = 0;
  D.st.event(D.st.seq, ['confirm', pickD]);
}
const descIds = PACK.items.filter((i) => i.role === 'descriptive_check').map((i) => i.id);
if (await p2.evaluate(() => document.querySelector('.task[data-ready="true"]') !== null) && D.st.pending !== null) D.st.show(D.st.seq);
const recD = await p2.evaluate(async () => { const s = await import('/app/store.mjs'); const db = await s.openDB(); const r = await s.load(db, 'older1'); db.close(); return r; });
const { rev: r3, written_at: w3, ...plain3 } = recD;
check('الفحص الوصفي: البنود الأربعة ببطاقاتها و«أحتاج مساعدة» بلا لوحة أرقام ولا جواب يُعرض، ونتيجتها في السجل، والمحفوظ يطابق الإعادة في Node',
  [seenD, feedback, recD.records.filter((x) => x.activity === 'describe').map((x) => [x.item, x.final]),
    canonical(plain3) === canonical(D.st.snapshot('older1'))],
  [descIds.map((id) => [id, 'assess', true, true, false]), [false, false, false, false],
    descIds.map((id, k) => [id, k === 2 ? 'wrong' : 'correct']), true]);
await p2.goto(page.url().replace(/#.*$/, ''));
await p2.waitForSelector('[data-screen="who"]');
await p2.click('#adult');
await p2.fill('#pin', '1357');
await p2.fill('#pin2', '1357');
await p2.click('#pin-ok');
await p2.waitForSelector('#board[data-ready="true"]');
check('اللوحة تعرض نتيجة الفحص الوصفي', [await p2.evaluate(() => document.querySelector('#board .board-child[data-child="older1"] tr[data-skill="3-5-3"]').cells[7].textContent)],
  ['3 من 4 (وصفي، لا يُشترط لتقدم)']);
await ctx2.close();
const looks = await page.evaluate(() => {
  const b = document.querySelector('#board tr[data-skill="3-5-1"] td bdi'), t = b.firstChild;
  const at = (k) => { const r = document.createRange(); r.setStart(t, k); r.setEnd(t, k + 1); return r.getBoundingClientRect().left; };
  return [b.textContent, at(0) < at(t.length - 1), /[٠-٩]/.test(document.getElementById('board').textContent)];
});
check('اللوحة تُقرأ: رمز المهارة من اليسار (3-5-1 لا 1-5-3)، والأرقام 0-9 لا الهندية في التواريخ', looks, ['3-5-1', true, false]);
// ---------------------------------------------------------------- شاشة اللوح الأفقي القصير (صورة الأب، 19 نوفمبر)
// لوح الأب نحو 923×415 نقطة: كانت لوحة الأرقام تنزل تحت الشاشة فيختفي ✓. المتوقع: كل زر داخل الشاشة، في بند أرقام
// وفي بند بطاقات، وعلى أصغر من ذلك (800×360)
for (const [vw, vh] of [[923, 415], [800, 360]]) {
  const ctx3 = await browser.newContext({ viewport: { width: vw, height: vh }, hasTouch: true });
  await ctx3.addInitScript((t) => {
    window.MM_TEST = { noWorker: true, clock: { now: t, mono: 0 }, speaker: { available: async () => true, say() {} } };
    window.MM_TEST.now = () => window.MM_TEST.clock.now; window.MM_TEST.mono = () => 0;
  }, now);
  const p3 = await ctx3.newPage();
  p3.on('pageerror', (x) => errors.push(x.message));
  await p3.goto(page.url().replace(/#.*$/, ''));
  await p3.waitForSelector('[data-screen="who"]');
  await p3.evaluate(async (r) => { const s = await import('/app/store.mjs'); const db = await s.openDB(); await s.commit(db, r, 0); db.close(); }, H.rec);
  await p3.click('[data-child="older1"]');
  await p3.click('#start');
  await p3.waitForSelector('.task[data-ready="true"]');
  const outside = await p3.evaluate(() => [...document.querySelectorAll('button')].filter((x) => {
    const r = x.getBoundingClientRect(); return r.bottom > innerHeight + 1 || r.right > innerWidth + 1 || r.top < 0 || r.left < 0;
  }).map((x) => x.dataset.key || x.id));
  check(`شاشة ${vw}×${vh}: كل أزرار البند داخل الشاشة، ومنها ✓`, [outside, await p3.$('[data-key="ok"]') !== null], [[], true]);
  await ctx3.close();
}
check('لا خطأ في الصفحة', errors, []);
await browser.close();
server.close();
const ok = results.filter(Boolean).length;
console.log(`\nالنتيجة: نجح ${ok} من ${results.length}`);
process.exit(ok === results.length ? 0 : 1);
