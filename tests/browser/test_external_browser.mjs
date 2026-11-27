// المتطلب الخارجي من الشاشة (5.1، قرار الأب في 26 نوفمبر: بوابة الجاهزية وقرار المعلم كلاهما).
//
//     node tests/browser/test_external_browser.mjs [مسار Chrome]
//
// في Node يبدأ الطفل الكبير بقرار المعلم عند 8-5-2 (جمع المدد) ويخطئ فيها، حتى تُطلب بوابة جاهزيتها، ويُحفظ سجله. ثم في
// Chrome. المتوقع مكتوب من القرار قبل التشغيل:
//  1. أول بند بوابة الجاهزية: وجه ساعة عقرباه بزاويتي الوقت في البند (الطويل 6 درجات للدقيقة، والقصير 30 للساعة ونصف
//     درجة للدقيقة)، والبطاقات أوقات البند.
//  2. بطاقة خاطئة: تنتهي البوابة بلا تغذية راجعة، ولا يُعرض في الجلسة بند من درس 8-5-2، والسجل فيه محاولة «أخفق».
//  3. لوحة البالغ: سطر «قراءة الساعة» يقول إنه أخفق مرة. قرار «يعرف قراءة الساعة» بسببه يُسجَّل، فيصير السطر «بقرار المعلم»
//     ومعه «ألغِ القرار»، وصف 8-5-2 في اللوحة يذكر القرار.
//  4. اليوم التالي: يُفتح درس 8-5-2 (افتتاحه) بلا بوابة جاهزية.
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
const P = PROFILES.older1;
const T = '8-5-2';
const results = [];
function check(name, got, want) {
  const ok = canonical(got) === canonical(want);
  results.push(ok);
  console.log(`  ${ok ? 'نجح' : 'أخفق'}  ${results.length}. ${name}`);
  if (!ok) console.log(`        المتوقع ${JSON.stringify(want).slice(0, 600)}\n        الناتج  ${JSON.stringify(got).slice(0, 600)}`);
}

// Node: يعرف كل شيء إلا T، حتى تُطلب بوابة جاهزيتها
const DAY0 = Date.UTC(2026, 9, 1, 8);
function prepare() {
  const e = new Engine(undefined, { group: P.group });
  // قرار البداية عند 8-5-2 (كما في tests/test_external): يبلغ الطفل بوابة جاهزيتها في جلسته الثانية، بدل مئات الأيام
  e.apply({ id: 'd0', type: 'teacher_open', skill: T, bypass: [...e.pre[T]], reason: 'يبدأ من جمع المدد' });
  const src = new ContentSource(PACK.items, true, IDENT);
  let secs = 0;
  const sc = new Scheduler(e, P.types, (k, w) => src.pick(k, w), null, { group: P.group, scope: P.scope, learning: true,
    cap: P.cap, item_seconds: () => { const x = secs; secs = 0; return x; }, records: [], retention: true, content: IDENT,
    day_cap: P.day_cap });
  for (let d = 0; d < 5; d++) {
    const now = DAY0 + d * 86400000;
    sc.today = familyDay(now, TZ);
    for (let k = 0; k < 8; k++) {
      if (k > 0 && !(sc.cur === null && (sc.start_at === null || sc.more()))) break;
      const st = new Stepper(e, sc, () => now);
      st.open(sc.g_session());
      if (st.pending === null) { sc.practiced(null, true); break; }
      while (st.pending !== null) {
        const [item, w] = st.pending;
        if (w.activity === 'ready') return { rec: st.snapshot('older1'), now, first: item.id, day: d };
        st.show(st.seq);
        const role = BY.get(item.id).role;
        if (role.startsWith('lesson') || role.startsWith('practice')) { secs = 10; st.event(st.seq, ['end']); continue; }
        const v = item.skill === T ? wrongOf(item) : item.cards ? item.answer : rightOf(item);
        secs = 10;
        st.event(st.seq, ['confirm', v]);
        if (!ASSESS.includes(w.activity)) {
          if (item.skill === T) st.event(st.seq, ['confirm', item.cards ? item.answer : rightOf(item)]);
          st.event(st.seq, ['end']);
        }
      }
    }
  }
  throw new Error('لم تُطلب بوابة جاهزية ' + T);
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
const scr = (page) => page.evaluate(() => document.getElementById('app').dataset.screen);
const ready = () => page.waitForFunction(() => {
  const a = document.getElementById('app').dataset.screen, t = document.querySelector('.task');
  return a !== 'workshop' && (a !== 'item' || (t && t.dataset.ready === 'true'));
});
// يجيب صحيحًا حتى تنتهي الجلسة، إلا بنود بوابة الجاهزية فبما يُعطى. يعيد ما عُرض: [نشاط، مهارة]
async function play(page, readyAnswer) {
  const seen = [];
  for (let n = 0; n < 200; n++) {
    await ready();
    if (await scr(page) !== 'item') return seen;
    const [id, kind, act] = await page.evaluate(() => {
      const t = document.querySelector('.task');
      return [t.dataset.item, t.dataset.kind, t.dataset.activity];
    });
    const it = BY.get(id);
    if (!seen.length || seen[seen.length - 1].join(' ') !== `${act} ${it.skill}`) seen.push([act, it.skill]);
    await page.evaluate(() => { window.MM_TEST.clock.mono += 10000; });
    if (act === 'ready') { await page.click(`#cards [data-card="${readyAnswer(it)}"]`); continue; }
    if (it.role === 'lesson.watch') { await page.click('#next'); continue; }
    const v = it.cards ? it.answer : rightOf(it);
    if (it.cards) await page.click(`#cards [data-card="${v}"]`);
    else { await type(page, v); await page.click('[data-key="ok"]'); }
    if (kind === 'assess') { if (it.how) await page.click('#how [data-how="back"]'); continue; }
    await page.waitForSelector('#next');
    await page.click('#next');
  }
  throw new Error('جلسة لا تنتهي');
}
const acts = (seen) => seen.map(([a, s]) => `${a} ${s}`);
const record = (page) => page.evaluate(async () => {
  const s = await import('/app/store.mjs');
  const db = await s.openDB();
  const r = await s.load(db, 'older1');
  db.close();
  return r;
});

const { rec, now, first, day } = prepare();
console.log(`=== المتطلب الخارجي من الشاشة، Chrome ${browser.version()}: بوابة الجاهزية في اليوم ${day + 1} (${first})`);
NOW.t = now;
let page = await open();
await page.evaluate(async (r) => {
  const s = await import('/app/store.mjs');
  const db = await s.openDB();
  await s.commit(db, r, 0);
  db.close();
}, rec);
await page.reload();
await page.waitForSelector('[data-screen="who"]');
await page.click('[data-child="older1"]');
await page.waitForSelector('[data-screen="workshop"]');
await page.click('#start');
await ready();
// 1. وجه الساعة والبطاقات: يُقاس الرسم من إحداثيات العقربين، والبطاقات من نصوصها
const face = await page.evaluate(() => {
  const t = document.querySelector('.task'), svg = t.querySelector('svg.k-clock');
  const hands = svg ? [...svg.querySelectorAll('line.hand')].map((l) => {
    const [x1, y1, x2, y2] = ['x1', 'y1', 'x2', 'y2'].map((a) => +l.getAttribute(a));
    return [l.classList.contains('hour') ? 'hour' : 'minute', Math.round(((Math.atan2(x2 - x1, y1 - y2) * 180 / Math.PI) + 360) % 360 * 10) / 10];
  }) : null;
  const cards = [...document.querySelectorAll('#cards [data-card]')].map((b) => [b.dataset.card, b.textContent.replace(/[⁦-⁩]/g, '').trim()]);
  return { id: t.dataset.item, act: t.dataset.activity, hands, cards };
});
const it0 = BY.get(face.id);
const m0 = it0.model ?? {};
check('أول بند بوابة الجاهزية: وجه ساعة بعقربي الوقت، والبطاقات أوقات البند بترتيبها',
  [face.act, face.id === first, Object.fromEntries(face.hands ?? []), face.cards],
  ['ready', true, { hour: Math.round(((m0.h % 12) * 30 + m0.m * 0.5) % 360 * 10) / 10, minute: m0.m * 6 },
    (it0.cards ?? []).map((c) => [c, it0.card_labels[c].ar.replace(/[⁦-⁩]/g, '')])]);
// 2. بطاقة خاطئة: تنتهي البوابة، ولا درس لـ 8-5-2 في الجلسة
const day1 = acts(await play(page, (it) => it.cards.find((c) => c !== it.answer)));
let r = await record(page);
const tried = r.engine ? JSON.parse(r.engine).attempts.filter((a) => a.what === 'ready') : null;
check('بطاقة خاطئة: بند واحد من البوابة، ولا بند من درس 8-5-2 في الجلسة، والسجل فيه محاولة «أخفق»',
  [day1[0], day1.filter((x) => x === `ready ${T}`).length, day1.some((x) => /^(opening|lesson|evidence) 8-5-2$/.test(x)),
    (tried ?? []).map((a) => [a.ext, a.result])], [`ready ${T}`, 1, false, [['clock', 'fail']]]);
console.log(`        ${day1.join(' ← ')}`);
// 3. لوحة البالغ: السطر ثم القرار
await page.waitForSelector('[data-screen="end"], [data-screen="workshop"], [data-screen="who"]');
await page.close();
page = await open();
await page.click('[data-child="older1"]');
await page.waitForSelector('[data-screen="workshop"]');
await page.click('#adult');
await page.fill('#pin', '4821');
if (await page.$('#pin2')) await page.fill('#pin2', '4821');
await page.click('#pin-ok');
await page.waitForSelector('#external');
const line0 = await page.evaluate(() => document.querySelector('#external .ext[data-ext="clock"]')?.textContent ?? null);
await page.fill('#ready-reason', 'يقرأ الساعة في البيت');
await page.click('[data-ready="clock"]');
await page.waitForSelector('#external .ext[data-by="decision"]');
await page.waitForSelector('#board[data-ready="true"]');
const after = await page.evaluate(() => [document.querySelector('#external .ext[data-ext="clock"]').textContent,
  !!document.querySelector('[data-revoke-ready="clock"]'),
  document.querySelector('#board .board-child[data-child="older1"] tr[data-skill="8-5-2"] small.external')?.dataset.by ?? null]);
r = await record(page);
const dec = JSON.parse(r.engine).decisions.filter((d) => d.kind === 'ready').map((d) => [d.skills, d.reason, d.standing]);
check('اللوحة: «أخفق مرة» قبل القرار، ثم القرار بسببه يُسجَّل، والسطر «بقرار المعلم» ومعه «ألغِ القرار»، وصف 8-5-2 يذكره',
  [/أخفق في بوابة الجاهزية مرة/.test(line0 ?? ''), /بقرار المعلم/.test(after[0]), after[1], after[2], dec],
  [true, true, true, 'decision', [[['clock'], 'يقرأ الساعة في البيت', true]]]);
await page.close();
// 4. اليوم التالي: درس 8-5-2 بلا بوابة جاهزية
NOW.t = now + 86400000;
page = await open();
await page.click('[data-child="older1"]');
await page.waitForSelector('[data-screen="workshop"]');
await page.click('#start');
const day2 = acts(await play(page, (it) => it.answer));
check('اليوم التالي: يُفتح درس 8-5-2 بلا بوابة جاهزية',
  [day2.some((x) => x === `opening ${T}` || x === `lesson ${T}`), day2.some((x) => x.startsWith('ready '))], [true, false]);
console.log(`        ${day2.join(' ← ')}`);
check('لا خطأ في الصفحة', errors, []);
await browser.close();
server.close();
console.log(results.every(Boolean) ? `نجحت الاختبارات كلها: ${results.length}` : `النتيجة: نجح ${results.filter(Boolean).length} من ${results.length}`);
process.exit(results.every(Boolean) ? 0 : 1);
