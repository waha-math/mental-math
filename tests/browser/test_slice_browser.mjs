// تجربة الشريحة في Chrome: مسار الصغير في 1-4 من الشاشة، بالنقر، على IndexedDB الحقيقي.
//
//     node tests/browser/test_slice_browser.mjs [مسار Chrome]
//
// ما طلبه الأب للتجربة: يختار ملفه، ويسمع التعليمة، ويكمل مسألة، ويطلب المساعدة، ويعود بعد الإغلاق.
// النتائج المتوقعة مكتوبة هنا من القواعد قبل التشغيل. ومعها «مطابقة المسار» (UI-PLAN.md، القسم 5): كل ما نقره الاختبار
// يُعاد تشغيله هنا في Node على وحدات التطبيق مباشرة بلا شاشة ولا طبقة وصل، والسجل المحفوظ في المتصفح يطابق ناتجه حرفًا
// بحرف: المحرك، وحالة المجدول، وسجلات البنود، والبند الجاري.
//
// الصوت بديل يسجّل ما طُلب نطقه: الاختبار يثبت أن التعليمة طُلب نطقها، لا أنها سُمعت. والوقت والساعة يضعهما الاختبار.
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

const ROOT = resolve(new URL('../..', import.meta.url).pathname);
const CHROME = process.argv[2] || '/usr/bin/google-chrome';
const PACK = JSON.parse(readFileSync(join(ROOT, 'slice-content.json'), 'utf8'));
const BY = new Map(PACK.items.map((i) => [i.id, i]));
const IDENT = { version: PACK.version, digest: PACK.digest };
const TYPES = { '1-4-1': ['ف1', 'ف3'], '1-4-2': ['ف2', 'ف3', 'ف4'], '3-5-1': ['ف1', 'ف2', 'ف3'],
  '3-5-2': ['ف1', 'ف2', 'ف3', 'ف4'], '3-5-3': ['ف3'] };                   // من صفوف المهارات في الخريطة
// ملفات الأطفال كما في 10.2 وقرار الأب: السقف وحد اليوم بالثواني، وقرارات الفتح. مكتوبة هنا يدويًا، لا من إعداد التطبيق
const OLDER = { group: 'older', scope: ['3-5-1', '3-5-2', '3-5-3'], cap: 600, day_cap: 3000,
  decisions: [['3-5-1', ['3-3-2', '3-2-3']], ['3-5-2', ['3-2-1', '3-3-1', '2-5-2']]] };
const PROF = { young: { child: 'young', avatar: '🦊', group: 'young', scope: ['1-4-1', '1-4-2'], cap: 360, day_cap: 1800,
  decisions: [['1-4-1', ['1-3-3']]] }, older1: { child: 'older1', avatar: '🐬', ...OLDER },
older2: { child: 'older2', avatar: '🦉', ...OLDER } };
const DAY0 = Date.UTC(2026, 10, 19, 8, 0, 0);                             // 10 صباحًا في القاهرة، 19 نوفمبر 2026
const DAYNUM = Math.floor(Date.UTC(2026, 10, 19) / 86400000);
const SECS = 10;                                                          // ثواني كل بند، يضعها الاختبار
const results = [];

function check(name, got, want) {
  const ok = canonical(got) === canonical(want);
  results.push(ok);
  console.log(`  ${ok ? 'نجح' : 'أخفق'}  ${results.length}. ${name}`);
  if (!ok) console.log(`        المتوقع ${JSON.stringify(want).slice(0, 700)}\n        الناتج  ${JSON.stringify(got).slice(0, 700)}`);
}

const MIME = { '.html': 'text/html; charset=utf-8', '.mjs': 'text/javascript', '.json': 'application/json', '.css': 'text/css' };
const server = createServer(async (rq, rs) => {
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
const context = await browser.newContext({ viewport: { width: 1180, height: 820 }, hasTouch: true });
const errors = [];

// ---------------------------------------------------------------- الإعادة في Node: المرجع الذي يُقارن به المحفوظ
// لا تستعمل طبقة الوصل: تبني المحرك والمجدول وطبقة الخطوات مباشرة، بالخيارات المكتوبة هنا يدويًا من الخريطة
const RS = {};                                                            // حالة الإعادة لكل طفل
let CUR = PROF.young, R = (RS.young = { rec: null, st: null, e: null, sc: null, secs: 0 });
const use = (child) => { CUR = PROF[child]; R = (RS[child] ??= { rec: null, st: null, e: null, sc: null, secs: 0 }); };
const source = () => { const src = new ContentSource(PACK.items, true, IDENT); return (s, w) => src.pick(s, w); };
const secs = () => { const x = R.secs; R.secs = 0; return x; };
const rSnap = () => (R.st ? R.st.snapshot(CUR.child) : persist.snapshot(R.e, R.sc, null, CUR.child));
// decisions: أرقام قرارات الملف التي سجّلها البالغ، بترتيبها
function rSetup(reason, decisions = [0]) {
  R.e = new Engine(undefined, { group: CUR.group });
  decisions.forEach((d, k) => R.e.apply({ id: 'd' + k, type: 'teacher_open', skill: CUR.decisions[d][0],
    bypass: CUR.decisions[d][1], reason }));
  R.sc = new Scheduler(R.e, TYPES, source(), null, { group: CUR.group, scope: CUR.scope, learning: true, cap: CUR.cap,
    item_seconds: secs, records: [], retention: true, content: IDENT, day_cap: CUR.day_cap });
  R.st = null;
  R.rec = rSnap();
}
// قرار فتح بعد إنشاء الملف، والجلسة مغلقة
function rDecide(d, reason) {
  const r = persist.restore(JSON.parse(JSON.stringify(R.rec)), { types: TYPES, source: source(), answer: null,
    item_seconds: secs, records: [], today: null, content: IDENT });
  R.e = r.engine; R.sc = r.scheduler; R.st = null;
  R.sc.send({ type: 'teacher_open', skill: CUR.decisions[d][0], bypass: CUR.decisions[d][1], reason });
  R.rec = rSnap();
}
function rStart(now, more = false) {
  const day = Math.floor((now + 2 * 3600000) / 86400000);                 // القاهرة UTC+2 في نوفمبر
  const r = persist.restore(JSON.parse(JSON.stringify(R.rec)), { types: TYPES, source: source(), answer: null,
    item_seconds: secs, records: [], today: day, content: IDENT });
  R.e = r.engine; R.sc = r.scheduler; R.sc.today = day;
  R.st = new Stepper(R.e, R.sc, () => now);
  R.st.open(more ? R.sc.g_extra() : R.sc.g_session());
  R.rec = rSnap();
}
function rShow(id) {
  if (R.st.pending[0].id !== id) throw new Error(`الشاشة عرضت ${id} والإعادة تطلب ${R.st.pending[0].id}`);
  R.st.show(R.st.seq);
  R.rec = rSnap();
}
function rEvent(ev, final) {
  if (final) R.secs = SECS;
  const r = R.st.event(R.st.seq, ev);
  R.rec = rSnap();
  return r;
}
const eng = (rec) => JSON.parse(rec.engine);                            // المحرك محفوظ نصًّا قانونيًا
const strip = (rec) => { const { rev, written_at, ...rest } = rec; return rest; };

// ---------------------------------------------------------------- الصفحة
async function open({ stub = true } = {}) {
  const page = await context.newPage();
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error' && !m.text().includes('404')) errors.push(m.text()); });
  await page.addInitScript(({ stub, t }) => {
    // noWorker: عامل الخدمة (العمل دون اتصال) يُختبر في test_backup_browser.mjs، لا هنا
    const T = { spoken: [], clock: { now: t, mono: 0 }, fail: false, noWorker: true };
    T.now = () => T.clock.now;
    T.mono = () => T.clock.mono;
    T.hooks = { beforePut: (tx) => { if (T.fail) { T.fail = false; tx.abort(); } } };
    if (stub) T.speaker = { available: async () => true, say: (x) => T.spoken.push(x) };
    window.MM_TEST = T;
  }, { stub, t: NOW.t });
  await page.goto(URL_);
  await page.waitForSelector('[data-screen="who"]');
  return page;
}
const NOW = { t: DAY0 };
const scr = (page) => page.evaluate(() => document.getElementById('app').dataset.screen);
const dbRec = (page, key = 'young') => page.evaluate(async (key) => {
  const store = await import('/app/store.mjs');
  const db = await store.openDB();
  const r = await store.load(db, key);
  db.close();
  return r;
}, key);
const shownItem = async (page) => {
  await page.waitForSelector('.task[data-ready="true"]');
  return page.evaluate(() => {
    const t = document.querySelector('.task'), svg = document.querySelector('#model svg.frame'),
      ln = document.querySelector('#model > svg.line');                // خط البند وحده، لا خطّا المقارنة
    return { id: t.dataset.item, kind: t.dataset.kind, activity: t.dataset.activity,
      prompt: document.getElementById('prompt').textContent.replace(/\s+/g, ' ').trim(),
      // المعادلة من اليسار إلى اليمين فعلًا: أول محارفها على الشاشة يسار آخرها، لا صفة الاتجاه وحدها
      eqs: [...document.querySelectorAll('#prompt bdi')].map((b) => {
        const t = b.firstChild, at = (k) => { const r = document.createRange(); r.setStart(t, k); r.setEnd(t, k + 1); return r.getBoundingClientRect().left; };
        return [b.getAttribute('dir'), getComputedStyle(b).direction, at(0) < at(t.length - 1)];
      }),
      model: svg ? { counters: Number(svg.dataset.counters), covered: svg.dataset.covered === 'true', ghost: svg.classList.contains('ghost') } : null,
      line: ln ? JSON.parse(ln.dataset.shown) : null,
      // بند المقارنة: الحلان كلٌّ على خط باسم بطاقته، والبطاقات بدل لوحة الأرقام
      pair: [...document.querySelectorAll('#model .pair-row')].map((r) => [r.dataset.card, JSON.parse(r.querySelector('svg.line').dataset.shown)]),
      cards: [...document.querySelectorAll('#cards [data-card]')].map((b) => b.dataset.card),
      // الإشارة قبل العدد على الرسم («−40» لا «40−»): اتجاه نص الرسم من اليسار، وأول محرف مرسوم يسار آخره
      lineLtr: ln ? [...ln.querySelectorAll('text')].every((t) => getComputedStyle(t).direction === 'ltr'
        && (t.textContent.length < 2 || t.getStartPositionOfChar(0).x < t.getStartPositionOfChar(t.textContent.length - 1).x)) : null,
      next: Boolean(document.getElementById('next')), ok: Boolean(document.getElementById('ok')),
      who: document.querySelector('.strip .who')?.textContent ?? null,
      scroll: document.documentElement.scrollHeight <= window.innerHeight && document.documentElement.scrollWidth <= window.innerWidth,
      said: window.MM_TEST.spoken[window.MM_TEST.spoken.length - 1] ?? null };
  });
};
const type = async (page, n) => { for (const d of String(n)) await page.click(`[data-key="${d}"]`); };
const tick = (page) => page.evaluate((s) => { window.MM_TEST.clock.mono += s * 1000; }, SECS);
const settled = (page) => page.waitForFunction(() => {
  const a = document.getElementById('app').dataset.screen, t = document.querySelector('.task');
  return a !== 'item' || (t && t.dataset.ready === 'true');
});
const plain = (s) => s.replace(/[⁦-⁩]/g, '').replace(/\s+/g, ' ').trim();
const say = (s) => plain(s).replace(/[+−\-=▢]/g, (c) => ({ '+': ' زائد ', '−': ' ناقص ', '-': ' ناقص ', '=': ' يساوي ', '▢': ' كم ' })[c])
  .replace(/\s+/g, ' ').trim();

// ما يجب أن تعرضه الشاشة لكل بند، من تعريفه في المحتوى. يعيد قائمة المخالفات
const FAULTS = [];
function inspect(v) {
  const it = BY.get(v.id), n = it.numbers, bad = [];
  if (v.prompt.replace(/\s/g, '') !== plain(it.text_ar).replace(/\s/g, '')) bad.push('النص');
  const eqs = (it.text_ar.match(/⁦/g) || []).length;
  if (v.eqs.length !== eqs || v.eqs.some(([a, b, c]) => a !== 'ltr' || b !== 'ltr' || c !== true)) bad.push('اتجاه المعادلة');
  const model = it.performance === 'frame_empty' ? { counters: n.n, covered: false, ghost: false }
    : it.performance === 'frame_counters' ? { counters: 10 - n.e, covered: true, ghost: false }
      : it.performance === 'step_pair' ? { counters: 0, covered: false, ghost: true } : null;
  if (canonical(v.model) !== canonical(model)) bad.push('النموذج');
  // خط الأعداد: ما يُكتب عليه، من حقل model في المحتوى وبوصف المورد في 10.2. المسؤول عنه مربع، ولا يُكتب جوابه
  const m = it.performance === 'compare' ? null : it.model ?? null;
  if (it.performance === 'compare') {
    const [A, B] = it.model.pair;
    const pair = [['A', { stations: [A.start, ...A.stations].map(String), jumps: A.jumps.map((j) => '−' + j) }],
      ['B', { stations: [B.start, ...B.stations].map(String), jumps: B.jumps.map((j) => '+' + j) }]];
    if (canonical([v.pair, v.cards]) !== canonical([pair, it.cards])) bad.push('رسم المقارنة أو بطاقاتها');
  } else if (v.pair.length || v.cards.length) bad.push('رسم مقارنة أو بطاقات في غير بند مقارنة');
  const line = m === null ? null : {
    line_back: { stations: [String(m.start), ...m.stations.map((_, k) => (k === m.stations.length - 1 ? '▢' : ''))],
      jumps: m.jumps.map((j) => '−' + j) },
    station_back: { stations: [String(m.start), ...m.stations.map((x, k) => (k === m.hide[1] ? '▢' : String(x)))],
      jumps: m.jumps.map((j) => '−' + j) },
    line_up: { stations: [m.start, ...m.stations].map(String), jumps: m.jumps.map((j) => '+' + j) },
    jump_missing: { stations: [m.start, ...m.stations].map(String), jumps: m.jumps.map((j, k) => (k === m.hide[1] ? '▢' : '+' + j)) },
  }[it.performance];
  if (canonical(v.line) !== canonical(line)) bad.push('خط الأعداد');
  if (line !== null && v.lineLtr !== true) bad.push('اتجاه أعداد خط الأعداد');
  if (!v.said || !v.said.includes(say(it.audio_ar))) bad.push('الصوت');
  if (v.who !== CUR.avatar) bad.push('هوية الطفل');
  if (!v.scroll) bad.push('الشاشة تتمرر');
  if (v.kind === 'assess' && (v.next || v.ok)) bad.push('تغذية راجعة أو «التالي» في بند تقييم');
  if (bad.length) FAULTS.push([v.id, bad]);
  return it;
}

// طفل الاختبار يتعلّم: لا يعرف المهارة حتى يرى درسها. قبله يخطئ في بنود التقييم، وفي بنود التعليم يخطئ أولًا ثم يصيب على
// النموذج. بعده يجيب صحيحًا. يعيد معرّفات ما عُرض، ويتوقف عند stopAt والبند معروض لم يُجب
const KNOWN = new Set();
const SHOT = new Set();
const wrongOf = (it) => (it.answer === 9 ? 8 : it.answer + 1);
async function play(page, { stopAt = null } = {}) {
  const seen = [];
  for (;;) {
    await settled(page);
    if (await scr(page) !== 'item') return seen;
    const v = await shownItem(page);
    const it = inspect(v);
    rShow(v.id);
    seen.push(v.id);
    if (process.env.DEBUG) console.log('   ', R.sc.cur, v.id, v.kind);
    if (process.env.SHOTS && !SHOT.has(it.role + it.performance)) {     // صورة لأول بند من كل دور وأداء، للمعاينة
      SHOT.add(it.role + it.performance);
      await page.screenshot({ path: `${process.env.SHOTS}/${v.id.replace(/\//g, '_')}.png` });
    }
    if (stopAt !== null && seen.length === stopAt) return seen;
    await tick(page);
    const role = it.role;
    if (v.kind === 'shown') {
      if (role.startsWith('lesson')) KNOWN.add(it.skill);
      if (it.performance === 'compare') {                                // بطاقة، ثم يُعرض الجواب
        await page.click(`#cards [data-card="${it.answer}"]`);
        await page.waitForSelector('#next');
      } else if (role !== 'lesson.watch') await type(page, it.answer), await page.click('[data-key="ok"]');
      await page.click('#next');
      rEvent(['end'], true);
    } else if (v.kind === 'assess') {
      const a = KNOWN.has(it.skill) ? it.answer : wrongOf(it);
      await type(page, a);
      await page.click('[data-key="ok"]');
      if (it.how) {                                                      // «كيف حسبتها؟» قبل التأكيد (17.25)
        await page.click('#how [data-how="back"]');
        rEvent(['how', 'back'], false);
      }
      rEvent(['confirm', a], true);
    } else {
      if (!KNOWN.has(it.skill)) {
        const w = wrongOf(it);
        await type(page, w);
        await page.click('[data-key="ok"]');
        await page.waitForSelector('[data-key="ok"]:disabled');
        rEvent(['confirm', w], false);
        await page.waitForFunction(() => document.getElementById('answer').textContent === '');
      }
      await type(page, it.answer);
      await page.click('[data-key="ok"]');
      await page.waitForSelector('#next');
      rEvent(['confirm', it.answer], false);
      await page.click('#next');
      rEvent(['end'], true);
    }
  }
}
// «ابدأ»، وانتظار خروج الشاشة من الورشة: بلا هذا يقرأ الاختبار الورشة قبل أن تُعرض الجلسة (خطأ في أداتي أول مرة)
const press = async (page) => {
  await page.click('#start');
  await page.waitForFunction(() => document.getElementById('app').dataset.screen !== 'workshop');
};
const pin = async (page, first = false) => {
  await page.click('#adult');
  await page.fill('#pin', '4821');
  if (first) await page.fill('#pin2', '4821');
  await page.click('#pin-ok');
  await page.waitForSelector('[data-screen="adult"]');
};
const sameAsReplay = async (page, name) => check(name + ': المحفوظ في المتصفح يطابق الإعادة في Node حرفًا بحرف',
  strip(await dbRec(page, CUR.child)), R.rec);
const sameAsReplay2 = async (name, child) => check(name + ': المحفوظ في المتصفح يطابق الإعادة في Node حرفًا بحرف',
  strip(await dbRec(page, child)), RS[child].rec);

console.log(`=== تجربة الشريحة في Chrome ${browser.version()}: مسار الصغير في 1-4 من الشاشة`);

// ---------------------------------------------------------------- 1) يختار ملفه، ولا ملف: يُنادى بالغ، ويسجّل القرار
let page = await open();
await page.click('[data-child="young"]');
await page.waitForSelector('[data-screen="call"]');
check('أول فتح: الطفل يختار صورته، ولا ملف له: «نادِ أحد الكبار» بصوتها، ولا شيء محفوظ ولا قرار فتح ضمني',
  [await page.evaluate(() => document.querySelector('.center').dataset.reason), await dbRec(page),
    await page.evaluate(() => window.MM_TEST.spoken)], ['setup', null, ['نادِ أحد الكبار']]);
await pin(page, true);
await page.fill('#child-name', 'ك');
await page.fill('#decision-reason', 'قرار الشريحة في 10.2');
await page.click('#setup-ok');                                           // بلا قرار مختار: لا يُنشأ ملف
check('مدخل البالغ: لا قرار مختار سلفًا، وبلا اختيار لا يُنشأ ملف', [await page.evaluate(() => document.getElementById('dec-0').checked),
  await page.evaluate(() => document.getElementById('adult-msg').textContent), await dbRec(page)],
[false, 'اختر قرارًا واحدًا على الأقل', null]);
await page.click('#dec-0');
await page.click('#setup-ok');
await page.waitForSelector('[data-screen="workshop"]');
rSetup('قرار الشريحة في 10.2');
{
  const rec = await dbRec(page), dev = await dbRec(page, '@device');
  check('البالغ يسجّل قرار 10.2 برمزه: الملف يُنشأ بقرار فتح 1-4-1 متجاوزًا 1-3-3 وحده وبسببه، والاسم في سجل الجهاز لا في ملف الطفل، والرمز غير محفوظ نصًا',
    [rec.rev, eng(rec).decisions.map((x) => [x.kind, x.skills, x.bypass, x.reason]), dev.names, dev.pin !== '4821' && dev.pin.length === 64, JSON.stringify(rec).includes('"ك"')],
    [1, [['open', ['1-4-1'], ['1-3-3'], 'قرار الشريحة في 10.2']], { young: 'ك' }, true, false]);
  await sameAsReplay(page, 'بعد إنشاء الملف');
}

// ---------------------------------------------------------------- 2) يسمع التعليمة
await press(page);
rStart(NOW.t);
let v = await shownItem(page);
inspect(v);
rShow(v.id);
{
  const rec = await dbRec(page);
  check('«ابدأ»: جلسة البحث S1 بيوم الأسرة، وأول بند بوابة 1-4-1، ونُطق تمهيد البوابة ثم السؤال، والبند محفوظ معروضًا قبل أي إجابة',
    [v.id, v.prompt, v.said, eng(rec).sessions.S1.kind, eng(rec).sessions.S1.day, rec.current?.journal?.item ?? null, rec.current?.journal?.raw ?? null,
      rec.records.length],
    ['1-4-1/gate/01', '6 وكم تصير 10؟', 'أسئلة قصيرة لنعرف من أين نبدأ. 6 وكم تصير 10؟', 'search', DAYNUM, '1-4-1/gate/01', [], 0]);
}
await page.click('#listen');
check('زر «اسمع السؤال» يعيد نطق السؤال وحده', await page.evaluate(() => window.MM_TEST.spoken.slice(-1)), ['6 وكم تصير 10؟']);

// ---------------------------------------------------------------- 3) يكمل مسألة
await tick(page);
await type(page, 5);
await page.click('[data-key="del"]');                                    // زلّة إصبع تُصحَّح بالحذف قبل التأكيد (4.1)
await type(page, 4);
await page.click('[data-key="ok"]');
rEvent(['confirm', 4], true);
v = await shownItem(page);
inspect(v);
{
  const rec = await dbRec(page), r0 = rec.records[0];
  check('يكتب 5 ثم يحذف ثم 4 ويؤكد: سجل واحد لبند البوابة، أول إجابة صحيحة بقيمتها 4 بلا دعم، بجلسته وحزمته ووقته. وعُرض بند آخر بلا '
    + 'تغذية راجعة، وحالة الحفظ «تم الحفظ»',
  [rec.records.length, r0.item, r0.status, r0.first, r0.support_before, r0.session, r0.pack, r0.at, r0.values,
    v.id !== '1-4-1/gate/01', v.ok, await page.evaluate(() => document.getElementById('save').textContent)],
  [1, '1-4-1/gate/01', 'complete', true, [], 'S1', PACK.version, NOW.t, [4], true, false, 'تم الحفظ']);
}
rShow(v.id);

// ---------------------------------------------------------------- 4) يطلب المساعدة
const second = v.id;
await page.click('#help');
await page.waitForSelector('#sheet');
await page.click('#help-no');
{
  const rec = await dbRec(page);
  check('«أحتاج مساعدة» ثم «لا»: لا يُسجَّل شيء، والبند باقٍ', [rec.records.length, rec.current?.journal?.item ?? null, rec.current?.journal?.raw ?? null,
    await page.evaluate(() => Boolean(document.getElementById('sheet')))], [1, second, [], false]);
}
await tick(page);
await page.click('#help');
await page.click('#help-yes');
rEvent(['support', 'requested'], true);
await settled(page);
{
  const rec = await dbRec(page), r1 = rec.records[1];
  check('«أحتاج مساعدة» ثم «نعم» في بند بوابة: البند يُختم منقطعًا ومعه طلب المساعدة، لا خطأً ولا صحيحًا، ولا يُعرض تلميح',
    [r1.item, r1.status, r1.first, r1.support_before, r1.final], [second, 'interrupted', null, ['requested'], 'incomplete']);
}
await play(page);
await page.waitForSelector('[data-screen="end"]');
{
  const rec = await dbRec(page);
  const n = rec.records.filter((r) => r.session === 'S1' && r.status === 'complete').length;
  check('ختام S1: الجلسة مختومة في المحرك، والرسالة بعدد ما أكّد فيه إجابة، وحالة الحفظ «تم الحفظ»',
    [eng(rec).sessions.S1.ended, eng(rec).current, await page.evaluate(() => document.getElementById('end-message').textContent),
      await page.evaluate(() => document.getElementById('save').textContent)],
    [true, null, n === 1 ? 'أجبتَ عن سؤال واحد اليوم' : n === 2 ? 'أجبتَ عن سؤالين اليوم' : `أجبتَ عن ${n} أسئلة اليوم`, 'تم الحفظ']);
  await sameAsReplay(page, 'بعد S1');
}
await page.click('#exit');
await page.click('[data-child="young"]');
await page.waitForSelector('[data-screen="workshop"]');
check('في اليوم نفسه بعد ختم الجلسة: لا زر «ابدأ»', [await page.evaluate(() => Boolean(document.getElementById('start'))),
  await page.evaluate(() => Boolean(document.getElementById('done-today')))], [false, true]);
await page.close();

// ---------------------------------------------------------------- 5) يعود بعد الإغلاق
NOW.t = DAY0 + 86400000;
page = await open();
await page.click('[data-child="young"]');
await page.waitForSelector('[data-screen="workshop"]');
await press(page);
rStart(NOW.t);
// أول بند تعليم («جرّب أولًا»): يخطئ ثم يصيب (4.1 و10.3)
v = await shownItem(page);
{
  const it = inspect(v);
  rShow(v.id);
  await tick(page);
  const w = it.answer === 9 ? 8 : it.answer + 1;
  await type(page, w);
  await page.click('[data-key="ok"]');
  await page.waitForFunction(() => document.getElementById('answer').textContent === '' && document.querySelector('#model svg'));
  rEvent(['confirm', w], false);
  const m = await page.evaluate(() => ({ counters: Number(document.querySelector('#model svg').dataset.counters),
    red: [...document.querySelectorAll('.task *')].some((n) => /^rgb\((1[6-9]\d|2\d\d), \d?\d, \d?\d\)$/.test(getComputedStyle(n).color)),
    next: Boolean(document.getElementById('next')), said: window.MM_TEST.spoken.slice(-1)[0] }));
  await type(page, it.answer);
  await page.click('[data-key="ok"]');
  await page.waitForSelector('#next');
  const ok = await page.evaluate(() => Boolean(document.getElementById('ok')));
  rEvent(['confirm', it.answer], false);
  await page.click('#next');
  rEvent(['end'], true);
  await settled(page);
  const rec = (await dbRec(page)).records.find((r) => r.item === v.id && r.status === 'complete');
  check('خطأ أول في بند تعليم: لا علامة حمراء ولا «التالي»، ويعود الإطار مجهّزًا بالمسألة دون حلّها. ثم الصحيح: علامة ✓ و«التالي»، والسجل '
    + '«أول إجابة خاطئة بقيمتها، ونهائية صحيحة»، ولا تغيّر الثانيةُ صحة الأولى',
  [v.id, v.kind, m, ok, rec ? [rec.first, rec.final, rec.later.map((l) => l.correct), rec.values] : null],
  ['1-4-1/opening/01', 'teach', { counters: it.numbers.n, red: false, next: false, said: 'انظر إلى الإطار، وجرّب مرة أخرى' }, true,
    [false, 'correct', [true], [w, it.answer]]]);
}
const before = await play(page, { stopAt: 2 });   // يُعرض البند الثاني بعده ولا يُجاب
await tick(page);
await type(page, 1);                                                      // رقم مكتوب لم يؤكَّد
const ses = eng(await dbRec(page)).current;
const cut = before[1];
if (process.env.DEBUG) console.log('before', before, await scr(page));
await page.close();                                                       // إغلاق والبند الثاني معروض
page = await open();
await page.click('[data-child="young"]');
await page.waitForSelector('[data-screen="workshop"]');
check('بعد الإغلاق في اليوم نفسه والجلسة مفتوحة: «ابدأ» ظاهر', await page.evaluate(() => Boolean(document.getElementById('start'))), true);
await press(page);
rStart(NOW.t);
v = await shownItem(page);
{
  const rec = await dbRec(page);
  const r = rec.records.find((x) => x.item === cut && x.session === ses);
  const kind = BY.get(cut).role.split('.')[0];
  check('العودة تكمل الجلسة نفسها لا جلسة جديدة. البند الذي كان معروضًا محفوظ منقطعًا «غير محسوم» بلا إجابة (الرقم غير المؤكد لا يُحتسب)، '
    + 'ولا تُعرض هويته ثانية إن كان بند تقييم',
  [eng(rec).current, r ? [r.status, r.first, r.unsettled ?? false] : null,
    ['gate', 'short_check', 'check', 'deferred_check'].includes(kind) ? v.id !== cut : true],
  [ses, ['interrupted', null, true], true]);
}
await play(page);
await page.waitForSelector('[data-screen="end"]');
await sameAsReplay(page, 'بعد جلسة قُطعت بإغلاق');

// ---------------------------------------------------------------- 5ب) يريد أن يستمر (قرار الأب، 19 نوفمبر)
// القاعدة: الدرس اكتمل وثبت الفهم اليوم، فالمهارة تنتظر فحص استقلالها غدًا. الإضافية تعرض تدريبها مرة، ولا تقييم فيها
const PRACTICE = PACK.items.filter((i) => i.skill === '1-4-1' && ['practice', 'practice.more'].includes(i.role)).map((i) => i.id);   // 6 ثم 12
const moreBtn = (p) => p.evaluate(() => { const b = document.getElementById('more'); return b ? [b.dataset.plan, b.textContent] : null; });
check('ختام جلسة اليوم: يُعرض «تدريب أكثر»، ويُسأل الطفل بصوت «هل تريد المزيد؟»', [await moreBtn(page),
  (await page.evaluate(() => window.MM_TEST.spoken.slice(-1)[0])).endsWith('هل تريد المزيد؟')], [['practice', '▶ تدريب أكثر'], true]);
await page.click('#exit');
await page.click('[data-child="young"]');
await page.waitForSelector('[data-screen="workshop"]');
check('خرج ثم عاد في اليوم نفسه: لا «ابدأ»، و«تدريب أكثر» ما زال معروضًا', [await page.evaluate(() => Boolean(document.getElementById('start'))),
  await moreBtn(page)], [false, ['practice', '▶ تدريب أكثر']]);
await page.click('#more');
await page.waitForFunction(() => document.getElementById('app').dataset.screen !== 'workshop');
rStart(NOW.t, true);
const more1 = await play(page, { stopAt: 3 });                            // ثالث بنود التدريب معروض
{
  const rec = await dbRec(page), cur = eng(rec).current;
  check('الجلسة الإضافية: نوعها extra في يوم الأسرة نفسه، وبنودها تدريب 1-4-1 بترتيبه، بلا سجل تقييم',
    [eng(rec).sessions[cur].kind, eng(rec).sessions[cur].day, more1, rec.records.filter((x) => x.session === cur && !x.void).length],
    ['extra', DAYNUM + 1, PRACTICE.slice(0, 3), 0]);
  await page.close();                                                     // إغلاق في منتصف الإضافية
  page = await open();
  await page.click('[data-child="young"]');
  await page.waitForSelector('[data-screen="workshop"]');
  check('العودة والإضافية مفتوحة: «ابدأ» يكملها، لا «تدريب أكثر»', [await page.evaluate(() => Boolean(document.getElementById('start'))),
    await moreBtn(page)], [true, null]);
  await press(page);
  rStart(NOW.t);
  const more2 = await play(page);
  await page.waitForSelector('[data-screen="end"]');
  const rec2 = await dbRec(page);
  check('تُكمَل الإضافية نفسها من البند الذي أُغلق عليه حتى آخر التدريب، ثم لا يُعرض المزيد: ما عندنا اليوم انتهى',
    [more2, eng(rec2).sessions[cur].ended, eng(rec2).current, await moreBtn(page)], [PRACTICE.slice(2), true, null, null]);
  await sameAsReplay(page, 'بعد الإضافية');
}
await page.close();

// ---------------------------------------------------------------- 6) فشل الحفظ
NOW.t = DAY0 + 2 * 86400000;
page = await open();
await page.click('[data-child="young"]');
await page.waitForSelector('[data-screen="workshop"]');
await press(page);
rStart(NOW.t);
v = await shownItem(page);
const itF = inspect(v);
rShow(v.id);
{
  const r0 = await dbRec(page);
  await tick(page);
  await page.evaluate(() => { window.MM_TEST.fail = true; });
  const aF = v.kind === 'shown' || KNOWN.has(itF.skill) ? itF.answer : wrongOf(itF);
  if (v.kind === 'shown') {
    if (itF.role.startsWith('lesson')) KNOWN.add(itF.skill);
    if (itF.role !== 'lesson.watch') await type(page, itF.answer), await page.click('[data-key="ok"]');
    await page.click('#next');
  } else {
    await type(page, aF);
    await page.click('[data-key="ok"]');
  }
  await page.waitForSelector('[data-screen="call"]');
  const r1 = await dbRec(page);
  check('الكتابة تُلغى بعد إجابة: لا يُعرض بند جديد، ويظهر «نادِ أحد الكبار» بسبب الحفظ، والمحفوظ كما كان قبل الإجابة',
    [await page.evaluate(() => document.querySelector('.center').dataset.reason), canonical(r1) === canonical(r0)], ['save', true]);
  await pin(page);
  await page.click('#save-retry');
  await settled(page);
  if (v.kind === 'shown') rEvent(['end'], true);
  else if (v.kind === 'assess') rEvent(['confirm', aF], true);
  else rEvent(['confirm', aF], false);
  const r2 = await dbRec(page);
  check('البالغ يعيد المحاولة برمزه: تُحفظ الحالة التي بقيت في النافذة، ثم تتابع الشاشة', [r2.rev > r1.rev, canonical(strip(r2)) === canonical(R.rec),
    await scr(page)], [true, true, 'item']);
  if (v.kind === 'teach') {                                               // يكمل بند التعليم: يصيب إن كان أخطأ، ثم «التالي»
    if (aF !== itF.answer) {
      await type(page, itF.answer);
      await page.click('[data-key="ok"]');
      rEvent(['confirm', itF.answer], false);
    }
    await page.waitForSelector('#next');
    await page.click('#next');
    rEvent(['end'], true);
  }
}
// ---------------------------------------------------------------- 7) نافذة ثانية
{
  const other = await open();
  await other.click('[data-child="young"]');
  await other.waitForSelector('[data-screen="call"]');
  check('نافذة ثانية لملف الطفل نفسه: لا تفتحه، وتطلب بالغًا', await other.evaluate(() => document.querySelector('.center').dataset.reason),
    'other_window');
  await other.close();
}
await play(page);
await page.waitForSelector('[data-screen="end"]');
await sameAsReplay(page, 'بعد جلسة فشل فيها حفظ');
await page.close();

// ---------------------------------------------------------------- 8) أيام تالية: التعليم والخطأ فيه
const kinds = new Set(), acts = new Set();
for (let d = 3; d <= 45; d++) {
  NOW.t = DAY0 + d * 86400000;
  page = await open();
  await page.click('[data-child="young"]');
  await page.waitForSelector('[data-screen="workshop"]');
  if (!(await page.evaluate(() => Boolean(document.getElementById('start'))))) { await page.close(); continue; }
  await press(page);
  rStart(NOW.t);
  const seen = await play(page);
  for (const id of seen) { kinds.add(BY.get(id).role); acts.add(id.split('/')[1].replace(/[AB]$/, '')); }
  await page.waitForFunction(() => ['end', 'nothing'].includes(document.getElementById('app').dataset.screen));
  await sameAsReplay(page, `اليوم ${d + 1}`);
  await page.close();
}
check('الأيام التالية بلغت الدرس ودليل الفهم وفحص الاستقلال', ['lesson', 'evidence', 'check'].filter((a) => !acts.has(a)), []);
console.log('        أدوار البنود التي عُرضت في الأيام التالية: ' + [...kinds].sort().join('، ') + ' · الأنشطة: ' + [...acts].sort().join('، '));

// ---------------------------------------------------------------- 8ب) الكبيران في 3-5: ملف لكل طفل وقراراته
// القاعدة: القراران في 10.2 يُعرضان لكل طفل، ويسجّل البالغ منهما ما يراه. قرار المعلم يفتح التقدم وليس دليل إتقان.
// الطفل الأول يُسجَّل له القراران. الثاني يُسجَّل له 3-5-1 وحده، ثم 3-5-2 لاحقًا من مدخل البالغ.
const youngRev = (await (async () => { const p = await open(); const r = await dbRec(p); await p.close(); return r; })()).rev;
const setupOlder = async (child, picks) => {
  use(child);
  page = await open();
  await page.click(`[data-child="${child}"]`);
  await page.waitForSelector('[data-screen="call"]');
  await pin(page);
  for (const k of picks) await page.click('#dec-' + k);
  await page.fill('#decision-reason', 'تحديد نقطة البدء');
  await page.click('#setup-ok');
  await page.waitForSelector('[data-screen="workshop"]');
  rSetup('تحديد نقطة البدء', picks);
};
const opens = (rec) => eng(rec).decisions.filter((x) => x.kind === 'open').map((x) => [x.skills[0], x.bypass, x.reason]);
NOW.t = DAY0 + 50 * 86400000;
await setupOlder('older1', [0, 1]);
await sameAsReplay(page, 'ملف الطفل الأول');
await page.close();
await setupOlder('older2', [0]);
{
  const r1 = await dbRec(page, 'older1'), r2 = await dbRec(page, 'older2'), y = await dbRec(page);
  check('لكل طفل ملفه وقراراته: الأول بالقرارين، والثاني بقرار 3-5-1 وحده، وملف الصغير لم يُمسّ. ولا دليل إتقان في ملفيهما',
    [opens(r1), opens(r2), y.rev, eng(r1).evidence.length + eng(r2).evidence.length],
    [[['3-5-1', ['3-2-3', '3-3-2'], 'تحديد نقطة البدء'], ['3-5-2', ['2-5-2', '3-2-1', '3-3-1'], 'تحديد نقطة البدء']],
      [['3-5-1', ['3-2-3', '3-3-2'], 'تحديد نقطة البدء']], youngRev, 0]);
  await pin(page);
  const shownMade = await page.evaluate(() => [...document.querySelectorAll('#decisions .made')].map((n) => n.dataset.skill));
  await page.fill('#decide-reason', 'بعد أسبوع من المتابعة');
  await page.click('[data-decide="3-5-2"]');
  await page.waitForFunction(() => document.querySelectorAll('#decisions .made').length === 2);
  rDecide(1, 'بعد أسبوع من المتابعة');
  check('قرار لاحق من مدخل البالغ: يُسجَّل باسم مهارته وسببه، ويظهر «قرار معلم» مع السابق',
    [shownMade, opens(await dbRec(page, 'older2')).map((x) => [x[0], x[2]])],
    [['3-5-1'], [['3-5-1', 'تحديد نقطة البدء'], ['3-5-2', 'بعد أسبوع من المتابعة']]]);
  await sameAsReplay2('ملف الطفل الثاني بعد القرار اللاحق', 'older2');
}
await page.close();

// الطفل الأول يمضي أيامًا، ويطلب المزيد كلما عُرض عليه. خط الأعداد يُفحص في كل بند يُعرض (inspect)
use('older1');
const perfs = new Set(), olderActs = new Set();
let olderMore = 0;
for (let d = 50; d <= 58; d++) {
  NOW.t = DAY0 + d * 86400000;
  page = await open();
  await page.click('[data-child="older1"]');
  await page.waitForSelector('[data-screen="workshop"]');
  if (!(await page.evaluate(() => Boolean(document.getElementById('start'))))) { await page.close(); continue; }
  await press(page);
  rStart(NOW.t);
  let seen = await play(page);
  await page.waitForFunction(() => ['end', 'nothing'].includes(document.getElementById('app').dataset.screen));
  while (await page.evaluate(() => Boolean(document.getElementById('more')))) {
    await page.click('#more');
    await page.waitForFunction(() => document.getElementById('app').dataset.screen !== 'end');
    rStart(NOW.t, true);
    const extra = await play(page);
    olderMore += extra.length;
    seen = [...seen, ...extra];
    await page.waitForSelector('[data-screen="end"]');
  }
  for (const id of seen) { perfs.add(BY.get(id).performance); olderActs.add(BY.get(id).role.split('.')[0]); }
  await sameAsReplay2(`الطفل الأول، اليوم ${d - 49}`, 'older1');
  await page.close();
}
check('الطفل الأول بلغ الأداءات الأربعة على خط الأعداد، والمسألة السياقية، والحساب بلا نموذج، وفحص الاستقلال، وطلب المزيد',
  [['line_back', 'station_back', 'line_up', 'jump_missing', 'context_sub', 'solve'].filter((x) => !perfs.has(x)), olderActs.has('check'),
    olderMore > 0], [[], true, true]);
check('ملف الطفل الثاني وملف الصغير لم يتغيرا أثناء أيام الأول', [strip(await (async () => { const p = await open(); const r = await dbRec(p, 'older2');
  const y = await dbRec(p); await p.close(); return { ...r, y: y.rev }; })())], [{ ...RS.older2.rec, y: youngRev }]);

// ---------------------------------------------------------------- 9) بلا صوت عربي
page = await open({ stub: false });
await page.click('[data-child="young"]');
await page.waitForFunction(() => ['call', 'workshop'].includes(document.getElementById('app').dataset.screen), null, { timeout: 8000 });
check('متصفح بلا صوت عربي: لا يُترك الطفل الذي لا يقرأ وحده، ويُنادى بالغ', [await scr(page),
  await page.evaluate(() => document.querySelector('.center').dataset.reason ?? null)], ['call', 'audio']);
await page.click('#adult');
await page.click('#pin-cancel');
await page.waitForFunction(() => document.getElementById('app').dataset.screen !== 'pin');
check('«رجوع» من شاشة الرمز بلا رمز يعيد إلى «نادِ أحد الكبار»، لا إلى الورشة', [await scr(page),
  await page.evaluate(() => document.querySelector('.center').dataset.reason ?? null)], ['call', 'audio']);
await page.close();
page = await open({ stub: false });                                       // من يقرأ يمضي بلا صوت
await page.click('[data-child="older2"]');
await page.waitForFunction(() => ['call', 'workshop'].includes(document.getElementById('app').dataset.screen), null, { timeout: 8000 });
check('متصفح بلا صوت عربي والطفل يقرأ: يصل إلى الورشة بلا مناداة بالغ', await scr(page), 'workshop');
await page.close();

check('كل بند عُرض: نصه من المحتوى، ومعادلته من اليسار إلى اليمين، ونموذجه بأعداده، وصوته، وهوية الطفل، والشاشة لا تتمرر، ولا تغذية '
  + 'راجعة في التقييم', FAULTS, []);
check('لا خطأ في الصفحة', errors, []);
await browser.close();
server.close();
const okAll = results.every(Boolean);
console.log(okAll ? `نجحت الاختبارات كلها: ${results.length}` : `أخفق ${results.filter((x) => !x).length} من ${results.length}`);
process.exit(okAll ? 0 : 1);
