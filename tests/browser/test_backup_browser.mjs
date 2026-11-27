// النسخة الاحتياطية والعمل دون اتصال في Chrome (9.2)، من الشاشة بالنقر، على IndexedDB الحقيقي وعامل الخدمة الحقيقي.
//
//     node tests/browser/test_backup_browser.mjs [مسار Chrome]
//
// المتوقع مكتوب هنا من القواعد في app/backup.mjs و build_sw.py قبل التشغيل:
//  1. الملف المصدَّر هو سجلات الجهاز كلها كما في IndexedDB، حرفًا بحرف، وبهوية المحتوى الحالي.
//  2. جهاز ثانٍ يستعيده: سجل الطفل فيه هو سجل النسخة إلا rev ووقت الكتابة، ورمز البالغ رمز النسخة لا رمزه.
//  3. بعد الاستعادة يمضي الطفل على الجهازين بالبنود نفسها، ويُحفظ على الجهازين السجل نفسه.
//  4. ملف تالف أو غريب يُرفض بسببه، ولا يتغير في الجهاز شيء.
//  5. التراجع يعيد ما كان على الجهاز قبل الاستيراد.
//  6. نافذة كانت مفتوحة قبل الاستيراد لا تكتب فوقه: تتوقف بـ conflict.
//  7. بعد أول فتح يعمل التطبيق والشبكة مقطوعة: يُفتح، ويُنشأ ملف، ويُجاب بند ويُحفظ، ولا طلب يصل إلى الخادم.
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
const SW_URLS = [...readFileSync(join(ROOT, 'app/sw.js'), 'utf8').matchAll(/^ {2}'([^']+)',$/gm)].map((m) => m[1]);
const NOW = Date.UTC(2026, 10, 19, 8, 0, 0);
const results = [];
function check(name, got, want) {
  const ok = canonical(got) === canonical(want);
  results.push(ok);
  console.log(`  ${ok ? 'نجح' : 'أخفق'}  ${results.length}. ${name}`);
  if (!ok) console.log(`        المتوقع ${JSON.stringify(want).slice(0, 600)}\n        الناتج  ${JSON.stringify(got).slice(0, 600)}`);
}

const MIME = { '.html': 'text/html; charset=utf-8', '.mjs': 'text/javascript', '.js': 'text/javascript',
  '.json': 'application/json', '.css': 'text/css', '.png': 'image/png', '.webmanifest': 'application/manifest+json' };
let hits = 0;
const server = createServer(async (rq, rs) => {
  hits += 1;
  const path = normalize(join(ROOT, decodeURIComponent(new URL(rq.url, 'http://x').pathname)));
  let body;
  try {
    if (!path.startsWith(ROOT)) throw new Error('خارج المستودع');
    body = await readFile(path);
  } catch {
    rs.writeHead(404).end();
    return;
  }
  rs.writeHead(200, { 'content-type': MIME[extname(path)] || 'application/octet-stream' }).end(body);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const URL_ = `http://127.0.0.1:${server.address().port}/app/index.html`;
const browser = await chromium.launch({ executablePath: CHROME, headless: true });
const errors = [];

async function device({ worker = false } = {}) {
  const context = await browser.newContext({ viewport: { width: 1180, height: 820 }, hasTouch: true, acceptDownloads: true });
  await context.addInitScript(({ t, worker }) => {
    const T = { spoken: [], clock: { now: t, mono: 0 }, noWorker: !worker };
    T.now = () => T.clock.now;
    T.mono = () => T.clock.mono;
    T.speaker = { available: async () => true, say: (x) => T.spoken.push(x) };
    window.MM_TEST = T;
  }, { t: NOW, worker });
  return context;
}
async function open(context) {
  const page = await context.newPage();
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error' && !m.text().includes('404')) errors.push(m.text()); });
  await page.goto(URL_);
  await page.waitForSelector('[data-screen="who"]');
  return page;
}
const all = (page) => page.evaluate(async () => {
  const b = await import('/app/backup.mjs');
  const s = await import('/app/store.mjs');
  const db = await s.openDB();
  const r = await b.readAll(db);
  db.close();
  return r;
});
const strip = (rec) => { const { rev, written_at, ...rest } = rec; return rest; };
const adult = async (page, code, first = false) => {
  await page.click('#adult');
  await page.fill('#pin', code);
  if (first) await page.fill('#pin2', code);
  await page.click('#pin-ok');
};
const type = async (page, n) => { for (const d of String(n)) await page.click(`[data-key="${d}"]`); };
// يجيب n بندًا صحيحًا من «ابدأ». يعيد معرّفات ما عُرض
async function answer(page, n) {
  await page.click('#start');
  const seen = [];
  while (seen.length < n) {
    await page.waitForFunction(() => {
      const a = document.getElementById('app').dataset.screen, t = document.querySelector('.task');
      return a !== 'workshop' && (a !== 'item' || (t && t.dataset.ready === 'true'));
    });
    if (await page.evaluate(() => document.getElementById('app').dataset.screen) !== 'item') break;
    const [id, kind] = await page.evaluate(() => [document.querySelector('.task').dataset.item, document.querySelector('.task').dataset.kind]);
    const it = BY.get(id);
    seen.push(id);
    await page.evaluate(() => { window.MM_TEST.clock.mono += 10000; });
    if (kind === 'shown') {
      if (it.role !== 'lesson.watch') await type(page, it.answer), await page.click('[data-key="ok"]');
      await page.click('#next');
    } else if (kind === 'assess') {
      await type(page, it.answer);
      await page.click('[data-key="ok"]');
    } else {
      await type(page, it.answer);
      await page.click('[data-key="ok"]');
      await page.waitForSelector('#next');
      await page.click('#next');
    }
    await page.waitForFunction((id) => document.querySelector('.task')?.dataset.item !== id
      || document.getElementById('app').dataset.screen !== 'item', id);
  }
  return seen;
}
async function newChild(page, code) {
  await page.click('[data-child="young"]');
  await page.waitForSelector('[data-screen="call"]');
  await adult(page, code, true);
  await page.waitForSelector('[data-screen="adult"]');
  await page.fill('#child-name', 'ك');
  await page.click('#dec-0');
  await page.click('#setup-ok');
  await page.waitForSelector('[data-screen="workshop"]');
}
const menu = async (page, code) => {
  await adult(page, code);
  await page.waitForSelector('[data-screen="adult"] #backup');
};

console.log(`=== النسخة الاحتياطية والعمل دون اتصال في Chrome ${browser.version()}`);

// ---------------------------------------------------------------- 1) جهاز أ: ملف، وبنود، ثم تصدير
const A = await device();
let pa = await open(A);
await newChild(pa, '1234');
await answer(pa, 3);
await pa.reload();
await pa.waitForSelector('[data-screen="who"]');
await menu(pa, '1234');
const [dl] = await Promise.all([pa.waitForEvent('download'), pa.click('#backup-save')]);
const file = JSON.parse(readFileSync(await dl.path(), 'utf8'));
const recA = await all(pa);
check('التصدير: الملف هو سجلات الجهاز كلها كما في IndexedDB، بهوية المحتوى الحالي واسم يومه',
  [file.format, file.version, file.content, file.made_at, dl.suggestedFilename(), file.records.map((r) => r.child),
    canonical(file.records.map((r) => (r.child === '@device' ? strip(r) : r)))
      === canonical(recA.map((r) => (r.child === '@device' ? (({ backup_at, ...x }) => strip(x))(r) : r)))],
  ['mental-math-backup', 1, { version: PACK.version, digest: PACK.digest }, NOW, 'mental-math-backup-2026-11-19.json',
    ['@device', 'young'], true]);
check('التصدير يسجّل تاريخه في سجل الجهاز ويعرضه',
  [recA.find((r) => r.child === '@device').backup_at, (await pa.textContent('#backup p')).startsWith('آخر نسخة احتياطية')], [NOW, true]);

// ---------------------------------------------------------------- 2) ملفات مرفوضة على جهاز أ: لا يتغير شيء
const refuse = async (page, name, obj, code) => {
  const before = await all(page);
  await page.setInputFiles('#backup-file', { name: 'x.json', mimeType: 'application/json',
    buffer: Buffer.from(typeof obj === 'string' ? obj : JSON.stringify(obj)) });
  await page.waitForSelector('#backup-refused');
  check(`ملف ${name}: يُرفض بسببه، ولا زر استبدال، ولم يتغير في الجهاز شيء`,
    [await page.getAttribute('#backup-refused', 'data-code'), await page.$('#backup-import') === null,
      canonical(await all(page)) === canonical(before)], [code, true, true]);
};
const young = file.records.find((r) => r.child === 'young');
await refuse(pa, 'ليس JSON', 'not json', 'unreadable');
await refuse(pa, 'غريب', { hello: 1 }, 'not_backup');
await refuse(pa, 'بمحرك تالف', { ...file, records: file.records.map((r) => (r.child === 'young' ? { ...r, engine: '{' } : r)) },
  'restore_rejected');
await refuse(pa, 'بطفل لا يعرفه التطبيق', { ...file, records: [...file.records, { ...young, child: 'stranger' }] }, 'unknown_child');
await refuse(pa, 'بملف مكرر', { ...file, records: [...file.records, young] }, 'duplicate');
await refuse(pa, 'بصيغة أحدث', { ...file, version: 2 }, 'version');

// ---------------------------------------------------------------- 3) جهاز ب: له رمزه، ويستعيد النسخة
const B = await device();
let pb = await open(B);
await pb.click('[data-child="young"]');
await pb.waitForSelector('[data-screen="call"]');
await adult(pb, '9999', true);
await pb.waitForSelector('[data-screen="adult"]');
await pb.click('#adult-back');
await pb.waitForSelector('[data-screen="who"]');
const beforeB = await all(pb);
await menu(pb, '9999');
await pb.setInputFiles('#backup-file', { name: 'b.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(file)) });
await pb.waitForSelector('#backup-import');
await Promise.all([pb.waitForEvent('load'), pb.click('#backup-import')]);
await pb.waitForSelector('[data-screen="who"]');
const recB = await all(pb);
check('الاستعادة: سجلات الجهاز هي سجلات النسخة إلا rev ووقت الكتابة، و rev كل سجل أكبر من كل rev كان على الجهاز',
  [canonical(recB.map(strip)) === canonical(file.records.map(strip)), recB.map((r) => r.rev),
    await pb.textContent('[data-child="young"] small')],
  [true, [beforeB[0].rev + 1, beforeB[0].rev + 1], 'ك']);
await pb.click('#adult');
await pb.fill('#pin', '9999');
await pb.click('#pin-ok');
const wrong = await pb.textContent('#pin-msg');
await pb.click('#pin-cancel');
await pb.waitForSelector('[data-screen="who"]');
await menu(pb, '1234');
await pb.waitForSelector('#undo-import', { timeout: 5000 }).catch(() => null);   // يُضاف بعد قراءة سجل التراجع
check('رمز البالغ بعد الاستعادة رمز النسخة: رمز الجهاز القديم يُرفض، ورمز النسخة يُدخل، وزر التراجع ظاهر',
  [wrong.length > 0, await pb.$('#undo-import') !== null], [true, true]);
await pb.click('#adult-back');
await pb.waitForSelector('[data-screen="who"]');

// ---------------------------------------------------------------- 4) الطفل يمضي على الجهازين بالبنود نفسها
await pa.click('#adult-back');
await pa.waitForSelector('[data-screen="who"]');
await pa.click('[data-child="young"]');
await pa.waitForSelector('[data-screen="workshop"]');
await pb.click('[data-child="young"]');
await pb.waitForSelector('[data-screen="workshop"]');
const nextA = await answer(pa, 4);
const nextB = await answer(pb, 4);
const ya = (await all(pa)).find((r) => r.child === 'young'), yb = (await all(pb)).find((r) => r.child === 'young');
check('بعد الاستعادة: البنود الأربعة التالية نفسها على الجهازين، والمحفوظ بعدها واحد إلا rev ووقت الكتابة',
  [nextA.length, canonical(nextA) === canonical(nextB), canonical(strip(ya)) === canonical(strip(yb))], [4, true, true]);

// ---------------------------------------------------------------- 5) نافذة مفتوحة قبل الاستيراد لا تكتب فوقه
// جهاز أ: الطفل في الورشة في نافذة، والبالغ يستعيد النسخة القديمة في نافذة أخرى. النافذة الأولى تتوقف عند «ابدأ»
await pa.reload();
await pa.waitForSelector('[data-screen="who"]');
await pa.evaluate(() => { window.MM_TEST.clock.now += 86400000; });   // اليوم التالي: جلسة يومه لم تُعقد، فـ«ابدأ» ظاهر
await pa.click('[data-child="young"]');
await pa.waitForSelector('[data-screen="workshop"]');
const pa2 = await open(A);
await menu(pa2, '1234');
await pa2.setInputFiles('#backup-file', { name: 'a.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(file)) });
await pa2.waitForSelector('#backup-import');
await Promise.all([pa2.waitForEvent('load'), pa2.click('#backup-import')]);
await pa2.waitForSelector('[data-screen="who"]');
const imported = (await all(pa2)).find((r) => r.child === 'young');
const goId = await pa.$('#start') !== null;
await pa.click('#start');
await pa.waitForSelector('[data-screen="call"]');
check('نافذة فتحت الطفل قبل الاستيراد: «ابدأ» يتوقف بـ conflict، والمحفوظ هو النسخة المستعادة لم يُكتب فوقها',
  [goId, await pa.evaluate(() => document.querySelector('.center').dataset.reason),
    canonical(strip((await all(pa2)).find((r) => r.child === 'young'))) === canonical(strip(young)),
    (await all(pa2)).find((r) => r.child === 'young').rev === imported.rev], [true, 'conflict', true, true]);
await pa.close();

// ---------------------------------------------------------------- 6) التراجع على جهاز ب
await pb.reload();
await pb.waitForSelector('[data-screen="who"]');
await menu(pb, '1234');
await Promise.all([pb.waitForEvent('load'), pb.click('#undo-import')]);
await pb.waitForSelector('[data-screen="who"]');
const undone = await all(pb);
await pb.click('[data-child="young"]');
await pb.waitForSelector('[data-screen="call"]');
check('التراجع: الجهاز كما كان قبل الاستيراد (سجل الجهاز وحده برمزه)، والطفل بلا ملف، ولا تراجع ثانٍ',
  [canonical(undone.map(strip)) === canonical(beforeB.map(strip)), await pb.evaluate(() => document.querySelector('.center').dataset.reason),
    await pb.evaluate(async () => {
      const b = await import('/app/backup.mjs'); const s = await import('/app/store.mjs');
      const db = await s.openDB(); const u = await b.undoInfo(db); db.close(); return u;
    })], [true, 'setup', null]);

// ---------------------------------------------------------------- 7) دون اتصال
const C = await device({ worker: true });
let pc = await open(C);
const cached = await pc.evaluate(async () => {
  const r = await navigator.serviceWorker.ready;
  const keys = await caches.keys();
  const c = await caches.open(keys[0]);
  return { keys, urls: (await c.keys()).map((q) => new URL(q.url).pathname).sort(), active: Boolean(r.active) };
});
const want = SW_URLS.map((u) => new URL(u, URL_).pathname).sort();
check('أول فتح: عامل الخدمة يعمل، ومخزن واحد باسم إصداره فيه كل ملفات القائمة',
  [cached.active, cached.keys.length, cached.keys[0].startsWith('mental-math-'), canonical(cached.urls) === canonical(want), want.length],
  [true, 1, true, true, SW_URLS.length]);
await C.setOffline(true);
const before = hits;
await pc.reload();
await pc.waitForSelector('[data-screen="who"]');
await newChild(pc, '5555');
const off = await answer(pc, 1);
const recC = (await all(pc)).find((r) => r.child === 'young');
check('الشبكة مقطوعة: التطبيق يُفتح، ويُنشأ الملف، ويُجاب بند ويُحفظ، ولم يصل الخادم طلب',
  [off.length, recC !== undefined && recC.rev >= 2, hits - before], [1, true, 0]);
await C.setOffline(false);
// فتح المجلد بلا اسم الصفحة، والشبكة مقطوعة
await C.setOffline(true);
const pc2 = await C.newPage();
await pc2.goto(URL_.replace('index.html', ''));
await pc2.waitForSelector('[data-screen="who"]');
check('الشبكة مقطوعة: فتح مجلد التطبيق بلا اسم الصفحة يُخدم بالصفحة', [await pc2.evaluate(() => document.title)], ['الحساب الذهني']);
await C.setOffline(false);

check('لا خطأ في الصفحات', errors, []);
await browser.close();
server.close();
const ok = results.filter(Boolean).length;
console.log(`\nالنتيجة: نجح ${ok} من ${results.length}`);
process.exit(ok === results.length ? 0 : 1);
