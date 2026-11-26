// أنواع الإجابة في الشاشة (5.3)، من أزرار الواجهة على مهارة حقيقية لكل نوع في المحتوى.
//
//     node tests/browser/test_answers_browser.mjs [مسار Chrome]
//
// لكل نوع جواب غير العدد الصحيح والبطاقة (ج2 إلى ج7) تُختار أول مهارة في المحتوى بنود درسها منه. في Node يمضي طفل كبير
// يعرف كل شيء إلا تلك المهارة، يومًا بعد يوم، حتى يُطلب أول بند منها، ويُحفظ سجله. ثم في Chrome يفتح الطفل ملفه ويجيب
// عن بنود المهارة حتى نهاية الجلسة. المتوقع من 5.3 ومن قاعدة التغذية الراجعة (4.1)، قبل التشغيل:
//  1. بند الشرح يعرض الجواب بصيغة نوعه (format)، وخانة الإجابة معطّلة.
//  2. في بند يُجاب: الجواب الخاطئ من النوع نفسه لا يُقبل وتُمسح الخانة (أو الخانتان)، والصحيح يُقبل (✓).
//  3. في بند تقييم: القيمة المرسلة في السجل هي ما كُتب بنوعه (زوج، أو نص عشري)، وحكمها same.
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { readFileSync } from 'node:fs';
import { extname, join, normalize, resolve } from 'node:path';
import { chromium } from 'playwright-core';
import { Engine, canonical } from '../../app/engine.mjs';
import { Scheduler } from '../../app/scheduler.mjs';
import { ContentSource, same } from '../../app/items.mjs';
import { Stepper } from '../../app/stepper.mjs';
import { PROFILES, TZ } from '../../app/ui/config.mjs';
import { familyDay } from '../../app/ui/link.mjs';
import { format } from '../../app/ui/answers.mjs';
import { rightOf, wrongOf, type, emptied } from './answer_input.mjs';

const ROOT = resolve(new URL('../..', import.meta.url).pathname);
const CHROME = process.argv[2] || '/usr/bin/google-chrome';
const PACK = JSON.parse(readFileSync(join(ROOT, 'slice-content.json'), 'utf8'));
const IDENT = { version: PACK.version, digest: PACK.digest };
const BY = new Map(PACK.items.map((i) => [i.id, i]));
const P = PROFILES.older1;
const results = [];
function check(name, got, want) {
  const ok = canonical(got) === canonical(want);
  results.push(ok);
  console.log(`  ${ok ? 'نجح' : 'أخفق'}  ${results.length}. ${name}`);
  if (!ok) console.log(`        المتوقع ${JSON.stringify(want).slice(0, 600)}\n        الناتج  ${JSON.stringify(got).slice(0, 600)}`);
}

// أول مهارة في نطاق الكبير لكل نوع جواب
const TARGETS = [];
for (const code of ['ج2', 'ج3', 'ج4', 'ج5', 'ج6', 'ج7']) {
  const it = PACK.items.find((i) => i.answer_type === code && i.group === 'lesson' && P.scope.includes(i.skill));
  if (it) TARGETS.push([code, it.skill]);
}

// Node: الطفل يعرف كل ما في نطاقه إلا T، حتى يُطلب أول بند من T
const DAY0 = Date.UTC(2026, 9, 1, 8);
function prepare(T) {
  const e = new Engine(undefined, { group: P.group });
  P.decisions.forEach((d, k) => e.apply({ id: 'd' + k, type: 'teacher_open', skill: d.skill, bypass: d.bypass, reason: 'x' }));
  const src = new ContentSource(PACK.items, true, IDENT);
  let secs = 0;
  const sc = new Scheduler(e, P.types, (k, w) => src.pick(k, w), null, { group: P.group, scope: P.scope, learning: true,
    cap: P.cap, item_seconds: () => { const x = secs; secs = 0; return x; }, records: [], retention: true, content: IDENT,
    day_cap: P.day_cap });
  for (let d = 0; d < 120; d++) {
    const now = DAY0 + d * 86400000;
    sc.today = familyDay(now, TZ);
    for (let k = 0; k < 8; k++) {
      if (k > 0 && !(sc.cur === null && (sc.start_at === null || sc.more()))) break;
      const st = new Stepper(e, sc, () => now);
      st.open(sc.g_session());
      if (st.pending === null) { sc.practiced(null, true); break; }
      while (st.pending !== null) {
        const [item, w] = st.pending;
        if (item.skill === T) return { rec: st.snapshot('older1'), now, first: item.id };
        st.show(st.seq);
        const a = w.activity, role = BY.get(item.id).role;
        if (role.startsWith('lesson') || role.startsWith('practice')) { secs = 10; st.event(st.seq, ['end']); continue; }
        const v = item.cards ? item.answer : rightOf(item);
        secs = 10;
        st.event(st.seq, ['confirm', v]);
        if (!['gate', 'short', 'check', 'retention', 'describe', 'ready'].includes(a)) st.event(st.seq, ['end']);
      }
    }
  }
  throw new Error('لم يُطلب بند من ' + T);
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
const errors = [];
console.log(`=== أنواع الإجابة في الشاشة، Chrome ${browser.version()}: ${TARGETS.map(([c, s]) => c + ' ' + s).join('، ')}`);
check('في المحتوى مهارة لكل نوع جواب بُني حتى الآن (ج4 على الأقل)', TARGETS.some(([c]) => c === 'ج4'), true);

for (const [code, T] of TARGETS) {
  const { rec, now, first } = prepare(T);
  const context = await browser.newContext({ viewport: { width: 1180, height: 820 }, hasTouch: true });
  const page = await context.newPage();
  page.on('pageerror', (x) => errors.push(x.message));
  page.on('console', (m) => { if (m.type() === 'warning') errors.push('console: ' + m.text()); });
  await page.addInitScript((t) => {
    const M = { spoken: [], clock: { now: t, mono: 0 }, noWorker: true };
    M.now = () => M.clock.now; M.mono = () => M.clock.mono;
    M.speaker = { available: async () => true, say: (x) => M.spoken.push(x) };
    window.MM_TEST = M;
  }, now);
  await page.goto(`http://127.0.0.1:${server.address().port}/app/index.html`);
  await page.waitForSelector('[data-screen="who"]');
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
  const seen = [], bad = [];
  let sessions = 0;
  for (let n = 0; n < 160; n++) {
    await page.waitForFunction(() => {
      const a = document.getElementById('app').dataset.screen, t = document.querySelector('.task');
      return a !== 'workshop' && (a !== 'item' || (t && t.dataset.ready === 'true'));
    }).catch(async (x) => {
      const st = await page.evaluate(() => [document.getElementById('app').dataset.screen, document.querySelector('.task')?.dataset.item,
        document.getElementById('app').textContent.slice(0, 300)]);
      throw new Error(`${x.message}: ${JSON.stringify(st)} ${errors.join(' | ')}`);
    });
    if (await page.evaluate(() => document.getElementById('app').dataset.screen) !== 'item') {
      // الجلسة انتهت: «تابع» إلى الجلسة التالية في اليوم نفسه حتى يبلغ درس المهارة (البوابة أُخطئ فيها)
      if (!seen.some(([r]) => r === 'lesson.watch') && sessions < 3 && await page.$('#more')) {
        sessions += 1;
        await page.click('#more');
        await page.waitForFunction(() => document.getElementById('app').dataset.screen !== 'end');
        continue;
      }
      break;
    }
    const [id, kind] = await page.evaluate(() => [document.querySelector('.task').dataset.item, document.querySelector('.task').dataset.kind]);
    const it = BY.get(id);
    await page.evaluate(() => { window.MM_TEST.clock.mono += 10000; });
    if (it.skill !== T) {                       // مهارة أخرى في الجلسة: جواب صحيح، بلا حكم في هذا الاختبار
      if (it.role === 'lesson.watch') { await page.click('#next'); continue; }
      if (it.cards) await page.click(`#cards [data-card="${it.answer}"]`);
      else { await type(page, rightOf(it)); await page.click('[data-key="ok"]'); }
      if (kind !== 'assess') { await page.waitForSelector('#next'); await page.click('#next'); }
      else if (it.how) await page.click('#how [data-how="back"]');
      continue;
    }
    seen.push([it.role, kind]);
    if (it.role === 'lesson.watch') {
      const shown = await page.textContent('#answer');
      if (shown !== format(it.answer, 'ar')) bad.push(['الشرح يعرض الجواب بصيغة نوعه', id, shown, format(it.answer, 'ar')]);
      await page.click('#next');
      continue;
    }
    if (it.cards) {
      await page.click(`#cards [data-card="${it.answer}"]`);
      if (kind !== 'assess') { await page.waitForSelector('#next'); await page.click('#next'); }
      continue;
    }
    if (kind === 'assess') {                    // البوابة خطأً بنوع الجواب، فيلزم الدرس. وغيرها صحيحًا
      await type(page, it.group === 'gate' ? wrongOf(it) : rightOf(it));
      await page.click('[data-key="ok"]');
      if (it.how) await page.click('#how [data-how="back"]');
      continue;
    }
    // بند يُجاب بتغذية راجعة: خاطئ من النوع نفسه، ثم صحيح
    const w = wrongOf(it);
    if (same(w, it.answer)) bad.push(['الخاطئ في الاختبار ليس خاطئًا', id, w]);
    await type(page, w);
    await page.click('[data-key="ok"]');
    await emptied(page).catch(() => bad.push(['الخاطئ لا يُقبل وتُمسح الخانة', id]));
    if (await page.$('#ok')) bad.push(['الخاطئ قُبل', id]);
    await type(page, rightOf(it));
    await page.click('[data-key="ok"]');
    await page.waitForSelector('#ok', { timeout: 5000 }).catch(() => bad.push(['الصحيح لم يُقبل', id, rightOf(it)]));
    await page.click('#next');
  }
  check(`${code} في ${T}: البوابة خطأً ثم «تابع» إلى درسها: الشرح بصيغة النوع، والخطأ يُمسح، والصحيح يُقبل (5.3 و4.1)`,
    [seen.some(([r]) => r === 'lesson.watch'), seen.some(([r, k]) => k === 'teach' && !BY.get(first).cards), bad], [true, true, []]);
  console.log(`        ${seen.map(([r, k]) => r + '/' + k).join(' ← ')}`);
  // ما حُفظ: قيم التأكيد بنوعها في سجل البنود
  const recs = await page.evaluate(async () => {
    const s = await import('/app/store.mjs');
    const db = await s.openDB();
    const r = await s.load(db, 'older1');
    db.close();
    return r.records;
  });
  const typed = recs.filter((r) => BY.get(r.item)?.skill === T && BY.get(r.item)?.answer_type === code)
    .flatMap((r) => (r.values ?? []).map((v) => [r.item, v]));
  check(`${code}: قيم التأكيد في السجل بنوع الجواب، وحكمها same`, typed.length > 0 && typed.every(([i, v]) =>
    typeof same(v, BY.get(i).answer) === 'boolean' && (Array.isArray(v) || typeof v === 'string' || Number.isInteger(v))), true);
  await context.close();
}
check('لا خطأ في الصفحة', errors, []);
await browser.close();
server.close();
console.log(results.every(Boolean) ? `نجحت الاختبارات كلها: ${results.length}` : `النتيجة: نجح ${results.filter(Boolean).length} من ${results.length}`);
process.exit(results.every(Boolean) ? 0 : 1);
