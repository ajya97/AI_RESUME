import { api } from '../core/api.js';
import { esc, fmtDate } from '../core/ui.js';
import { lineChart, barChart } from '../core/charts.js';

export const detailUrl = i => `/history/${i.kind}/${i.id}`;

try {
  const a = await api('/api/analytics/summary');
  const kpi = (v, l) => `<div class="card kpi"><div class="stat-val gradient-text">${esc(v)}</div><div class="stat-label">${esc(l)}</div></div>`;
  document.getElementById('kpis').innerHTML =
    kpi(a.credits.balance, 'Credits remaining') + kpi(a.totals.analyses, 'Analyses run') +
    kpi(a.average_ats_score ?? '—', 'Average ATS score') + kpi(a.totals.interview, 'Interview sessions');
  document.getElementById('kpis').removeAttribute('aria-busy');

  const draw = (id, empty, pts, fn, ...rest) => {
    if (!pts.length) { document.getElementById(id).classList.add('hidden'); document.getElementById(empty).classList.remove('hidden'); }
    else fn(document.getElementById(id), pts, ...rest);
  };
  draw('chartAts', 'emptyAts', a.ats_timeline.map(p => ({ label: p.date, value: p.score })), lineChart, 100);
  draw('chartGap', 'emptyGap', a.skill_gap_trend.map(p => ({ label: p.date, value: p.coverage })), barChart, 100, true);
  draw('chartIv', 'emptyIv', a.interview_progress.map(p => ({ label: p.date, value: p.avg ?? 0 })), barChart, 10);

  document.getElementById('recent').innerHTML = a.recent_activity.length
    ? a.recent_activity.map(i => `<div class="activity-item"><div><a href="${detailUrl(i)}">${esc(i.title)}</a><div class="small dim">${esc(i.kind_label)} · ${esc(fmtDate(i.created_at))}</div></div>
        ${i.score != null ? `<span class="badge">${esc(i.score)}/${i.score_max}</span>` : ''}</div>`).join('')
    : '<div class="empty"><div class="empty-icon">🗂️</div>No activity yet. Upload a resume to get started.</div>';

  const u = a.credits.by_operation;
  document.getElementById('usage').innerHTML = u.length
    ? u.map(o => `<div class="activity-item"><span>${esc(o.label)}</span><b>${esc(o.credits)}</b></div>`).join('') +
      `<div class="small dim" style="margin-top:8px">Provider tokens used: ${esc(a.ai_usage.input_tokens + a.ai_usage.output_tokens)}${a.ai_usage.estimated_cost_usd != null ? ` (≈ $${a.ai_usage.estimated_cost_usd.toFixed(4)})` : ''}</div>`
    : '<div class="empty">No credits spent yet.</div>';
} catch (e) {
  document.getElementById('kpis').innerHTML = `<div class="alert alert-error" style="grid-column:1/-1">${esc(e.message)}</div>`;
}
