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
  const hidden = (kind, k) => m.hide[0] === kind && m.hide[1] === k;
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

// نموذج البند كما يطلبه موردُه (resource)، أو null إن كان «بلا نموذج» أو لا رسم له بعد
export function modelFor(item) {
  const n = item.numbers;
  if (item.performance === 'frame_empty') return tenFrame({ counters: n.n });
  if (item.performance === 'frame_counters') return tenFrame({ counters: 10 - n.e, covered: true });
  if (item.performance === 'step_pair') return tenFrame({ ghost: true });
  if (item.model) return numberLine(item.model, { perf: item.performance });
  return null;
}

// النموذج الذي يعود بعد خطأ في التعلّم (4.1): المسألة مجهّزة على الإطار دون حلّها
export function supportFor(item) {
  const n = item.numbers;
  if (item.performance === 'frame_counters') return tenFrame({ counters: 10 - n.e, covered: true });
  if (typeof n.n === 'number' && n.n >= 0 && n.n <= 10) return tenFrame({ counters: n.n });
  if (item.model) return numberLine(item.model, { perf: item.performance });
  if (typeof n.a === 'number' && typeof n.b === 'number') return blankLine(n.a, n.b);
  return null;
}
