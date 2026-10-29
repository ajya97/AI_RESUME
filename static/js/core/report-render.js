/** Renderers for saved reports (used by feature pages and the history detail page). All values escaped. */
import { esc, fmtDate, toast } from './ui.js';
import { scoreRing } from './charts.js';
import { api } from './api.js';

const chips = (xs, cls = '') => (xs && xs.length ? `<div class="chips">${xs.map(x => `<span class="chip ${cls}">${esc(x)}</span>`).join('')}</div>` : '<span class="dim small">None</span>');
const bar = (name, pct) => pct == null ? '' : `<div class="bar-row"><div>${esc(name)}</div><div class="progress"><span style="width:${pct}%"></span></div><div class="val">${pct}%</div></div>`;

export function renderJobMatch(root, r) {
  const c = r.data.comparison, a = r.data.advice || {};
  root.innerHTML = `<div class="card stack">
    <div class="score-hero"><div class="score-ring" id="jmRing" role="img" aria-label="Match score ${esc(c.score)} percent"></div>
      <div class="stack" style="flex:1;min-width:240px"><h2 style="margin:0">Match score</h2><p class="muted">${esc(a.summary || '')}</p>
        ${bar('Skills', c.components.skills)}${bar('Keywords', c.components.keywords)}${bar('Experience', c.components.experience)}</div></div>
    <div class="alert alert-info small"><b>Methodology:</b> ${esc(c.methodology)} Estimated resume experience: ${esc(c.experience.estimated_resume_years)} yrs${c.experience.required_years ? ` vs ${esc(c.experience.required_years)}+ requested` : ''}. ${esc(c.experience.note)}</div></div>
  <div class="compare-grid" style="margin-top:16px">
    <div class="card"><h3>✅ Matching skills</h3>${chips(c.matched_skills, 'chip-ok')}</div>
    <div class="card"><h3>❌ Missing required skills</h3>${chips(c.missing_required_skills, 'chip-miss')}</div>
    <div class="card"><h3>➕ Missing preferred skills</h3>${chips(c.missing_preferred_skills, 'chip-warn')}</div>
    <div class="card"><h3>⚠ Underrepresented</h3><div class="small dim" style="margin-bottom:6px">Mentioned once on your resume but emphasised by the job.</div>${chips(c.underrepresented_skills, 'chip-warn')}</div>
  </div>
  <div class="card" style="margin-top:16px"><h3>Keyword coverage ${c.keyword_coverage.percent != null ? `(${c.keyword_coverage.percent}%)` : ''}</h3>
    <div class="small dim">Found</div>${chips(c.keyword_coverage.found, 'chip-ok')}<div class="small dim" style="margin-top:8px">Not found on resume</div>${chips(c.keyword_coverage.missing, 'chip-miss')}</div>
  <div class="grid grid-2" style="margin-top:16px">
    <div class="card"><h3>Requirement comparison <span class="badge badge-violet">AI</span></h3>${(a.requirement_comparison || []).map(q => `<div class="list-item"><span class="badge ${q.status === 'met' ? 'badge-success' : q.status === 'partial' ? 'badge-warning' : 'badge-danger'}">${esc(q.status)}</span><div><b>${esc(q.requirement)}</b><div class="small muted">${esc(q.note)}</div></div></div>`).join('') || '<span class="dim small">None</span>'}</div>
    <div class="card"><h3>Tailoring suggestions <span class="badge badge-violet">AI</span></h3>${(a.tailored_suggestions || []).map(s => `<div class="list-item" style="display:block"><b>${esc(s.section)}</b><div class="small muted">${esc(s.suggestion)}</div>${s.example_bullet ? `<div class="small" style="margin-top:6px"><i>${esc(s.example_bullet)}</i></div>` : ''}</div>`).join('') || '<span class="dim small">None</span>'}
      ${(a.keywords_to_add || []).length ? `<h3 style="margin-top:14px">Keywords to add (if true for you)</h3>${chips(a.keywords_to_add)}` : ''}
      <div class="small dim" style="margin-top:10px">Example wording is a suggestion — only use what is true for you. No hiring outcome is implied.</div></div></div>`;
  scoreRing(root.querySelector('#jmRing'), c.score, 100);
}

export function renderSkillGap(root, r) {
  const g = r.data.gap, p = r.data.plan || {};
  root.innerHTML = `<div class="card stack">
    <div class="score-hero"><div class="score-ring" id="sgRing" role="img" aria-label="Skill coverage ${esc(g.coverage_percent)} percent"></div>
      <div class="stack" style="flex:1;min-width:240px"><h2 style="margin:0">${esc(r.inputs.target_role || 'Target role')}</h2><p class="muted">${esc(p.summary || '')}</p>
        <div class="small dim">Required skills from: ${esc(g.role_source)}</div></div></div>
    <div class="alert alert-info small">${esc(g.verification_note)}</div></div>
  <div class="compare-grid" style="margin-top:16px">
    <div class="card"><h3>✅ Skills your resume shows</h3>${chips(g.matched_skills, 'chip-ok')}</div>
    <div class="card"><h3>❌ Missing skills</h3>${chips(g.missing_skills, 'chip-miss')}</div></div>
  <div class="card" style="margin-top:16px"><div class="card-title"><h3>Prioritised learning plan <span class="badge badge-violet">AI</span></h3><span class="small dim">Progress is self-reported</span></div>
    ${(p.learning_plan || []).map(i => `<div class="list-item"><div class="plan-item" style="flex:1"><div class="row row-between"><b>${esc(i.skill)}</b>
        <span class="row"><span class="badge ${i.priority === 'High' ? 'badge-danger' : i.priority === 'Medium' ? 'badge-warning' : ''}">${esc(i.priority)}</span><span class="small dim">~${esc(i.estimated_weeks)} wks</span>
        <select data-skill="${esc(i.skill)}" aria-label="Progress for ${esc(i.skill)}">${['todo', 'in_progress', 'done'].map(s => `<option value="${s}" ${i.status === s ? 'selected' : ''}>${{ todo: 'To do', in_progress: 'In progress', done: 'Done' }[s]}</option>`).join('')}</select></span></div>
        <div class="small muted">${esc(i.why)}</div>${i.practice_task ? `<div class="small">🛠 ${esc(i.practice_task)}</div>` : ''}${(i.resources || []).length ? `<div class="small dim">🎓 ${i.resources.map(esc).join(' · ')}</div>` : ''}</div></div>`).join('') || '<span class="dim small">No plan items.</span>'}</div>
  <div class="card" style="margin-top:16px"><h3>Project ideas <span class="badge badge-violet">AI</span></h3><div class="compare-grid">${(p.project_ideas || []).map(x => `<div class="list-item" style="display:block"><b>${esc(x.title)}</b> <span class="badge">${esc(x.difficulty)}</span><div class="small muted">${esc(x.description)}</div>${chips(x.skills_practiced)}</div>`).join('')}</div></div>`;
  scoreRing(root.querySelector('#sgRing'), g.coverage_percent, 100);
  root.querySelectorAll('select[data-skill]').forEach(s => s.addEventListener('change', async () => {
    try { await api(`/api/reports/${r.id}/progress`, { method: 'PATCH', json: { skill: s.dataset.skill, status: s.value } }); toast('Progress saved.', 'success'); }
    catch (e) { toast(e.message, 'error'); }
  }));
}

export function renderInterviewSummary(root, s) {
  const done = s.answers || [];
  const scored = done.filter(a => !a.skipped);
  root.innerHTML = `<div class="card stack"><div class="score-hero"><div class="score-ring" id="ivRing" role="img" aria-label="Average score ${esc(s.average_score ?? 0)} out of 10"></div>
    <div class="stack"><h2 style="margin:0">${esc(s.target_role || 'Interview session')}</h2>
      <div class="muted">${esc(s.candidate_name)} · ${esc(s.difficulty)} · ${s.answered}/${s.total_questions} answered · ${esc(s.status.replace('_', ' '))}</div>
      <div class="small dim">${esc(s.disclaimer)}</div></div></div></div>
    <div class="stack" style="margin-top:16px">${done.map(a => `<div class="card"><div class="row row-between"><span class="badge">${esc(a.category)}</span><b>${a.skipped ? 'Skipped' : esc(a.score) + '/10'}</b></div>
      <h3 style="margin-top:8px">Q${a.index + 1}. ${esc(a.question)}</h3>
      ${a.skipped ? '' : `<p class="muted">${esc(a.answer)}</p><div class="grid grid-2"><div><b class="small">Strengths</b><ul>${(a.evaluation.strengths || []).map(x => `<li>${esc(x)}</li>`).join('')}</ul></div>
        <div><b class="small">To improve</b><ul>${(a.evaluation.weaknesses || []).map(x => `<li>${esc(x)}</li>`).join('')}</ul></div></div>
        <p>${esc(a.evaluation.detailed_feedback || '')}</p><div class="alert alert-info small"><b>Model answer:</b> ${esc(a.evaluation.model_answer || '')}</div>`}</div>`).join('') || '<div class="empty">No answers recorded yet.</div>'}</div>`;
  scoreRing(root.querySelector('#ivRing'), s.average_score || 0, 10, 1);
}

export function renderChatTranscript(root, d) {
  root.innerHTML = `<div class="card"><h2>${esc(d.session.title)}</h2><div class="small dim">Resume: ${esc(d.session.resume_filename)}</div></div>
    <div class="chat-log" style="max-height:none">${d.messages.map(m => `<div class="msg ${m.role}">${esc(m.content)}</div>`).join('') || '<div class="empty">No messages.</div>'}</div>`;
}
export { fmtDate };
