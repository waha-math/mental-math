// بداية كريم من الشاشة على ملف جديد، في يومين (قرار الأب، 25 نوفمبر).
//
//     node tests/browser/test_start_browser.mjs [مسار Chrome]
//
// المتوقع مكتوب من القرار قبل التشغيل. طفل الاختبار لا يعرف 1-4-1 حتى يرى درسها، ولا يُسأل في غيرها ما دام لم يثبت شيئًا.
//  1. اليوم الأول: البالغ ينشئ الملف بقرار 1-4-1. «ابدأ»: بوابة 1-4-1 وحدها. «تابع»: افتتاح درس 1-4-1 ثم درسها.
//  2. اليوم الثاني: «ابدأ» يواصل 1-4-1، ولا بوابة ولا تحقق قصير لمهارة غيرها.
//  3. اللوحة: ما تحت 1-4-1 في سطر «تُخطيت بقرار تحديد نقطة البداية»، والمهارة الجانبية 1-2-1 في سطر «لم تُفحص بعد»،
//     والسطران منفصلان.
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { readFileSync } from 'node:fs';
import { extname, join, normalize, resolve } from 'node:path';
import { chromium } from 'playwright-core';
import { canonical } from '../../app/engine.mjs';

const ROOT = resolve(new URL('../..', import.meta.url).pathname);
const CHROME = process.argv[2] || '/usr/bin/google-chrome';
const PACK = JSON.parse(readFileSync(join(ROOT, 'slice-content.json'), 'utf8'));
const BY = new Map(PACK.items.map((i) => [i.id, i]));
const DAY0 = Date.UTC(2026, 10, 25, 8, 0, 0);
const results = [];
function check(name, got, want) {
  const ok = canonical(got) === canonical(want);
  results.push(ok);
  console.log(`  ${ok ? 'نجح' : 'أخفق'}  ${results.length}. ${name}`);
  if (!ok) console.log(`        المتوقع ${JSON.stringify(want).slice(0, 600)}\n        الناتج  ${JSON.stringify(got).slice(0, 600)}`);
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
const NOW = { t: DAY0 };
async function open() {
  const page = await context.newPage();
  page.on('pageerror', (x) => errors.push(x.message));
  await page.addInitScript((t) => {
    const T = { spoken: [], clock: { now: t, mono: 0 }, noWorker: true };
    T.now = () => T.clock.now; T.mono = () => T.clock.mono;
    T.speaker = { available: async () => true, say: (x) => T.spoken.push(x) };
    window.MM_TEST = T;
  }, NOW.t);
  await page.goto(`http://127.0.0.1:${server.address().port}/app/index.html`);
  await page.waitForSelector('[data-screen="who"]');
  return page;
}
const scr = (page) => page.evaluate(() => document.getElementById('app').dataset.screen);
const KNOWN = new Set();
const wrongOf = (it) => (it.cards ? it.cards.find((c) => c !== it.answer) : it.answer === 9 ? 8 : it.answer + 1);
const type = async (page, n) => { for (const d of String(n)) await page.click(`[data-key="${d}"]`); };
// يجيب حتى تنتهي الجلسة. يعيد ما عُرض: [النشاط من دور البند، المهارة]
async function play(page) {
  const seen = [];
  for (;;) {
    await page.waitForFunction(() => {
      const a = document.getElementById('app').dataset.screen, t = document.querySelector('.task');
      return a !== 'workshop' && (a !== 'item' || (t && t.dataset.ready === 'true'));
    });
    if (await scr(page) !== 'item') return seen;
    const [id, kind] = await page.evaluate(() => [document.querySelector('.task').dataset.item, document.querySelector('.task').dataset.kind]);
    const it = BY.get(id);
    seen.push([it.role.split('.')[0].replace('_check', ''), it.skill]);
    await page.evaluate(() => { window.MM_TEST.clock.mono += 10000; });
    if (kind === 'shown') {
      if (it.role.startsWith('lesson')) KNOWN.add(it.skill);
      if (it.cards) { await page.click(`#cards [data-card="${it.answer}"]`); await page.waitForSelector('#next'); }
      else if (it.role !== 'lesson.watch') await type(page, it.answer), await page.click('[data-key="ok"]');
      await page.click('#next');
    } else if (kind === 'assess') {
      const a = KNOWN.has(it.skill) ? it.answer : wrongOf(it);
      if (it.cards) await page.click(`#cards [data-card="${a}"]`);
      else { await type(page, a); await page.click('[data-key="ok"]'); if (it.how) await page.click('#how [data-how="back"]'); }
    } else {
      if (!KNOWN.has(it.skill)) {
        if (it.cards) {
          await page.click(`#cards [data-card="${wrongOf(it)}"]`);
          await page.waitForFunction(() => !document.querySelector('#cards button:disabled'));
        } else {                                               // كما في test_slice_browser: يُقفل الزر ثم يُمسح الجواب
          await type(page, wrongOf(it));
          await page.click('[data-key="ok"]');
          await page.waitForSelector('[data-key="ok"]:disabled');
          await page.waitForFunction(() => document.getElementById('answer').textContent === '');
        }
      }
      if (it.cards) await page.click(`#cards [data-card="${it.answer}"]`);
      else { await type(page, it.answer); await page.click('[data-key="ok"]'); }
      await page.waitForSelector('#next');
      await page.click('#next');
    }
  }
}
const acts = (seen) => seen.map(([a, s]) => `${a} ${s}`).filter((x, k, xs) => x !== xs[k - 1]);

console.log(`=== بداية الصغير من الشاشة في Chrome ${browser.version()}`);
let page = await open();
await page.click('[data-child="young"]');
await page.waitForSelector('[data-screen="call"]');
await page.click('#adult');
await page.fill('#pin', '4821');
await page.fill('#pin2', '4821');
await page.click('#pin-ok');
await page.waitForSelector('[data-screen="adult"]');
await page.fill('#child-name', 'ك');
await page.fill('#decision-reason', 'تحديد نقطة البداية');
await page.click('#dec-0');
await page.click('#setup-ok');
await page.waitForSelector('[data-screen="workshop"]');
await page.click('#start');
const s1 = acts(await play(page));
await page.waitForSelector('#more');
await page.click('#more');
await page.waitForFunction(() => document.getElementById('app').dataset.screen !== 'end');   // بلا هذا يُقرأ الختام قبل الجلسة
const s2 = acts(await play(page));
check('اليوم الأول: «ابدأ» بوابة 1-4-1 وحدها، و«تابع» افتتاح درسها ثم درسها، بلا تحقق قصير قبله',
  [s1, s2.slice(0, 2)], [['gate 1-4-1'], ['opening 1-4-1', 'lesson 1-4-1']]);
console.log(`        ${s1.join(' ← ')}  ||  ${s2.join(' ← ')}`);
await page.close();

NOW.t = DAY0 + 86400000;
page = await open();
await page.click('[data-child="young"]');
await page.waitForSelector('[data-screen="workshop"]');
await page.click('#start');
const d2 = acts(await play(page));
check('اليوم الثاني: «ابدأ» يواصل 1-4-1، ولا بوابة ولا تحقق قصير لمهارة غيرها',
  [d2[0]?.endsWith(' 1-4-1'), d2.filter((x) => /^(gate|short) /.test(x) && !x.endsWith(' 1-4-1'))], [true, []]);
console.log(`        ${d2.join(' ← ')}`);
await page.click('#exit').catch(() => {});
await page.waitForSelector('[data-screen="who"]').catch(() => {});

await page.click('#adult');
await page.fill('#pin', '4821');
await page.click('#pin-ok');
await page.waitForSelector('#board[data-ready="true"]');
const board = await page.evaluate(() => {
  const c = document.querySelector('#board .board-child[data-child="young"]');
  return [c.querySelector('.skipped')?.dataset.skipped.split(' ') ?? [], c.querySelector('.untested')?.dataset.untested.split(' ') ?? []];
});
check('اللوحة: ما تحت 1-4-1 «تُخطيت بقرار تحديد نقطة البداية»، و1-2-1 «لم تُفحص بعد»، في سطرين منفصلين',
  [board[0].includes('1-3-3') && board[0].includes('1-1-1'), board[1].includes('1-2-1'), board[0].includes('1-2-1'),
    board[1].includes('1-3-3')], [true, true, false, false]);
check('لا خطأ في الصفحة', errors, []);
await browser.close();
server.close();
console.log(results.every(Boolean) ? `نجحت الاختبارات كلها: ${results.length}` : `النتيجة: نجح ${results.filter(Boolean).length} من ${results.length}`);
process.exit(results.every(Boolean) ? 0 : 1);
