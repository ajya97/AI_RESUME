/** Tiny dependency-free SVG charts (theme-aware through CSS classes). */
import { esc } from './ui.js';

const W = 360, H = 180, PAD = { l: 30, r: 10, t: 12, b: 24 };

function frame(max) {
  const lines = [0, .5, 1].map(f => {
    const y = PAD.t + (H - PAD.t - PAD.b) * (1 - f);
    return `<line class="grid-line" x1="${PAD.l}" x2="${W - PAD.r}" y1="${y}" y2="${y}"/><text x="4" y="${y + 3}">${Math.round(max * f)}</text>`;
  }).join('');
  return lines;
}

/** points: [{label, value}] */
export function lineChart(el, points, max = 100) {
  if (!points.length) { el.innerHTML = ''; return; }
  const iw = W - PAD.l - PAD.r, ih = H - PAD.t - PAD.b;
  const x = i => PAD.l + (points.length === 1 ? iw / 2 : (iw * i) / (points.length - 1));
  const y = v => PAD.t + ih * (1 - Math.min(v, max) / max);
  const path = points.map((p, i) => `${i ? 'L' : 'M'}${x(i)},${y(p.value)}`).join(' ');
  const area = `${path} L${x(points.length - 1)},${PAD.t + ih} L${x(0)},${PAD.t + ih} Z`;
  const dots = points.map((p, i) => `<circle class="dot" cx="${x(i)}" cy="${y(p.value)}" r="4"><title>${esc(p.label)}: ${esc(p.value)}</title></circle>`).join('');
  const labels = points.map((p, i) => (points.length <= 6 || i % 2 === 0) ? `<text x="${x(i) - 14}" y="${H - 6}">${esc(p.label.slice(5))}</text>` : '').join('');
  el.setAttribute('viewBox', `0 0 ${W} ${H}`);
  el.innerHTML = `${frame(max)}<path class="area" d="${area}"/><path class="line" d="${path}"/>${dots}${labels}`;
}

export function barChart(el, points, max = 100, alt = false) {
  if (!points.length) { el.innerHTML = ''; return; }
  const iw = W - PAD.l - PAD.r, ih = H - PAD.t - PAD.b, bw = Math.min(34, iw / points.length - 8);
  const bars = points.map((p, i) => {
    const cx = PAD.l + (iw * (i + .5)) / points.length, h = ih * Math.min(p.value, max) / max;
    return `<rect class="bar${alt ? ' alt' : ''}" x="${cx - bw / 2}" y="${PAD.t + ih - h}" width="${bw}" height="${h}" rx="4"><title>${esc(p.label)}: ${esc(p.value)}</title></rect>
            <text x="${cx - 14}" y="${H - 6}">${esc(p.label.slice(5))}</text>`;
  }).join('');
  el.setAttribute('viewBox', `0 0 ${W} ${H}`);
  el.innerHTML = frame(max) + bars;
}

/** Animated SVG score ring: returns nothing; el = .score-ring root. */
export function scoreRing(el, value, max = 100, decimals = 0) {
  const C = 2 * Math.PI * 62;
  el.innerHTML = `<svg viewBox="0 0 150 150" width="150" height="150" aria-hidden="true">
      <circle class="bg" cx="75" cy="75" r="62" fill="none" stroke-width="11"/>
      <circle class="fg" cx="75" cy="75" r="62" fill="none" stroke-width="11" stroke-linecap="round" stroke-dasharray="${C}" stroke-dashoffset="${C}"/></svg>
    <div class="center"><div class="num">0</div><div class="max">/ ${max}</div></div>`;
  const fg = el.querySelector('.fg'), num = el.querySelector('.num');
  const start = performance.now(), dur = 1200;
  const step = now => {
    const p = Math.min((now - start) / dur, 1), e = 1 - Math.pow(1 - p, 3);
    num.textContent = (e * value).toFixed(decimals);
    fg.style.strokeDashoffset = C - (C * e * value) / max;
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}
