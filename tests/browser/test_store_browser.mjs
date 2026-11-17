// الحفظ الذرّي في متصفح حقيقي: Chrome و IndexedDB، بلا بديل محاكٍ للتخزين.
//
//     npm install                        (playwright-core: يقود Chrome المثبّت، ولا ينزّل متصفحًا)
//     node tests/browser/test_store_browser.mjs [مسار Chrome]
//
// يشغّل خادمًا محليًا للمستودع، ويشغّل Chrome بملف تعريف على القرص، ويفتح tests/browser/harness.html. كل حالة
// بقاعدة بيانات جديدة، ونتائجها المتوقعة مكتوبة هنا يدويًا من 9.2 ومن الضمانات في app/store.mjs. الأعطال حقيقية في
// آلية المتصفح: حصة تخزين مصغّرة عبر Chrome DevTools Protocol، وسجل يرفضه IndexedDB، وقتل عملية Chrome كلها
// (SIGKILL) داخل المعاملة وبعدها ثم تشغيله بملف التعريف نفسه، وإسقاط الصفحة (Page.crash).
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize, resolve } from 'node:path';
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { chromium } from 'playwright-core';

const ROOT = resolve(new URL('../..', import.meta.url).pathname);
const CHROME = process.argv[2] || '/usr/bin/google-chrome';
const TYPES = { '.html': 'text/html; charset=utf-8', '.mjs': 'text/javascript', '.js': 'text/javascript',
  '.json': 'application/json' };
const results = [];
const T0 = Date.now();
const dbg = process.env.DEBUG ? (m) => console.error(`[${((Date.now() - T0) / 1000).toFixed(1)}] ${m}`) : () => {};

function check(name, cond, detail = '') {
  results.push(Boolean(cond));
  console.log(`  ${cond ? 'نجح' : 'أخفق'}  ${results.length}. ${name}`);
  if (!cond && detail) console.log('        ' + String(detail).slice(0, 500));
}

const server = createServer(async (rq, rs) => {
  const path = normalize(join(ROOT, decodeURIComponent(new URL(rq.url, 'http://x').pathname)));
  if (!path.startsWith(ROOT)) { rs.writeHead(403).end(); return; }
  try {
    const body = await readFile(path);
    rs.writeHead(200, { 'content-type': TYPES[extname(path)] || 'application/octet-stream' }).end(body);
  } catch {
    rs.writeHead(404).end();
  }
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const ORIGIN = `http://127.0.0.1:${server.address().port}`;
const URL_ = `${ORIGIN}/tests/browser/harness.html`;

const PROFILE = mkdtempSync(join(tmpdir(), 'mm-profile-'));
let proc, browser, context;

// Chrome بملف تعريف على القرص، يُقاد عبر CDP. القتل بـ SIGKILL يحاكي إغلاق التطبيق أو انقطاع الجهاز فجأة
async function launch() {
  dbg('launch');
  const port = 9300 + Math.floor(Math.random() * 600);
  proc = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${PROFILE}`,
    '--no-first-run', '--disable-background-networking', '--disable-component-update', '--disable-sync', 'about:blank'],
  { stdio: 'ignore' });
  for (let i = 0; i < 100; i++) {
    try {
      browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
      break;
    } catch {
      await new Promise((r) => setTimeout(r, 100));
    }
  }
  context = browser.contexts()[0];
}

async function kill() {
  dbg('kill');
  const exited = new Promise((r) => proc.once('exit', r));
  proc.kill('SIGKILL');
  await exited;
  browser = null;
}

await launch();

async function open() {
  dbg('open');
  const page = await context.newPage();
  const statuses = [];
  page.on('console', (m) => {
    const t = m.text();
    if (t.startsWith('STATUS ')) statuses.push(JSON.parse(t.slice(7)));
  });
  await page.goto(URL_);
  dbg('loaded');
  await page.waitForFunction(() => window.ready === true);
  return { page, statuses };
}

console.log(`=== الحفظ الذرّي في Chrome ${browser.version()} (IndexedDB، ملف تعريف على القرص)`);

// الترتيب: امتلاء التخزين أولًا، لأن Chrome يطبّق الحصة المصغّرة على الأصل قبل أول استعمال لتخزينه في الجلسة.
// ثم الحالات التي لا تقتل Chrome، ثم التي تقتله وتعيد تشغيله.
// 2. امتلاء التخزين: حصة مصغّرة للأصل عبر CDP (200 كيلوبايت)، والسجل الأول أصغر منها
{
  const { page, statuses } = await open();
  const cdp = await context.newCDPSession(page);
  await cdp.send('Storage.overrideQuotaForOrigin', { origin: ORIGIN, quotaSize: 200000 });
  await page.evaluate(async () => {
    const { store, persist, setup } = window.H;
    window.db = await store.openDB('t2');
    window.st = setup();
    window.big = '';
    window.saver = new store.Saver(window.db, 'kid', () => ({ ...persist.snapshot(window.st.e, window.st.sc, null, 'kid'),
      pad: window.big }), { onStatus: (s) => console.log('STATUS ' + JSON.stringify(s)) });
    await window.saver.request();
  });
  const r = await page.evaluate(async () => {
    window.big = 'x'.repeat(4000000);           // سجل أكبر من الحصة
    let err = null;
    try { await window.saver.request(); } catch (x) { err = x.code; }
    const rec = await window.H.store.load(window.db, 'kid');
    return { err, rev: rec.rev, pad: rec.pad.length };
  });
  await cdp.send('Storage.overrideQuotaForOrigin', { origin: ORIGIN });
  const after = await page.evaluate(async () => {
    window.big = 'y';
    const res = await window.saver.request();
    const rec = await window.H.store.load(window.db, 'kid');
    return { res, rev: rec.rev, pad: rec.pad };
  });
  const sts = statuses.map((s) => s.status + (s.code ? ':' + s.code : '')).join();
  check('امتلاء التخزين: الكتابة تُرفض بـ quota، والسجل المحفوظ يبقى كما كان (rev 1)، ولا يظهر «تم الحفظ» لها بل '
    + '«فشل». وبعد عودة المساحة يكتب الطلب التالي أحدث حالة', r.err === 'quota' && r.rev === 1 && r.pad === 0
    && after.res.ok && after.rev === 2 && after.pad === 'y' && sts === 'saving,saved,saving,failed:quota,saving,saved',
  JSON.stringify({ r, after, sts }));
  await page.close();
}

// 1. حفظ ثم قراءة من اتصال آخر، و«تم الحفظ» بعد complete وحده
{
  const { page } = await open();
  const r = await page.evaluate(async () => {
    const { store, persist, setup } = window.H;
    const db = await store.openDB('t1');
    const other = await store.openDB('t1');
    const { e, sc } = setup();
    const seen = [];
    const saver = new store.Saver(db, 'kid', () => persist.snapshot(e, sc, null, 'kid'), {
      onStatus: (s) => { seen.push(s.status); },
    });
    const pAt = [];
    saver.onStatus = async (s) => {
      seen.push(s.status);
      if (s.status === 'saved') pAt.push((await store.load(other, 'kid'))?.rev ?? 0);   // اتصال آخر يرى السجل
    };
    const res = await saver.request();
    await new Promise((x) => setTimeout(x, 50));
    const rec = await store.load(other, 'kid');
    const back = window.H.reopen(rec);
    return { res, seen, pAt, rev: rec.rev, same: JSON.stringify(persist.snapshot(back.engine, back.scheduler, null, 'kid'))
      === JSON.stringify(persist.snapshot(e, sc, null, 'kid')), notes: back.notes, nrec: sc.records.length,
      recs: JSON.stringify(back.scheduler.records) === JSON.stringify(sc.records) };
  });
  check('حفظ أول: «جارٍ الحفظ» ثم «تم الحفظ» بعد اكتمال المعاملة، واتصال آخر يرى السجل عند «تم الحفظ» نفسه. والسجل '
    + `المقروء يُستعاد إلى الحالة نفسها حرفًا بحرف، ومعها سجلات البنود الـ${r.nrec} كما هي (R14-01)`,
  r.res.ok && r.res.rev === 1 && r.seen.join() === 'saving,saved' && r.pAt.join() === '1' && r.rev === 1 && r.same
    && r.notes.length === 0 && r.nrec > 0 && r.recs, JSON.stringify(r));
  await page.close();
}

// 3. فشل الكتابة: سجل لا يقبله IndexedDB (فيه دالة)، فيرفضه المتصفح نفسه
{
  const { page, statuses } = await open();
  const r = await page.evaluate(async () => {
    const { store, persist, setup } = window.H;
    const db = await store.openDB('t3');
    const st = setup();
    let poison = false;
    const saver = new store.Saver(db, 'kid', () => ({ ...persist.snapshot(st.e, st.sc, null, 'kid'),
      ...(poison ? { bad: () => 1 } : {}) }), { onStatus: (s) => console.log('STATUS ' + JSON.stringify(s)) });
    await saver.request();
    poison = true;
    st.sc.log.push([99, 'marker', '1-4-1']);
    let err = null;
    try { await saver.request(); } catch (x) { err = x.code; }
    const rec = await store.load(db, 'kid');
    poison = false;
    const res = await saver.request();
    const rec2 = await store.load(db, 'kid');
    return { err, rev: rec.rev, marker: rec.scheduler.state.log.some((x) => x[1] === 'marker'), res,
      rev2: rec2.rev, marker2: rec2.scheduler.state.log.some((x) => x[1] === 'marker') };
  });
  const sts = statuses.map((s) => s.status + (s.code ? ':' + s.code : '')).join();
  check('فشل الكتابة: يرفض المتصفح السجل، فتُلغى المعاملة، ويبقى السجل المحفوظ بلا التغيير الأخير، ويظهر «فشل» لا '
    + '«تم الحفظ». والطلب التالي يكتب الحالة كلها ومعها التغيير', r.err === 'write_failed' && r.rev === 1 && !r.marker
    && r.res.ok && r.rev2 === 2 && r.marker2 && sts === 'saving,saved,saving,failed:write_failed,saving,saved',
  JSON.stringify({ r, sts }));
  await page.close();
}

// 5. تكرار طلب الحفظ
{
  const { page } = await open();
  const r = await page.evaluate(async () => {
    const { store, persist, setup } = window.H;
    const db = await store.openDB('t5');
    const st = setup();
    const saver = new store.Saver(db, 'kid', () => persist.snapshot(st.e, st.sc, null, 'kid'));
    const ps = [];
    const marks = [];
    for (let i = 0; i < 30; i++) {
      st.sc.log.push([99, 'n' + i, '1-4-1']);
      ps.push(saver.request().then((x) => marks.push([i, x.rev])));
    }
    const settled = await Promise.allSettled(ps);
    const rejected = settled.filter((x) => x.status === 'rejected').length;
    const rec = await store.load(db, 'kid');
    const last = rec.scheduler.state.log.filter((x) => x[1].startsWith('n')).map((x) => x[1]);
    return { commits: saver.commits, rev: rec.rev, last, marks, done: saver.done, seq: saver.seq, rejected };
  });
  const lastOk = r.last.length === 30 && r.last[29] === 'n29';
  check('ثلاثون طلب حفظ متتاليًا مع تغيّر الحالة: لا تُكتب معاملتان معًا، والطلبات المتراكمة تُكتب معًا، فالمعاملات '
    + `${r.commits} لا ثلاثون. كل وعد تحقق بعد كتابة تشمل حالته، والسجل الأخير يحمل التغييرات الثلاثين كلها`,
  r.commits >= 2 && r.commits < 30 && r.rev === r.commits && lastOk && r.done === 30 && r.seq === 30
    && r.marks.length === 30 && r.rejected === 0, JSON.stringify(r));
  await page.close();
}

// 6. نافذتان على ملف الطفل نفسه
{
  const A = await open(), B = await open();
  const ra = await A.page.evaluate(async () => {
    const { store, persist, setup } = window.H;
    window.db = await store.openDB('t6');
    window.st = setup();
    window.release = await store.claimWriter('kid6');
    window.saver = new store.Saver(window.db, 'kid6', () => persist.snapshot(window.st.e, window.st.sc, null, 'kid6'));
    await window.saver.request();
    return { got: window.release !== null };
  });
  const rb = await B.page.evaluate(async () => {
    const { store, persist } = window.H;
    window.db = await store.openDB('t6');
    const got = await store.claimWriter('kid6');
    const rec = await store.load(window.db, 'kid6');
    window.rec = rec;
    return { got: got !== null, rev: rec.rev };
  });
  await A.page.evaluate(async () => {
    window.st.sc.log.push([99, 'fromA', '1-4-1']);
    await window.saver.request();
  });
  const forced = await B.page.evaluate(async () => {
    // النافذة الثانية تتجاوز القفل وتكتب على ما قرأته (rev 1)، وقد كتبت الأولى بعده
    const { store } = window.H;
    const s = new store.Saver(window.db, 'kid6', () => ({ ...window.rec, scheduler: { ...window.rec.scheduler, b: 1 } }),
      { rev: window.rec.rev });
    let err = null;
    try { await s.request(); } catch (x) { err = x.code; }
    const again = await s.request().catch((x) => x.code);
    const now = await store.load(window.db, 'kid6');
    return { err, again, rev: now.rev, fromA: now.scheduler.state.log.some((x) => x[1] === 'fromA'), b: 'b' in now.scheduler };
  });
  await A.page.close();
  await new Promise((x) => setTimeout(x, 200));
  const after = await B.page.evaluate(async () => {
    const { store, persist } = window.H;
    const got = await store.claimWriter('kid6');
    const rec = await store.load(window.db, 'kid6');
    const back = window.H.reopen(rec);
    const s = new store.Saver(window.db, 'kid6', () => persist.snapshot(back.engine, back.scheduler, null, 'kid6'),
      { rev: rec.rev });
    const res = await s.request();
    return { got: got !== null, res };
  });
  check('نافذتان على الطفل نفسه: الأولى تحجز الكتابة والثانية للقراءة. وإن تجاوزت الثانية القفل وكتبت على سجل قرأته '
    + 'قبل كتابة الأولى رُفضت بـ conflict وصارت للقراءة وحدها، ولم يتغير ما كتبته الأولى. وبعد إغلاق الأولى تحجز '
    + 'الثانية الكتابة وتقرأ السجل الأخير ثم تكتب بعده', ra.got && !rb.got && rb.rev === 1 && forced.err === 'conflict'
    && forced.again === 'read_only' && forced.rev === 2 && forced.fromA && !forced.b && after.got && after.res.ok
    && after.res.rev === 3, JSON.stringify({ ra, rb, forced, after }));
  await B.page.close();
}

// 8. استثناء في صنع اللقطة أو في دالة العرض (R14-03)
{
  const { page } = await open();
  const r = await page.evaluate(async () => {
    const { store, persist, setup } = window.H;
    const db = await store.openDB('t8');
    const st = setup();
    let failSnap = true, failStatus = 0;
    const seen = [];
    const saver = new store.Saver(db, 'kid8', () => {
      if (failSnap) { failSnap = false; throw new Error('منشئ اللقطة فشل'); }
      return persist.snapshot(st.e, st.sc, null, 'kid8');
    }, { onStatus: (s) => {
      seen.push(s.status + (s.code ? ':' + s.code : ''));
      if (s.status === 'saving' && failStatus++ === 0) throw new Error('دالة العرض فشلت');
    } });
    const within = (p) => Promise.race([p.then((x) => ({ ok: true, rev: x.rev }), (x) => ({ ok: false, code: x.code })),
      new Promise((res) => setTimeout(() => res({ pending: true }), 2000))]);
    const first = await within(saver.request());
    const runningAfter = saver.running;
    const second = await within(saver.request());
    const rec = await store.load(db, 'kid8');
    return { first, runningAfter, second, rev: rec ? rec.rev : 0, seen, waiting: saver.waiting.length,
      statusErrors: saver.statusErrors || 0 };
  });
  check('منشئ لقطة يفشل مرة ثم يعمل: يُرفض الطلب الأول بـ snapshot_failed ويظهر «فشل»، ويعود الكاتب غير مشغول. ثم ينجح '
    + 'طلب تالٍ على IndexedDB وتُحسم وعوده، ولو رمت دالة العرض استثناءً عند «جارٍ الحفظ»',
  r.first.code === 'snapshot_failed' && r.runningAfter === false && r.second.ok && r.second.rev === 1 && r.rev === 1
    && r.waiting === 0 && r.seen.join() === 'failed:snapshot_failed,saving,saved' && r.statusErrors === 1,
  JSON.stringify(r));
  await page.close();
}

// 4. إغلاق التطبيق قبل اكتمال المعاملة، وبعده: قتل عملية Chrome كلها، ثم تشغيله بملف التعريف نفسه
for (const when of ['before', 'after']) {
  const { page, statuses } = await open();
  await page.evaluate(async (name) => {
    const { store, persist, setup } = window.H;
    window.db = await store.openDB(name);
    const st = setup();
    window.st = st;
    window.hooks = {};
    window.saver = new store.Saver(window.db, 'kid4', () => persist.snapshot(st.e, st.sc, null, 'kid4'), {
      onStatus: (s) => console.log('STATUS ' + JSON.stringify(s)), hooks: window.hooks });
    await window.saver.request();
  }, 't4' + when);
  if (when === 'before') {
    // داخل المعاملة وقبل الكتابة: انشغال ثلاث ثوانٍ، والعملية تُقتل في منتصفه
    page.evaluate(() => {
      window.hooks.beforePut = () => { const t = Date.now(); while (Date.now() - t < 3000) { /* انشغال */ } };
      window.st.sc.log.push([99, 'second', '1-4-1']);
      window.saver.request();
    }).catch(() => {});
    await new Promise((x) => setTimeout(x, 800));
  } else {
    await page.evaluate(async () => {
      window.st.sc.log.push([99, 'second', '1-4-1']);
      await window.saver.request();
    });
  }
  await kill();
  await launch();
  const { page: p2 } = await open();
  const r = await p2.evaluate(async (name) => {
    const db = await window.H.store.openDB(name);
    const rec = await window.H.store.load(db, 'kid4');
    const back = window.H.reopen(rec);
    return { rev: rec.rev, second: rec.scheduler.state.log.some((x) => x[1] === 'second'), notes: back.notes };
  }, 't4' + when);
  const savedRevs = statuses.filter((s) => s.status === 'saved').map((s) => s.rev);
  const ok = when === 'before'
    ? r.rev === 1 && !r.second && savedRevs.join() === '1'
    : r.rev === 2 && r.second && savedRevs.join() === '1,2';
  check(when === 'before'
    ? 'قتل Chrome داخل المعاملة قبل اكتمالها، ثم تشغيله بملف التعريف نفسه: يُقرأ السجل السابق كاملًا (rev 1) بلا '
      + 'التغيير الأخير، ولم يظهر «تم الحفظ» للكتابة الثانية، والسجل يُستعاد متسقًا'
    : 'قتل Chrome بعد «تم الحفظ»، ثم تشغيله: يُقرأ السجل الجديد (rev 2) بالتغيير الأخير، فما أُقرّ حفظه باقٍ',
  ok && Array.isArray(r.notes), JSON.stringify({ r, savedRevs }));
  await p2.close();
}

// 7. الإجابة الجارية وأحداث الدعم: إغلاق بعد طلب دعم في الخانة السادسة، ثم إعادة الفتح
{
  const { page } = await open();
  await page.evaluate(async () => {
    const { store, persist, midCheck } = window.H;
    const db = await store.openDB('t7');
    const { e, sc, current } = midCheck([['support', 'hint']]);
    const saver = new store.Saver(db, 'kid7', () => persist.snapshot(e, sc, current, 'kid7'));
    await saver.request();
  });
  const cdp = await context.newCDPSession(page);
  // تنهار الصفحة، ثم تُقتل العملية كلها. Page.crash لا يجيب: الصفحة انهارت، فيُنتظر قليلًا ثم يُمضى
  await Promise.race([cdp.send('Page.crash').catch(() => {}), new Promise((x) => setTimeout(x, 500))]);
  await kill();
  await launch();
  const { page: p2 } = await open();
  const r = await p2.evaluate(async () => {
    const db = await window.H.store.openDB('t7');
    const rec = await window.H.store.load(db, 'kid7');
    const back = window.H.reopen(rec);
    const entry = back.scheduler.entry('check', '1-4-1');
    back.scheduler.follow_learning();
    const res = back.engine.s.log.filter((x) => x.type === 'independence_result')
      .map((x) => [x.session, x.check_id, x.result, x.items.length]);
    return { journal: rec.current.journal.raw, notes: back.notes, items: entry.items.length, result: entry.act.result,
      unsettled: back.scheduler.records.at(-1).unsettled, res };
  });
  check('أحداث البند الجاري تُحفظ فور وقوعها: طلب الدعم في الخانة السادسة محفوظ في journal. بعد إسقاط الصفحة وإعادة '
    + 'فتحها يُختم البند بانقطاع «غير محسوم» ومعه الدعم، فتنتهي المحاولة «بطلب دعم» كما في بايثون، وتُختم S4، ويصدر '
    + 'حدث المحاولة الأصلية في S5 بالخانات الست', JSON.stringify(r.journal) === '[["support","hint"]]'
    && JSON.stringify(r.notes) === JSON.stringify([['unsettled_item', '1-4-1', '1-4-1/checkA/11', 'help'],
      ['current_saved', 'check', '1-4-1'], ['session_closed', 'S4']])
    && r.items === 6 && r.result === 'help' && r.unsettled === true
    && JSON.stringify(r.res) === JSON.stringify([['S5', '1-4-1/check/1', 'help', 6]]), JSON.stringify(r));
  await p2.close();
}

await kill();
rmSync(PROFILE, { recursive: true, force: true });
server.close();
console.log(results.every(Boolean) ? `نجحت الاختبارات كلها: ${results.length}` : 'أخفق اختبار');
process.exit(results.every(Boolean) ? 0 : 1);
