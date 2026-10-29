import { api } from '../core/api.js';
import { esc, fmtDate } from '../core/ui.js';
let page = 1; const per = 15;
async function load() {
  const d = await api(`/api/credits?page=${page}&per_page=${per}`);
  document.getElementById('balanceBig').textContent = d.balance;
  document.getElementById('txBody').innerHTML = d.transactions.length ? d.transactions.map(t => `<tr>
    <td>${esc(fmtDate(t.created_at))}</td><td>${esc(t.description)}</td>
    <td><span class="badge ${t.type === 'refund' ? 'badge-success' : t.type === 'initial_grant' ? 'badge-violet' : ''}">${esc(t.type.replace('_', ' '))}${t.status === 'refunded' ? ' · refunded' : ''}</span></td>
    <td class="tx-amt ${t.amount > 0 ? 'pos' : 'neg'}">${t.amount > 0 ? '+' : ''}${esc(t.amount)}</td><td>${esc(t.balance_after)}</td></tr>`).join('')
    : '<tr><td colspan="5" class="empty">No transactions.</td></tr>';
  document.getElementById('pageLbl').textContent = `Page ${page}`;
  document.getElementById('prev').disabled = page === 1;
  document.getElementById('next').disabled = d.transactions.length < per;
}
document.getElementById('prev').onclick = () => { page--; load(); };
document.getElementById('next').onclick = () => { page++; load(); };
load();
