import { api } from '../core/api.js';
import { esc, setBusy, showError, toast, confirmDialog } from '../core/ui.js';
import { initResumePicker } from '../core/resume-picker.js';

const $ = id => document.getElementById(id);
let rid = null, sid = null;

const picker = await initResumePicker($('picker'), { onChange: id => { rid = id; sid = null; loadSessions(); clearLog(); } });
rid = picker.id;

const clearLog = () => { $('log').innerHTML = '<div class="empty"><div class="empty-icon">💬</div>Start a new chat or pick one on the left.</div>'; };
const addMsg = (role, text) => {
  const d = document.createElement('div'); d.className = `msg ${role}`; d.textContent = text; // textContent: never interpreted as HTML
  const log = $('log'); if (log.querySelector('.empty')) log.innerHTML = ''; log.appendChild(d); log.scrollTop = log.scrollHeight; return d;
};

async function loadSessions() {
  if (!rid) { $('sessList').innerHTML = ''; return; }
  try {
    const { sessions } = await api(`/api/chat/sessions?resume_id=${rid}`);
    $('sessList').innerHTML = sessions.map(s => `<div class="row" style="flex-wrap:nowrap"><button class="sess" style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" data-id="${s.id}" ${s.id === sid ? 'aria-current="true"' : ''}>${esc(s.title)}</button>
      <button class="icon-btn" style="width:32px;height:32px" data-del="${s.id}" aria-label="Delete chat">🗑</button></div>`).join('') || '<div class="small dim">No chats yet.</div>';
  } catch (e) { toast(e.message, 'error'); }
}
async function open(id) {
  const d = await api(`/api/chat/sessions/${id}`); sid = id; $('log').innerHTML = '';
  d.messages.forEach(m => addMsg(m.role, m.content)); if (!d.messages.length) clearLog(); loadSessions();
}
async function newChat() {
  if (!rid) { toast('Select or upload a resume first.', 'error'); return null; }
  const d = await api('/api/chat/sessions', { method: 'POST', json: { resume_id: rid } }); sid = d.session.id; clearLog(); await loadSessions(); return sid;
}
$('newChat').addEventListener('click', () => newChat().catch(e => toast(e.message, 'error')));
$('sessList').addEventListener('click', async e => {
  const o = e.target.closest('[data-id]'), del = e.target.closest('[data-del]');
  try {
    if (o) await open(Number(o.dataset.id));
    if (del && await confirmDialog('Delete this conversation?')) { await api(`/api/chat/sessions/${del.dataset.del}`, { method: 'DELETE' }); if (sid === Number(del.dataset.del)) { sid = null; clearLog(); } loadSessions(); }
  } catch (err) { toast(err.message, 'error'); }
});

async function send(text) {
  $('chatErr').innerHTML = '';
  if (!text.trim()) return;
  if (!sid && !(await newChat().catch(e => { showError($('chatErr'), e); return null; }))) return;
  const pending = addMsg('user', text); const thinking = addMsg('assistant', 'Thinking…');
  setBusy($('sendBtn'), true, 'Sending'); $('msg').disabled = true;
  try {
    const d = await api(`/api/chat/sessions/${sid}/messages`, { method: 'POST', idempotent: true, json: { message: text } });
    thinking.textContent = d.message.content; $('msg').value = ''; loadSessions();
  } catch (e) { pending.remove(); thinking.remove(); showError($('chatErr'), e); }
  finally { setBusy($('sendBtn'), false); $('msg').disabled = false; $('msg').focus(); $('log').scrollTop = $('log').scrollHeight; }
}
$('chatForm').addEventListener('submit', e => { e.preventDefault(); send($('msg').value); });
$('msg').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('chatForm').requestSubmit(); } });
$('suggest').addEventListener('click', e => { const b = e.target.closest('[data-q]'); if (b) send(b.dataset.q); });
loadSessions();
