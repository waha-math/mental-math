// فحص الاستقلال المعلّق من الشاشة (3.6): «يُعلَّق للمراجعة بسببه ويظهر للمعلم... حتى يتركه المعلم».
//
//     node tests/browser/test_held_browser.mjs [مسار Chrome]
//
// لم يكن في التطبيق ما يُظهر الفحص المعلّق ولا ما يتركه، فيبقى درس المهارة ممنوعًا من محاولة أخرى بلا علامة. هنا يُحضَّر في
// Node طفل صغير بقرار البداية عند 1-4-1، يخطئ في بوابتها ويصيب ما سواها، ومصدر بلا نص الفحص الأول لـ 1-4-1، حتى يُعلَّق
// فحصها «لا بنود لهذه المحاولة». ثم في Chrome. المتوقع مكتوب من القاعدة قبل التشغيل:
//  1. لوحة البالغ: قسم «فحص استقلال ينتظر قرارك»، سطره للمهارة 1-4-1 بسببه، وزر «اترك المحاولة».
//  2. الترك بلا سبب يُرفض برسالة، ولا يتغير السجل.
//  3. الترك بسببه: المحاولة «تُركت» بسببها في السجل، ويختفي القسم.
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { readFileSync } from 'node:fs';
import { extname, join, normalize, resolve } from 'node:path';
import { chromium } from 'playwright-core';
import { Engine, canonical } from '../../app/engine.mjs';
import { Scheduler } from '../../app/scheduler.mjs';
import { ContentSource } from '../../app/items.mjs';
import { Stepper, ASSESS } from '../../app/stepper.mjs';
import { PROFILES, TZ } from '../../app/ui/config.mjs';
import { familyDay } from '../../app/ui/link.mjs';
import { rightOf, wrongOf, type } from './answer_input.mjs';

const ROOT = resolve(new URL('../..', import.meta.url).pathname);
const CHROME = process.argv[2] || '/usr/bin/google-chrome';
const PACK = JSON.parse(readFileSync(join(ROOT, 'slice-content.json'), 'utf8'));
const IDENT = { version: PACK.version, digest: PACK.digest };
const BY = new Map(PACK.items.map((i) => [i.id, i]));
const P = PROFILES.young;
const T = '1-4-1';
const results = [];
function check(name, got, want) {
  const ok = canonical(got) === canonical(want);
  results.push(ok);
  console.log(`  ${ok ? 'نجح' : 'أخفق'}  ${results.length}. ${name}`);
  if (!ok) console.log(`        المتوقع ${JSON.stringify(want).slice(0, 600)}\n        الناتج  ${JSON.stringify(got).slice(0, 600)}`);
}


const DAY0 = Date.UTC(2026, 9, 1, 8);
function prepare() {
  const e = new Engine(undefined, { group: P.group });
  P.decisions.forEach((d, k) => e.apply({ id: 'd' + k, type: 'teacher_open', skill: d.skill, bypass: d.bypass, reason: 'x' }));
  const src = new ContentSource(PACK.items.filter((i) => !(i.skill === T && i.group === 'checkA')), true, IDENT);
  let secs = 0;
  const sc = new Scheduler(e, P.types, (k, w) => src.pick(k, w), null, { group: P.group, scope: P.scope, learning: true,
    cap: P.cap, item_seconds: () => { const x = secs; secs = 0; return x; }, records: [], retention: true, content: IDENT,
    day_cap: P.day_cap });
  for (let d = 0; d < 30; d++) {
    const now = DAY0 + d * 86400000;
    sc.today = familyDay(now, TZ);
    for (let k = 0; k < 8; k++) {
      if (k > 0 && !(sc.cur === null && (sc.start_at === null || sc.more()))) break;
      const st = new Stepper(e, sc, () => now);
      st.open(sc.g_session());
      const done = st.pending === null;
      while (st.pending !== null) {
        const [item, w] = st.pending;
        st.show(st.seq);
        const role = BY.get(item.id).role;
        secs = 10;
        if (role.startsWith('lesson') || role.startsWith('practice')) { st.event(st.seq, ['end']); continue; }
        const wrong = item.skill === T && w.activity === 'gate';
        st.event(st.seq, ['confirm', wrong ? wrongOf(item) : item.cards ? item.answer : rightOf(item)]);
        if (!ASSESS.includes(w.activity)) st.event(st.seq, ['end']);
      }
      const held = Object.values(e.s.checks).find((c) => c.skill === T && c.state === 'held');
      if (held && sc.cur === null) return { rec: st.snapshot('young'), now: now + 3600000, day: d, held };
      if (done) { sc.practiced(null, true); break; }
    }
  }
  throw new Error('لم يُعلَّق فحص ' + T);
}

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
const NOW = { t: 0 };
async function open() {
  const page = await context.newPage();
  page.on('pageerror', (x) => errors.push(x.message));
  await page.addInitScript((t) => {
    const M = { spoken: [], clock: { now: t, mono: 0 }, noWorker: true };
    M.now = () => M.clock.now; M.mono = () => M.clock.mono;
    M.speaker = { available: async () => true, say: (x) => M.spoken.push(x) };
    window.MM_TEST = M;
  }, NOW.t);
  await page.goto(`http://127.0.0.1:${server.address().port}/app/index.html`);
  await page.waitForSelector('[data-screen="who"]');
  return page;
}
const record = (page) => page.evaluate(async () => {
  const s = await import('/app/store.mjs');
  const db = await s.openDB();
  const r = await s.load(db, 'young');
  db.close();
  return r;
});
const checksOf = (r) => Object.values(JSON.parse(r.engine).checks).filter((c) => c.skill === T)
  .map((c) => [c.state, c.hold_reason ?? null, c.reason ?? null]);

const { rec, now, day, held } = prepare();
console.log(`=== الفحص المعلّق من الشاشة، Chrome ${browser.version()}: عُلّق في اليوم ${day + 1} (${held.hold_reason})`);
NOW.t = now;
const page = await open();
await page.evaluate(async (r) => {
  const s = await import('/app/store.mjs');
  const db = await s.openDB();
  await s.commit(db, r, 0);
  db.close();
}, rec);
await page.reload();
await page.waitForSelector('[data-screen="who"]');
await page.click('[data-child="young"]');
await page.waitForSelector('[data-screen="workshop"]');
await page.click('#adult');
await page.fill('#pin', '4821');
if (await page.$('#pin2')) await page.fill('#pin2', '4821');
await page.click('#pin-ok');
await page.waitForSelector('#held');
const line = await page.evaluate(() => [...document.querySelectorAll('#held .held')].map((p) => [p.dataset.reason,
  p.textContent.includes('1-4-1'), !!p.querySelector('[data-abandon]')]));
check('اللوحة: قسم الفحص المعلّق، سطره لـ 1-4-1 بسببه، وزر «اترك المحاولة»', line, [['no_items', true, true]]);
const before = checksOf(await record(page));
await page.click('[data-abandon]');
const msg = await page.evaluate(() => document.querySelector('#adult-msg')?.textContent ?? '');
check('الترك بلا سبب يُرفض برسالة، ولا يتغير السجل', [/السبب مطلوب/.test(msg), checksOf(await record(page))],
  [true, before]);
await page.fill('#abandon-reason', 'نفدت النصوص، أراجع مع المعلم');
await page.click('[data-abandon]');
await page.waitForFunction(() => !document.querySelector('#held'));
check('الترك بسببه: المحاولة «تُركت» بسببها في السجل، واختفى القسم', [checksOf(await record(page)), !!(await page.$('#held'))],
  [[['abandoned', 'no_items', 'نفدت النصوص، أراجع مع المعلم']], false]);
check('لا خطأ في الصفحة', errors, []);
await browser.close();
server.close();
console.log(results.every(Boolean) ? `نجحت الاختبارات كلها: ${results.length}` : `النتيجة: نجح ${results.filter(Boolean).length} من ${results.length}`);
process.exit(results.every(Boolean) ? 0 : 1);
