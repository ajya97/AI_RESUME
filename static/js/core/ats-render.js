/**
 * core/ats-render.js — renders an ATS report. Every dynamic value is escaped
 * (the original analyze.js inserted resume-derived skills unescaped).
 */
import { esc, initTabs } from './ui.js';
import { scoreRing } from './charts.js';

const label = k => k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
const chips = (xs, cls = '') => (xs && xs.length ? `<div class="chips">${xs.map(x => `<span class="chip ${cls}">${esc(x)}</span>`).join('')}</div>` : '<span class="dim small">None</span>');
const ORDER = { High: 0, Medium: 1, Low: 2 };

export function renderAts(root, d) {
  const { parsed, ats, missing_sections: missing = [], errors = [], gpt_analysis: g = {} } = d;
  const kw = g.keyword_recommendations || {}, gap = g.skill_gap_analysis || {};
  const sugg = [...(g.improvement_suggestions || [])].sort((a, b) => (ORDER[a.priority] ?? 3) - (ORDER[b.priority] ?? 3)); // fixes original sort bug

  const tags = [];
  if (ats.sections.contact_info?.score === 10) tags.push('Contact complete');
  if (ats.sections.projects?.score >= 10) tags.push('Strong projects');
  if (ats.sections.skills?.score >= 15) tags.push('Great skills');
  if (g.interview_readiness?.score >= 70) tags.push('Interview ready');
  if (ats.total_score < 50) tags.push('Needs work');

  root.innerHTML = `
  <div class="card stack">
    <div class="score-hero">
      <div class="score-ring" id="atsRing" role="img" aria-label="ATS score ${esc(ats.total_score)} out of 100"></div>
      <div class="stack" style="flex:1;min-width:240px">
        <div><span class="badge badge-violet">${esc(ats.rating)}</span></div>
        <h2 style="margin:0">${esc(parsed.name || 'Your resume')}</h2>
        <div class="muted">ATS compatibility score (heuristic)</div>
        <div class="chips">${tags.map(t => `<span class="chip chip-ok">✓ ${esc(t)}</span>`).join('')}</div>
        <div class="small dim">${esc(d.ats_note || '')}</div>
      </div>
    </div>
  </div>
  <div class="card" id="atsTabs" style="margin-top:16px">
    <div class="tabs" role="tablist">
      <button class="tab" role="tab" aria-selected="true" data-tab="overview">Overview</button>
      <button class="tab" role="tab" aria-selected="false" data-tab="issues">Issues (${errors.length})</button>
      <button class="tab" role="tab" aria-selected="false" data-tab="keywords">Keywords</button>
      <button class="tab" role="tab" aria-selected="false" data-tab="skills">Skill gap</button>
      <button class="tab" role="tab" aria-selected="false" data-tab="tips">Suggestions</button>
    </div>
    <div class="tab-panel" id="panel-overview">
      <div class="grid grid-2">
        <div><h3>Section breakdown</h3>${Object.entries(ats.sections).map(([k, v]) => {
          const pct = Math.round((v.score / v.max) * 100);
          return `<div class="bar-row"><div>${esc(label(k))}</div><div class="progress"><span style="width:${pct}%"></span></div><div class="val">${v.score}/${v.max}</div></div>`;
        }).join('')}</div>
        <div><h3>Extracted profile</h3>
          ${['name', 'email', 'phone', 'linkedin', 'github'].filter(k => parsed[k]).map(k => `<div class="row" style="margin-bottom:6px"><span class="dim" style="width:80px">${esc(label(k))}</span><span>${esc(parsed[k])}</span></div>`).join('') || '<span class="dim">Nothing detected</span>'}
          <div style="margin-top:10px">${chips((parsed.skills || []).slice(0, 14))}</div></div>
      </div>
      <h3 style="margin-top:18px">Missing sections</h3>
      ${missing.length ? missing.map(m => `<div class="list-item"><span aria-hidden="true">⚠️</span><div><b>${esc(m.section)}</b><div class="muted small">${esc(m.why_it_matters)}</div><div class="small"><b>Fix:</b> ${esc(m.suggestion)}</div></div></div>`).join('') : '<div class="alert alert-success">✓ No important sections missing.</div>'}
    </div>
    <div class="tab-panel" id="panel-issues" hidden>
      ${errors.length ? errors.map(e => `<div class="list-item"><span class="sev sev-${esc(e.severity)}">${esc(e.severity)}</span><div><b>${esc(e.type)}</b><div class="small muted">${esc(e.fix)}</div></div></div>`).join('') : '<div class="alert alert-success">✓ No issues detected.</div>'}
    </div>
    <div class="tab-panel" id="panel-keywords" hidden><div class="grid grid-2">
      ${[['Missing ATS keywords', 'missing_ats_keywords', 'chip-miss'], ['Technical keywords', 'recommended_technical_keywords', ''],
        ['Industry keywords', 'industry_keywords', ''], ['Role-specific keywords', 'role_specific_keywords', '']]
        .map(([t, k, c]) => `<div class="list-item" style="display:block"><h3>${esc(t)}</h3>${chips(kw[k], c)}</div>`).join('')}</div></div>
    <div class="tab-panel" id="panel-skills" hidden><div class="grid grid-2">
      <div class="list-item" style="display:block"><h3>Strong skills</h3>${chips(gap.strong_skills, 'chip-ok')}</div>
      <div class="list-item" style="display:block"><h3>Weak areas</h3>${chips(gap.weak_areas, 'chip-warn')}</div>
      <div class="list-item" style="display:block"><h3>Missing critical skills</h3>${chips(gap.missing_critical_skills, 'chip-miss')}</div>
      <div class="list-item" style="display:block"><h3>Recommended to learn</h3>${(gap.recommended_skills_to_learn || []).map(s => `<div style="margin-bottom:8px"><b>${esc(s.skill)}</b><div class="small muted">${esc(s.reason)}</div><div class="small dim">🎓 ${esc(s.resource)}</div></div>`).join('') || '<span class="dim small">None</span>'}</div></div></div>
    <div class="tab-panel" id="panel-tips" hidden>
      <p class="muted">${esc(g.overall_feedback || '')}</p>
      ${sugg.map(s => `<div class="list-item"><span class="sev sev-${esc(s.priority)}">${esc(s.priority)}</span><div><b>${esc(s.category)}</b><div class="small muted">${esc(s.suggestion)}</div></div></div>`).join('')}
      <div class="small dim" style="margin-top:12px">AI-generated feedback is advisory, not an employer assessment.</div>
    </div>
  </div>`;
  scoreRing(root.querySelector('#atsRing'), ats.total_score, 100);
  initTabs(root.querySelector('#atsTabs'));
}
