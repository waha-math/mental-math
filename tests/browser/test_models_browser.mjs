// كل نموذج مرسوم في المحتوى، بند واحد لكل (مهارة، أداء): يُرسم في Chrome بلا خطأ، وله مساحة، ولا يُكتب عليه جواب البند
// (إلا خط التقريب: العشرتان مكتوبتان والجواب إحداهما)، وما يُكتب عليه في data-shown هو نصوصه فعلًا. ولقطة لكل نوع
// في /tmp/models-<kind>.png للنظر
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { readFileSync } from 'node:fs';
import { extname, join, normalize, resolve } from 'node:path';
import { chromium } from 'playwright-core';

const ROOT = resolve(new URL('../..', import.meta.url).pathname);
const CHROME = process.argv[2] || '/usr/bin/google-chrome';
const PACK = JSON.parse(readFileSync(join(ROOT, 'slice-content.json'), 'utf8'));
const MIME = { '.html': 'text/html', '.mjs': 'text/javascript', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json' };
const server = createServer(async (req, res) => {
  const p = normalize(join(ROOT, decodeURIComponent(new URL(req.url, 'http://x').pathname)));
  if (!p.startsWith(ROOT)) { res.writeHead(403); res.end(); return; }
  try { const b = await readFile(p); res.writeHead(200, { 'content-type': MIME[extname(p)] ?? 'application/octet-stream' }); res.end(b); }
  catch { res.writeHead(404); res.end(); }
}).listen(0);
const port = server.address().port;

const seen = new Set(), sample = [];
for (const it of PACK.items) {
  if (!it.model || !it.model.kind) continue;
  // ولكل شكل مختلف من الرسم الواحد بندٌ: نصف الخلية في شبكة المئة، واتجاه منزلق المنازل
  const k = it.skill + '|' + it.performance + (it.model.kind === 'grid100' && it.model.n % 1 ? '|half' : '')
    + (it.model.kind === 'places' && it.model.point ? '|' + Math.sign(it.model.shift) : '');
  if (seen.has(k)) continue;
  seen.add(k);
  sample.push(it);
}
const results = [];
const check = (name, ok, info = '') => { results.push(ok); console.log(`  ${ok ? 'نجح' : 'أخفق'}  ${results.length}. ${name}${ok ? '' : '  ' + info}`); };

const browser = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 800, height: 600 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
await page.goto(`http://127.0.0.1:${port}/app/index.html?blank`, { waitUntil: 'domcontentloaded' }).catch(() => {});
await page.setContent(`<html><head><link rel="stylesheet" href="http://127.0.0.1:${port}/app/ui/style.css"></head>
  <body style="background:#fff"><div id="g" style="display:flex;flex-wrap:wrap;gap:8px"></div></body></html>`);
const out = await page.evaluate(async ([url, items]) => {
  const { modelFor } = await import(url);
  const g = document.getElementById('g');
  return items.map((it) => {
    try {
      const svg = modelFor(it);
      const box = document.createElement('div');
      box.style.cssText = 'width:360px;height:220px;border:1px solid #ccc;display:flex;align-items:center;justify-content:center';
      box.dataset.kind = it.model.kind;
      box.append(svg);
      g.append(box);
      const r = svg.getBoundingClientRect();
      const texts = [...svg.querySelectorAll('text')].map((t) => t.textContent);
      // الخلايا الملوّنة: كاملة ونصفية بعرضها نسبةً إلى الخلية، وكل شبكة على حدة بموضعها الأفقي (شبكتا المقارنة)
      const cells = [...svg.querySelectorAll('rect.cell')].map((c) => ({ x: +c.getAttribute('x'), w: +c.getAttribute('width'),
        h: +c.getAttribute('height'), on: c.classList.contains('on'), half: c.classList.contains('half') }));
      // الأرقام في جدول المنازل والفاصلة: موضع كل رقم أفقيًا، وموضع النقطة
      const digitsX = [...svg.querySelectorAll('text.num')].map((t) => [t.textContent, +t.getAttribute('x')]);
      const point = svg.querySelector('circle.point') ? +svg.querySelector('circle.point').getAttribute('cx') : null;
      // العقربان: زاوية كل منهما من الثانية عشرة باتجاه عقارب الساعة، مقيسة من إحداثيات الخط المرسوم
      const hands = [...svg.querySelectorAll('line.hand')].map((l) => {
        const [x1, y1, x2, y2] = ['x1', 'y1', 'x2', 'y2'].map((a) => +l.getAttribute(a));
        return [l.classList.contains('hour') ? 'hour' : 'minute', ((Math.atan2(x2 - x1, y1 - y2) * 180 / Math.PI) + 360) % 360,
          Math.hypot(x2 - x1, y2 - y1)];
      });
      return { id: it.id, kind: it.model.kind, w: r.width, h: r.height, texts, shown: svg.dataset.shown ?? null, cls: svg.getAttribute('class'), hands, cells, digitsX, point, w0: +svg.getAttribute('viewBox').split(' ')[2] };
    } catch (e) { return { id: it.id, kind: it.model.kind, err: String(e) }; }
  });
}, [`http://127.0.0.1:${port}/app/ui/models.mjs`, sample]);

const by = new Map(sample.map((it) => [it.id, it]));
const canonical12 = (a) => JSON.stringify([...a].sort());
const kinds = new Set();
for (const o of out) {
  const it = by.get(o.id);
  kinds.add(o.kind);
  if (o.err) { check(`${o.id} (${o.kind}) يُرسم`, false, o.err); continue; }
  const bad = [];
  if (!(o.w > 50 && o.h > 30)) bad.push('بلا مساحة');
  if (!o.cls.includes('k-' + o.kind)) bad.push('صنف الرسم');
  // الجواب مكتوب إن ظهر على الرسم وليس عددًا معطى في البند (2 − 1: الجزء المعطى 1 هو الجواب أيضًا، وهذا ليس كشفًا)
  const given = new Set([...Object.values(it.numbers), it.model.start, it.model.part].filter((v) => v !== undefined).map(String));
  if (o.kind !== 'round' && o.texts.includes(String(it.answer)) && !given.has(String(it.answer))) bad.push('الجواب مكتوب على الرسم');
  const shown = JSON.stringify(JSON.parse(o.shown));
  const vals = [];
  (function walk(v) { if (Array.isArray(v)) v.forEach(walk); else if (v && typeof v === 'object') Object.values(v).forEach(walk); else if (typeof v === 'string' && v) vals.push(v); })(JSON.parse(o.shown));
  if (vals.some((v) => !o.texts.includes(v))) bad.push('data-shown يذكر نصًّا غير مرسوم: ' + shown);
  if (o.kind === 'grid100' && !it.model.ra) {
    // المتوقع من n: floor(n) خلية كاملة ملوّنة، ونصف خلية بعرض (n mod 1) من الخلية إن كان كسرًا
    const full = o.cells.filter((c) => c.on && !c.half).length, half = o.cells.filter((c) => c.half);
    const n = it.model.n, cw = o.cells[0].h;
    if (full !== Math.floor(n) || half.length !== (n % 1 ? 1 : 0) || (half.length && Math.abs(half[0].w - cw * (n % 1)) > 0.01)) {
      bad.push(`خلايا الشبكة: ${full} كاملة و${half.length} نصفية، والمتوقع ${n}`);
    }
  }
  if (o.kind === 'grids') {
    // المتوقع: شبكة البطاقة الأولى يمينًا، وفي كلٍّ خلاياها، وتحت كلٍّ عددها
    const m = it.model, mid = Math.max(...o.cells.map((c) => c.x)) / 2;
    const right = o.cells.filter((c) => c.x > mid && c.on).length, left = o.cells.filter((c) => c.x <= mid && c.on).length;
    if (right !== m.cells[0] || left !== m.cells[1]) bad.push(`خلايا الشبكتين: ${right} و${left}، والمتوقع ${m.cells}`);
  }
  if (o.kind === 'places') {
    // المتوقع: كل رقم في منزلته (العدد الصحيح آحاده في آخر عمود)، والإزاحة تبقى داخل الجدول
    const m = it.model, c = 84, cols = Math.round((o.w0 - 40) / c), p = m.point ?? 0, sh = m.shift ?? 0;
    const firstCol = Math.round((o.digitsX[0][1] - 20 - c / 2) / c), lastCol = firstCol + m.digits.length - 1;
    const onesCol = lastCol - p;
    const wantOnes = p ? cols - 1 - p - Math.max(-sh, 0) : cols - 1;
    if (onesCol !== wantOnes || firstCol - Math.max(sh, 0) < 0 || lastCol - Math.min(sh, 0) > cols - 1 + (p ? 0 : 99)) {
      bad.push(`المنازل: الآحاد في العمود ${onesCol} والمتوقع ${wantOnes}، والإزاحة ${sh} من ${cols} أعمدة`);
    }
  }
  if (o.kind === 'places' && it.model.point) {
    // المتوقع: الرقم الأخير قبل الفاصلة عن يسار النقطة، وأرقام الكسر عن يمينها، والناتج غير مكتوب
    const m = it.model, xs = o.digitsX.map(([, x]) => x), intLen = m.digits.length - m.point;
    if (!(xs.slice(0, intLen).every((x) => x < o.point) && xs.slice(intLen).every((x) => x > o.point))) {
      bad.push('الفاصلة: ' + JSON.stringify([o.digitsX, o.point]));
    }
  }
  if (o.kind === 'clock') {
    // المتوقع من الوقت: الطويل 6 درجات لكل دقيقة، والقصير 30 لكل ساعة ونصف درجة لكل دقيقة، والقصير أقصر
    const m = it.model, want = { minute: m.m * 6, hour: ((m.h % 12) * 30 + m.m * 0.5) % 360 };
    const got = Object.fromEntries(o.hands.map(([k, a, len]) => [k, [a, len]]));
    const near = (a, b) => Math.min(Math.abs(a - b), 360 - Math.abs(a - b)) < 0.5;
    if (o.hands.length !== 2 || !near(got.minute[0], want.minute) || !near(got.hour[0], want.hour)
      || !(got.hour[1] < got.minute[1])) bad.push('العقربان: ' + JSON.stringify(o.hands));
    if (canonical12(o.texts) !== canonical12(Array.from({ length: 12 }, (_, j) => String(j + 1)))) bad.push('أرقام الوجه');
  }
  check(`${o.id} (${o.kind})`, bad.length === 0, bad.join('، '));
}
for (const k of kinds) {
  const els = await page.$$(`#g > div[data-kind="${k}"]`);
  for (const [j, el] of els.entries()) await el.screenshot({ path: `/tmp/models-${k}${j ? '-' + j : ''}.png` });
}
check('لا خطأ في الصفحة', errors.length === 0, errors.join(' | '));
await browser.close();
server.close();
console.log(results.every(Boolean) ? `نجحت الاختبارات كلها: ${results.length}` : `النتيجة: نجح ${results.filter(Boolean).length} من ${results.length}`);
process.exit(results.every(Boolean) ? 0 : 1);
