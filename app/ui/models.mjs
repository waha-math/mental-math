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

// نموذج البند كما يطلبه موردُه (resource)، أو null إن كان «بلا نموذج» أو لا رسم له بعد
export function modelFor(item) {
  const n = item.numbers;
  if (item.performance === 'frame_empty') return tenFrame({ counters: n.n });
  if (item.performance === 'frame_counters') return tenFrame({ counters: 10 - n.e, covered: true });
  if (item.performance === 'step_pair') return tenFrame({ ghost: true });
  return null;
}

// النموذج الذي يعود بعد خطأ في التعلّم (4.1): المسألة مجهّزة على الإطار دون حلّها
export function supportFor(item) {
  const n = item.numbers;
  if (item.performance === 'frame_counters') return tenFrame({ counters: 10 - n.e, covered: true });
  if (typeof n.n === 'number' && n.n >= 0 && n.n <= 10) return tenFrame({ counters: n.n });
  return null;
}
