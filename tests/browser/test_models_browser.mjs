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
  const k = it.skill + '|' + it.performance;
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
      // العقربان: زاوية كل منهما من الثانية عشرة باتجاه عقارب الساعة، مقيسة من إحداثيات الخط المرسوم
      const hands = [...svg.querySelectorAll('line.hand')].map((l) => {
        const [x1, y1, x2, y2] = ['x1', 'y1', 'x2', 'y2'].map((a) => +l.getAttribute(a));
        return [l.classList.contains('hour') ? 'hour' : 'minute', ((Math.atan2(x2 - x1, y1 - y2) * 180 / Math.PI) + 360) % 360,
          Math.hypot(x2 - x1, y2 - y1)];
      });
      return { id: it.id, kind: it.model.kind, w: r.width, h: r.height, texts, shown: svg.dataset.shown ?? null, cls: svg.getAttribute('class'), hands };
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
  const el = await page.$(`#g > div[data-kind="${k}"]`);
  await el.screenshot({ path: `/tmp/models-${k}.png` });
}
check('لا خطأ في الصفحة', errors.length === 0, errors.join(' | '));
await browser.close();
server.close();
console.log(results.every(Boolean) ? `نجحت الاختبارات كلها: ${results.length}` : `النتيجة: نجح ${results.filter(Boolean).length} من ${results.length}`);
process.exit(results.every(Boolean) ? 0 : 1);
