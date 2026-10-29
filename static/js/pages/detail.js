import { api } from '../core/api.js';
import { esc, fmtDate, showError } from '../core/ui.js';
import { renderAts } from '../core/ats-render.js';
import { renderJobMatch, renderSkillGap, renderInterviewSummary, renderChatTranscript } from '../core/report-render.js';

const box = document.getElementById('detail'), { kind, id } = box.dataset;
const head = document.getElementById('heading'), actions = document.getElementById('actions');
try {
  if (['ats', 'job_match', 'skill_gap'].includes(kind)) {
    const { report: r } = await api(`/api/reports/${id}`);
    head.textContent = r.title;
    actions.innerHTML = `<span class="small dim">${esc(fmtDate(r.created_at))}</span><a class="btn btn-ghost btn-sm" href="/api/reports/${r.id}/export.pdf">⬇ Download PDF</a>`;
    if (kind === 'ats') renderAts(box, r.data); else if (kind === 'job_match') renderJobMatch(box, r); else renderSkillGap(box, r);
  } else if (kind === 'interview') {
    const { session } = await api(`/api/interview/${id}`); head.textContent = 'Interview session'; renderInterviewSummary(box, session);
  } else {
    const d = await api(`/api/chat/sessions/${id}`); head.textContent = 'Resume chat'; renderChatTranscript(box, d);
  }
} catch (e) { showError(box, e); }
