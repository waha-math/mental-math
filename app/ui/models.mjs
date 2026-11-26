// النماذج المرسومة. الإطار لا ينعكس مع العربية: الخانات تُملأ من اليسار، الصف الأعلى أولًا (7.6).
const NS = 'http://www.w3.org/2000/svg';
const el = (tag, attrs = {}) => {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
};

// إطار العشرة. counters: عدد الأقراص. covered: الأقراص مغطاة (تُرى الخانات الفارغة وحدها). ghost: هيكل شفاف بلا أقراص
export function tenFrame({ counters = 0, covered = false, ghost = false } = {}) {
  const svg = el('svg', { viewBox: '0 0 520 220', class: 'frame' + (ghost ? ' ghost' : ''), role: 'img',
    'data-counters': String(counters), 'data-covered': String(covered) });
  for (let k = 0; k < 10; k++) {
    const x = 10 + (k % 5) * 100, y = 10 + Math.floor(k / 5) * 100;
    svg.append(el('rect', { x, y, width: 100, height: 100, class: 'cell' }));
    if (!ghost && k < counters) {
      svg.append(covered ? el('rect', { x: x + 6, y: y + 6, width: 88, height: 88, rx: 10, class: 'cover' })
        : el('circle', { cx: x + 50, cy: y + 50, r: 36, class: 'counter' }));
    }
  }
  return svg;
}

const BOX = '▢';

// خط الأعداد الفارغ: محطات متباعدة بالتساوي لا بالمقياس، فالقفزة الصغيرة تُرى كالكبيرة. لا ينعكس مع العربية: الأعداد
// الأكبر إلى اليمين، والقفز للخلف يتجه يسارًا والإكمال يمينًا (7.6).
// m: حقل model من المحتوى (line و start و jumps و stations و hide). الرسم منه وحده: التطبيق لا يحسب طريقة الحل.
// - line_back: القفزات مرسومة بمقاديرها، والمحطات بلا أعداد، والأخيرة هي المسؤول عنها.
// - station_back و jump_missing (ghost): الهيكل الشفاف، وما يذكره نص البند مكتوب، والمسؤول عنه مربع.
// - line_up: المحطات فوق الخط والقفزات تحته، والمسؤول عنه مجموعها فلا مربع.
// ما يُكتب على الرسم يُحفظ في data-shown ليُطابَق بالمحتوى: لا يظهر عليه جواب البند.
export function numberLine(m, { perf } = {}) {
  const ghost = perf === 'station_back' || perf === 'jump_missing';
  const back = m.line === 'back';
  const n = m.jumps.length, W = 720, pad = 70, y = 120;
  const xs = Array.from({ length: n + 1 }, (_, k) => (back ? W - pad - k * ((W - 2 * pad) / n) : pad + k * ((W - 2 * pad) / n)));
  const hidden = (kind, k) => Array.isArray(m.hide) && m.hide[0] === kind && m.hide[1] === k;   // المقارنة: لا مخفي
  const stations = [m.start, ...m.stations].map((v, k) => {
    if (k === 0) return String(v);
    if (hidden('station', k - 1)) return BOX;
    return perf === 'line_back' ? '' : String(v);          // القفزات مرسومة والمحطات يحسبها الطفل
  });
  const jumps = m.jumps.map((v, k) => (hidden('jump', k) ? BOX : (back ? '−' : '+') + v));
  const svg = el('svg', { viewBox: `0 0 ${W} 220`, class: 'line' + (ghost ? ' ghost' : ''), role: 'img', 'data-line': m.line,
    'data-perf': perf ?? '', 'data-shown': JSON.stringify({ stations, jumps }) });
  svg.append(el('line', { x1: pad - 40, y1: y, x2: W - pad + 40, y2: y, class: 'axis' }));
  const text = (x, yy, t, cls) => { const e = el('text', { x, y: yy, class: cls, 'text-anchor': 'middle' }); e.textContent = t; return e; };
  xs.forEach((x, k) => {
    svg.append(el('line', { x1: x, y1: y - 12, x2: x, y2: y + 12, class: 'tick' }));
    if (stations[k]) svg.append(text(x, y - 26 - (perf === 'line_up' ? 0 : 0), stations[k], 'station' + (stations[k] === BOX ? ' ask' : '')));
  });
  for (let k = 0; k < n; k++) {
    const a = xs[k], b = xs[k + 1], mid = (a + b) / 2;
    // القوس تحت الخط: المحطات فوقه والقفزات تحته
    svg.append(el('path', { d: `M ${a} ${y + 14} Q ${mid} ${y + 78} ${b} ${y + 14}`, class: 'jump' }));
    svg.append(el('path', { d: `M ${b} ${y + 14} l ${back ? 12 : -12} 4 l ${back ? -4 : 4} 10 z`, class: 'head' }));
    svg.append(text(mid, y + 82, jumps[k], 'size' + (jumps[k] === BOX ? ' ask' : '')));
  }
  return svg;
}

// بند المقارنة (10.2): الحلان اللذان يذكرهما نصه، كل على خط باسم بطاقته. labels: بطاقات المقارنة من المحتوى
export function comparePair(model, labels, lang = 'ar') {
  const box = document.createElement('div');
  box.className = 'pair';
  model.pair.forEach((m, k) => {
    const row = document.createElement('div');
    row.className = 'pair-row';
    row.dataset.card = k === 0 ? 'A' : 'B';
    const name = document.createElement('span');
    name.className = 'pair-name';
    name.textContent = labels[k === 0 ? 'A' : 'B'][lang];
    row.append(name, numberLine(m, { perf: 'compare' }));
    box.append(row);
  });
  return box;
}

// خط فارغ عليه أعداد المسألة وحدها: ما يعود بعد خطأ في مسألة طرح بلا نموذج (4.1)، مجهّزًا دون حلّها
export function blankLine(a, b) {
  const W = 720, y = 120;
  const svg = el('svg', { viewBox: `0 0 ${W} 220`, class: 'line', role: 'img', 'data-line': 'blank',
    'data-shown': JSON.stringify({ stations: [String(b), String(a)], jumps: [] }) });
  svg.append(el('line', { x1: 30, y1: y, x2: W - 30, y2: y, class: 'axis' }));
  for (const [x, v] of [[130, b], [W - 130, a]]) {
    svg.append(el('line', { x1: x, y1: y - 12, x2: x, y2: y + 12, class: 'tick' }));
    const t = el('text', { x, y: y - 26, class: 'station', 'text-anchor': 'middle' });
    t.textContent = String(v);
    svg.append(t);
  }
  return svg;
}

// ---------------------------------------------------------------- نماذج المرحلة 1 (units.py)، من حقل model وحده
// كل رسم يحمل في data-shown ما يُكتب أو يُعدّ فيه، ليُطابَق بالمحتوى. لا ينعكس مع العربية
const svgOf = (w, h, kind, shown) => el('svg', { viewBox: `0 0 ${w} ${h}`, class: 'm k-' + kind, role: 'img', 'data-kind': kind,
  'data-shown': JSON.stringify(shown) });
const txt = (x, y, t, cls) => { const e = el('text', { x, y, class: cls, 'text-anchor': 'middle', 'dominant-baseline': 'central' }); e.textContent = t; return e; };
// نقاط النرد: ثلاثة ترتيبات لكل عدد حتى 5
const DOTS = [
  { 1: [[1, 1]], 2: [[0, 0], [2, 2]], 3: [[0, 0], [1, 1], [2, 2]], 4: [[0, 0], [2, 0], [0, 2], [2, 2]], 5: [[0, 0], [2, 0], [1, 1], [0, 2], [2, 2]] },
  { 1: [[0, 1]], 2: [[0, 1], [2, 1]], 3: [[0, 2], [1, 0], [2, 2]], 4: [[1, 0], [0, 1], [2, 1], [1, 2]], 5: [[0, 1], [1, 0], [1, 1], [2, 1], [1, 2]] },
  { 1: [[2, 0]], 2: [[1, 0], [1, 2]], 3: [[0, 1], [1, 1], [2, 1]], 4: [[0, 0], [1, 0], [0, 1], [1, 1]], 5: [[0, 0], [1, 0], [2, 0], [0, 2], [2, 2]] },
];
function dots(m) {
  const svg = svgOf(300, 300, 'dots', { n: m.n });
  svg.append(el('rect', { x: 10, y: 10, width: 280, height: 280, rx: 30, class: 'die' }));
  for (const [c, r] of DOTS[m.layout][m.n]) svg.append(el('circle', { cx: 60 + c * 90, cy: 60 + r * 90, r: 30, class: 'counter' }));
  return svg;
}
function frame(m) {
  const cols = 5, rows = m.size / 5, svg = svgOf(520, 20 + rows * 100, 'frame', { n: m.n, size: m.size });
  for (let k = 0; k < m.size; k++) {
    const x = 10 + (k % cols) * 100, y = 10 + Math.floor(k / cols) * 100;
    svg.append(el('rect', { x, y, width: 100, height: 100, class: 'cell' }));
    if (k < m.n) svg.append(el('circle', { cx: x + 50, cy: y + 50, r: 36, class: 'counter' }));
  }
  return svg;
}
// مسار الأعداد: مربعات مرقّمة. hide: المربع المسؤول عنه. mark و jump: البداية والقفزة، والوصول مربع فارغ
function path(m) {
  const n = m.len, W = Math.max(560, n * 64), cell = (W - 20) / n;
  const nums = Array.from({ length: n }, (_, k) => m.start + k * m.step);
  const end = m.jump !== undefined ? m.mark + m.jump : null;
  const shown = nums.map((v, k) => (k === m.hide || v === end ? BOX : String(v)));
  const svg = svgOf(W, 190, 'path', { nums: shown, mark: m.mark ?? null, jump: m.jump ?? null });
  nums.forEach((v, k) => {
    const x = 10 + k * cell;
    svg.append(el('rect', { x, y: 70, width: cell - 4, height: 70, rx: 10, class: 'cell' + (v === m.mark ? ' mark' : '') }));
    svg.append(txt(x + cell / 2 - 2, 105, shown[k], 'num' + (shown[k] === BOX ? ' ask' : '')));
  });
  if (m.jump !== undefined && m.jump !== 0) {
    const i0 = nums.indexOf(m.mark), i1 = nums.indexOf(end);
    const a = 10 + i0 * cell + cell / 2 - 2, b = 10 + i1 * cell + cell / 2 - 2, top = 70 - 12 * Math.abs(m.jump) - 10;
    svg.append(el('path', { d: `M ${a} 66 Q ${(a + b) / 2} ${Math.max(4, top)} ${b} 66`, class: 'jump' }));
    svg.append(el('path', { d: `M ${b} 66 l ${b > a ? -12 : 12} -6 l ${b > a ? 2 : -2} 12 z`, class: 'head' }));
    svg.append(txt((a + b) / 2, Math.max(16, top + 10), (m.jump > 0 ? '+' : '−') + Math.abs(m.jump), 'size'));
  }
  return svg;
}
function discs(m) {
  const n = m.red + m.blue, svg = svgOf(Math.max(300, n * 70 + 20), 120, 'discs', { red: m.red, blue: m.blue });
  for (let k = 0; k < n; k++) svg.append(el('circle', { cx: 45 + k * 70, cy: 60, r: 28, class: k < m.red ? 'red' : 'blue' }));
  return svg;
}
// مخطط الرابطة: الكل فوق، والجزءان تحته، والجزء المسؤول عنه مربع
function bond(m) {
  const svg = svgOf(420, 300, 'bond', { whole: String(m.whole), parts: [String(m.part), BOX] });
  svg.append(el('line', { x1: 210, y1: 90, x2: 110, y2: 200, class: 'link' }));
  svg.append(el('line', { x1: 210, y1: 90, x2: 310, y2: 200, class: 'link' }));
  for (const [x, y, t] of [[210, 70, String(m.whole)], [110, 220, String(m.part)], [310, 220, BOX]]) {
    svg.append(el('circle', { cx: x, cy: y, r: 56, class: 'node' }));
    svg.append(txt(x, y, t, 'num' + (t === BOX ? ' ask' : '')));
  }
  return svg;
}
// الكوب المخفي: الأقراص الظاهرة، وكوب يغطي الباقي ولا يُعرف عددها منه
function cup(m) {
  const svg = svgOf(Math.max(420, m.shown * 70 + 200), 160, 'cup', { shown: m.shown, total: m.total });
  for (let k = 0; k < m.shown; k++) svg.append(el('circle', { cx: 45 + k * 70, cy: 100, r: 28, class: 'blue' }));
  const x = 30 + m.shown * 70;
  svg.append(el('path', { d: `M ${x} 140 L ${x + 30} 30 L ${x + 130} 30 L ${x + 160} 140 Z`, class: 'cupshape' }));
  return svg;
}
// المرحلة 2: إطارا عشرة (يمتلئ الأول ثم الثاني)، وصفّا خرز (المخفي صفّه مغطى)، وخط القفزات بقاعدة خط الأعداد نفسها
function frames2(m) {
  const svg = svgOf(1060, 220, 'frames2', { n: m.n });
  for (let f = 0; f < 2; f++) {
    for (let k = 0; k < 10; k++) {
      const x = 10 + f * 530 + (k % 5) * 100, y = 10 + Math.floor(k / 5) * 100;
      svg.append(el('rect', { x, y, width: 100, height: 100, class: 'cell' }));
      if (f * 10 + k < m.n) svg.append(el('circle', { cx: x + 50, cy: y + 50, r: 36, class: 'counter' }));
    }
  }
  return svg;
}
function beads(m) {
  const k = m.rows[0], svg = svgOf(Math.max(400, k * 56 + 60), 200, 'beads', { rows: m.rows, hide: m.hide ?? null });
  m.rows.forEach((n, r) => {
    const y = 55 + r * 90;
    svg.append(el('line', { x1: 20, y1: y, x2: n * 56 + 40, y2: y, class: 'link' }));
    if (r === m.hide) {
      svg.append(el('rect', { x: 20, y: y - 32, width: n * 56 + 20, height: 64, rx: 14, class: 'cupshape' }));
      return;
    }
    for (let j = 0; j < n; j++) svg.append(el('circle', { cx: 50 + j * 56, cy: y, r: 24, class: j < 5 ? 'red' : 'blue' }));
  });
  return svg;
}
function jumps(m) {
  const svg = numberLine(m, { perf: 'units' });
  svg.setAttribute('class', 'm k-jumps');
  svg.dataset.kind = 'jumps';
  return svg;
}
// المرحلة 3: حزم العشرات (حزمة = عمود من عشرة مربعات، والآحاد مربعات مفردة؛ المضاف بلون آخر، والمأخوذ مشطوب)،
// والعددان بالحزم في صفين، وخط التقريب بعشرتيه، والعددان قبل الزيادة وبعدها، والشريط المقصوص نصفين
function bundle(svg, x, y, cls) {
  svg.append(el('rect', { x, y, width: 34, height: 200, rx: 4, class: 'rod ' + cls }));
  for (let j = 1; j < 10; j++) svg.append(el('line', { x1: x, y1: y + j * 20, x2: x + 34, y2: y + j * 20, class: 'rodline' }));
}
function tens(m) {
  const plus = m.plus ?? 0, minus = m.minus ?? 0, total = m.tens + plus;
  const W = Math.max(420, total * 46 + (m.ones ? 70 : 0) + 40), svg = svgOf(W, 240, 'tens', { tens: m.tens, ones: m.ones, plus, minus });
  for (let k = 0; k < total; k++) {
    const x = 20 + k * 46;
    bundle(svg, x, 20, k >= m.tens ? 'add' : '');
    if (k >= m.tens - minus && k < m.tens) svg.append(el('line', { x1: x - 6, y1: 230, x2: x + 40, y2: 10, class: 'cross' }));
  }
  for (let j = 0; j < m.ones; j++) svg.append(el('rect', { x: 30 + total * 46 + (j % 2) * 26, y: 200 - Math.floor(j / 2) * 26, width: 22, height: 22, class: 'rod' }));
  return svg;
}
function tens2(m) {
  const W = 520, svg = svgOf(W, 500, 'tens2', { a: m.a, b: m.b });
  [m.a, m.b].forEach(([t, o], r) => {
    const y = 20 + r * 250;
    for (let k = 0; k < t; k++) bundle(svg, 20 + k * 46, y, r ? 'add' : '');
    for (let j = 0; j < o; j++) svg.append(el('rect', { x: 30 + t * 46 + (j % 2) * 26, y: y + 178 - Math.floor(j / 2) * 26, width: 22, height: 22, class: 'rod' + (r ? ' add' : '') }));
  });
  return svg;
}
// التقريب: خط من العشرة إلى التالية بأحد عشر تدريجًا، والعدد عليه نقطة، والعشرتان مكتوبتان
function round(m) {
  // dist (في الدرس): المسافتان من العدد إلى العشرتين قوسان تحت الخط بمقداريهما، فيُرى التساوي في ما آحاده 5
  const shown = m.dist ? { lo: m.lo, hi: m.hi, v: m.v, dist: [String(m.v - m.lo), String(m.hi - m.v)] } : { lo: m.lo, hi: m.hi, v: m.v };
  const W = 720, pad = 60, y = 110, step = (W - 2 * pad) / 10, svg = svgOf(W, m.dist ? 240 : 200, 'round', shown);
  svg.append(el('line', { x1: pad, y1: y, x2: W - pad, y2: y, class: 'link' }));
  for (let j = 0; j <= 10; j++) svg.append(el('line', { x1: pad + j * step, y1: y - (j % 5 ? 10 : 20), x2: pad + j * step, y2: y + (j % 5 ? 10 : 20), class: 'link' }));
  svg.append(txt(pad, y + 50, String(m.lo), 'num'));
  svg.append(txt(W - pad, y + 50, String(m.hi), 'num'));
  const x = pad + ((m.v - m.lo) / (m.hi - m.lo)) * (W - 2 * pad);       // عشرة أو مئة أو ألف بين العلامتين
  svg.append(el('circle', { cx: x, cy: y, r: 14, class: 'red' }));
  svg.append(txt(x, y - 48, String(m.v), 'num'));
  if (m.dist) {
    for (const [a, b, d] of [[pad, x, m.v - m.lo], [x, W - pad, m.hi - m.v]]) {
      svg.append(el('path', { d: `M ${a} ${y + 14} Q ${(a + b) / 2} ${y + 70} ${b} ${y + 14}`, class: 'jump' }));
      svg.append(txt((a + b) / 2, y + 90, String(d), 'size'));
    }
  }
  return svg;
}
// الفرق الثابت: خطان، الأول بالعددين، والثاني بهما بعد زيادة كلٍّ منهما d، والفرق بينهما قوس واحد بلا عدد
function slide(m) {
  const W = 720, svg = svgOf(W, 330, 'slide', { rows: [[m.b, m.a], [m.b + m.d, m.a + m.d]], d: m.d });
  [[m.b, m.a], [m.b + m.d, m.a + m.d]].forEach(([lo, hi], r) => {
    const y = 90 + r * 160, x0 = 120 + r * 80, x1 = 520 + r * 80;
    svg.append(el('line', { x1: 30, y1: y, x2: W - 30, y2: y, class: 'link' }));
    for (const [x, v] of [[x0, lo], [x1, hi]]) {
      svg.append(el('circle', { cx: x, cy: y, r: 12, class: 'red' }));
      svg.append(txt(x, y - 40, String(v), 'num'));
    }
    svg.append(el('path', { d: `M ${x0} ${y + 14} Q ${(x0 + x1) / 2} ${y + 70} ${x1} ${y + 14}`, class: 'jump' }));
  });
  return svg;
}
function bar(m) {
  const svg = svgOf(720, 220, 'bar', { whole: String(m.whole), parts: [BOX, BOX] });
  svg.append(txt(360, 30, String(m.whole), 'num'));
  for (let k = 0; k < 2; k++) {
    svg.append(el('rect', { x: 20 + k * 345, y: 70, width: 335, height: 80, rx: 8, class: 'cell' }));
    svg.append(txt(187 + k * 345, 110, BOX, 'num ask'));
  }
  return svg;
}
// المرحلة 4: مصفوفة نقاط (rows × cols). shade أعمدة ملوّنة من اليسار (نصف جدول 10)، cross أعمدة مشطوبة من اليمين
// (جدول 9)، split خطّان بعد العمود والصف (المربع عند 5). لا عدد مكتوبًا عليها
function arr(m) {
  const c = 30, pad = 16, W = pad * 2 + m.cols * c, H = pad * 2 + m.rows * c;
  const svg = svgOf(Math.max(W, 120), H, 'arr', { rows: m.rows, cols: m.cols, shade: m.shade ?? 0, cross: m.cross ?? 0,
    split: m.split ?? 0 });
  for (let r = 0; r < m.rows; r++) {
    for (let k = 0; k < m.cols; k++) {
      const x = pad + k * c + c / 2, y = pad + r * c + c / 2;
      const crossed = m.cross && k >= m.cols - m.cross;
      svg.append(el('circle', { cx: x, cy: y, r: 10, class: m.shade && k < m.shade ? 'red' : crossed ? 'counter off' : 'counter' }));
      if (crossed) svg.append(el('line', { x1: x - 11, y1: y - 11, x2: x + 11, y2: y + 11, class: 'cross' }));
    }
  }
  if (m.split) {
    svg.append(el('line', { x1: pad + m.split * c, y1: 4, x2: pad + m.split * c, y2: H - 4, class: 'split' }));
    if (m.rows > m.split) svg.append(el('line', { x1: 4, y1: pad + m.split * c, x2: W - 4, y2: pad + m.split * c, class: 'split' }));
  }
  return svg;
}
// القسمة: كومة تمر لم تُوزَّع (total)، وأطباق فارغة (plates) يوزّعها الطفل في ذهنه
function share(m) {
  const per = 12, c = 22, rows = Math.ceil(m.total / per), W = Math.max(per * c + 40, m.plates * 74 + 20);
  const H = 30 + rows * c + 100, svg = svgOf(W, H, 'share', { total: m.total, plates: m.plates });
  for (let j = 0; j < m.total; j++) svg.append(el('circle', { cx: 30 + (j % per) * c, cy: 24 + Math.floor(j / per) * c, r: 8, class: 'date' }));
  for (let k = 0; k < m.plates; k++) svg.append(el('ellipse', { cx: 46 + k * 74, cy: H - 40, rx: 32, ry: 18, class: 'plate' }));
  return svg;
}
// المرحلة 5: جدول المنازل بأرقام العدد، من اليسار إلى اليمين. shift: كم منزلة ينتقل العدد (موجب يسارًا في الضرب،
// وسالب يمينًا في القسمة)، سهم فوق الجدول بلا ناتج
function places(m) {
  const n = Math.max(m.digits.length + Math.max(m.shift ?? 0, 0), 4), c = 84, W = n * c + 40, H = m.shift ? 230 : 170;
  const svg = svgOf(W, H, 'places', { digits: m.digits.map(String), shift: m.shift ?? 0 });
  const names = ['آحاد', 'عشرات', 'مئات', 'آلاف', 'عشرات الآلاف', 'مئات الآلاف'];
  const top = m.shift ? 70 : 10;
  for (let k = 0; k < n; k++) {
    const x = 20 + k * c;
    svg.append(el('rect', { x, y: top, width: c, height: 40, class: 'cell head' }));
    svg.append(txt(x + c / 2, top + 20, names[n - 1 - k] ?? '', 'size'));
    svg.append(el('rect', { x, y: top + 40, width: c, height: 80, class: 'cell' }));
  }
  const off = n - m.digits.length - Math.max(m.shift ?? 0, 0);
  m.digits.forEach((d, k) => svg.append(txt(20 + (off + k) * c + c / 2, top + 80, String(d), 'num')));
  if (m.shift) {
    const x1 = 20 + (off + m.digits.length / 2) * c, x2 = x1 - m.shift * c;
    svg.append(el('path', { d: `M ${x1} 50 Q ${(x1 + x2) / 2} 0 ${x2} 50`, class: 'jump' }));
    svg.append(el('path', { d: `M ${x2} 50 l ${m.shift > 0 ? 4 : -4} -14 l ${m.shift > 0 ? 10 : -10} 6 z`, class: 'head' }));
  }
  return svg;
}
// المساحة: مستطيل بضلعيه مكتوبين، وداخله المجهول
function area(m) {
  const svg = svgOf(560, 320, 'area', { a: String(m.a), b: String(m.b) });
  svg.append(el('rect', { x: 90, y: 40, width: 420, height: 230, class: 'cell' }));
  svg.append(txt(300, 22, String(m.a), 'num'));
  svg.append(txt(50, 155, String(m.b), 'num'));
  svg.append(txt(300, 155, BOX, 'num ask'));
  return svg;
}
// المراحل 6 و8: مستطيل مقسوم. أطوال أجزاء ضلعيه مكتوبة (top فوق، side يسارًا)، والمناطق بلا نواتجها. cross شريط مشطوب
// من آخر الأعلى (التعويض)، و corner ركن ينقص من المربع (فرق المربعين)، و keep: المنطقة الأولى وحدها ملوّنة والباقي
// يُنزع (قرب 100)
function grid(m) {
  const W = 620, H = 380, x0 = 90, y0 = 60, w = W - x0 - 20, h = H - y0 - 20;
  const T = m.top.reduce((a, b) => a + b, 0), S = m.side.reduce((a, b) => a + b, 0);
  const svg = svgOf(W, H, 'grid', { top: m.top.map(String), side: m.side.map(String), cross: m.cross ?? 0, corner: m.corner ?? 0 });
  let x = x0;
  m.top.forEach((t, i) => {
    const dx = w * t / T;
    let y = y0;
    m.side.forEach((sd, j) => {
      const dy = h * sd / S;
      svg.append(el('rect', { x, y, width: dx, height: dy, class: 'cell' + (m.keep && (i > 0 || j > 0) ? ' off' : '') }));
      if (i === 0) svg.append(txt(x0 - 40, y + dy / 2, String(sd), 'size'));
      y += dy;
    });
    svg.append(txt(x + dx / 2, y0 - 26, String(t), 'size'));
    x += dx;
  });
  if (m.cross) {
    const dx = Math.max(w * m.cross / T, 14);
    svg.append(el('rect', { x: x0 + w - dx, y: y0, width: dx, height: h, class: 'strip-off' }));
    svg.append(txt(x0 + w - dx / 2, y0 - 26, '−' + m.cross, 'size'));
  }
  if (m.corner) {
    const d = w * m.corner / T, e = h * m.corner / S;
    svg.append(el('rect', { x: x0 + w - d, y: y0 + h - e, width: d, height: e, class: 'strip-off' }));
  }
  return svg;
}
// التنصيف والمضاعفة: المستطيل قبل القصّ، ثم بعد وضع النصف بجانب الآخر، وضلعه الطويل مجهول
function halve(m) {
  const svg = svgOf(700, 300, 'halve', { before: [String(m.a), String(m.b)], after: [String(m.a2), BOX] });
  svg.append(el('rect', { x: 40, y: 60, width: 180, height: 200, class: 'cell' }));
  svg.append(el('line', { x1: 40, y1: 160, x2: 220, y2: 160, class: 'split' }));
  svg.append(txt(130, 36, String(m.b), 'size'));
  svg.append(txt(18, 160, String(m.a), 'size'));
  svg.append(el('rect', { x: 300, y: 110, width: 360, height: 100, class: 'cell' }));
  svg.append(el('line', { x1: 480, y1: 110, x2: 480, y2: 210, class: 'split' }));
  svg.append(txt(480, 86, BOX, 'size ask'));
  svg.append(txt(278, 160, String(m.a2), 'size'));
  return svg;
}
// القسمة بتجزئة المقسوم: شريط بجزأين بطوليهما، والقاسم فوقه
function strip(m) {
  const T = m.parts.reduce((a, b) => a + b, 0), W = 660;
  const svg = svgOf(W, 200, 'strip', { parts: m.parts.map(String), by: String(m.by) });
  let x = 30;
  m.parts.forEach((p) => {
    const dx = (W - 60) * p / T;
    svg.append(el('rect', { x, y: 70, width: dx, height: 70, class: 'cell' }));
    svg.append(txt(x + dx / 2, 105, String(p), 'size'));
    x += dx;
  });
  svg.append(txt(W / 2 - 24, 30, '÷', 'num'));
  svg.append(txt(W / 2 + 14, 30, String(m.by), 'num'));
  return svg;
}
// الكسر: شريط d أجزاء، الملوّن n. d2: شريط ثانٍ مطابق بأجزاء أدق للمكافئ. whole: قيمة الشريط مكتوبة. times: عدد الأشرطة
function fstrip(m) {
  const rows = m.d2 ? 2 : Math.min(m.times ?? 1, 1), W = 680, H = 60 + (m.d2 ? 2 : 1) * 90;
  const svg = svgOf(W, H, 'fstrip', { n: m.n, d: m.d, d2: m.d2 ?? 0, whole: m.whole ?? null, times: m.times ?? 0 });
  const draw = (y, d, shaded) => {
    for (let k = 0; k < d; k++) {
      svg.append(el('rect', { x: 30 + k * (W - 60) / d, y, width: (W - 60) / d, height: 60, class: k < shaded ? 'cell on' : 'cell' }));
    }
  };
  draw(40, m.d, m.n);
  if (m.d2) draw(130, m.d2, 0);
  if (m.whole != null) svg.append(txt(W / 2, 20, String(m.whole), 'size'));
  return svg;
}
// شبكة المئة (الواحد): الملوّن n مربعًا صغيرًا. ra و rb (ضرب عشريين): مستطيل ra أعشار في rb أعشار
function grid100(m) {
  const c = 26, svg = svgOf(c * 10 + 20, c * 10 + 20, 'grid100', { n: m.n });
  for (let k = 0; k < 100; k++) {
    const col = k % 10, row = Math.floor(k / 10);
    const on = m.ra ? col < m.rb && row < m.ra : k < m.n;
    svg.append(el('rect', { x: 10 + col * c, y: 10 + row * c, width: c, height: c, class: on ? 'cell on' : 'cell' }));
  }
  return svg;
}
// وجه الساعة لبوابة الجاهزية (قراءة الساعة، 8-5-2): أرقام 1 إلى 12، والعقرب القصير بين ساعتيه بقدر الدقائق
function clock(m) {
  const C = 160, R = 140, svg = svgOf(2 * C, 2 * C, 'clock', { h: m.h, m: m.m });
  svg.append(el('circle', { cx: C, cy: C, r: R, class: 'face' }));
  const at = (turn, r) => [C + r * Math.sin(2 * Math.PI * turn), C - r * Math.cos(2 * Math.PI * turn)];
  for (let k = 1; k <= 12; k++) {
    const [x, y] = at(k / 12, R - 26);
    svg.append(txt(x, y, String(k), 'num'));
  }
  for (let k = 0; k < 60; k++) {
    const [x1, y1] = at(k / 60, R - (k % 5 ? 6 : 12)), [x2, y2] = at(k / 60, R);
    svg.append(el('line', { x1, y1, x2, y2, class: 'tick' }));
  }
  const [hx, hy] = at(((m.h % 12) + m.m / 60) / 12, R * 0.5), [mx, my] = at(m.m / 60, R * 0.8);
  svg.append(el('line', { x1: C, y1: C, x2: hx, y2: hy, class: 'hand hour', 'data-turn': ((m.h % 12) * 60 + m.m) / 720 }));
  svg.append(el('line', { x1: C, y1: C, x2: mx, y2: my, class: 'hand minute', 'data-turn': m.m / 60 }));
  svg.append(el('circle', { cx: C, cy: C, r: 7, class: 'pin' }));
  return svg;
}
const KINDS = { dots, frame, path, discs, bond, cup, frames2, beads, jumps, tens, tens2, round, slide, bar, arr, share, places,
  area, grid, halve, strip, fstrip, grid100, clock };

// نموذج البند كما يطلبه موردُه (resource)، أو null إن كان «بلا نموذج» أو لا رسم له بعد
export function modelFor(item) {
  if (item.model && KINDS[item.model.kind]) return KINDS[item.model.kind](item.model);
  const n = item.numbers;
  if (item.performance === 'frame_empty') return tenFrame({ counters: n.n });
  if (item.performance === 'frame_counters') return tenFrame({ counters: 10 - n.e, covered: true });
  if (item.performance === 'step_pair') return tenFrame({ ghost: true });
  if (item.model) return numberLine(item.model, { perf: item.performance });
  return null;
}

// النموذج الذي يعود بعد خطأ في التعلّم (4.1): المسألة مجهّزة على الإطار دون حلّها
export function supportFor(item) {
  if (item.model && KINDS[item.model.kind]) return KINDS[item.model.kind](item.model);   // الومضة تُعاد ظاهرة
  const n = item.numbers;
  if (item.performance === 'frame_counters') return tenFrame({ counters: 10 - n.e, covered: true });
  if (typeof n.n === 'number' && n.n >= 0 && n.n <= 10) return tenFrame({ counters: n.n });
  if (item.model) return numberLine(item.model, { perf: item.performance });
  if (typeof n.a === 'number' && typeof n.b === 'number') return blankLine(n.a, n.b);
  return null;
}
