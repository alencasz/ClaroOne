(() => {
  const { api, friendly, categoryLabel, departmentLabel, brDate, formatCpf, toast } = ClaroOne;
  const tableBody = document.getElementById('debug-sessions');
  const jsonCode = document.getElementById('session-json');
  const modal = document.getElementById('reset-modal');

  const maskCpf = cpf => {
    const formatted = formatCpf(cpf);
    return `***.${formatted.slice(4, 11)}-**`;
  };
  function ttl(expiresAt, status) {
    if (['RESOLVIDA', 'EXPIRADA'].includes(status)) return '—';
    const seconds = Math.max(0, Math.floor((new Date(expiresAt) - Date.now()) / 1000));
    return `${String(Math.floor(seconds / 3600)).padStart(2, '0')}:${String(Math.floor(seconds % 3600 / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
  }

  async function load() {
    const sessions = await api('/api/sessions?include_closed=true');
    tableBody.innerHTML = '';
    if (!sessions.length) tableBody.innerHTML = '<tr><td colspan="9">Nenhuma CCE armazenada.</td></tr>';
    sessions.forEach(item => {
      const row = document.createElement('tr');
      row.dataset.id = item.id;
      row.innerHTML = `<td>${item.protocol}</td><td>${maskCpf(item.cpf)}</td><td>${item.customer_name}</td><td><span class="table-status">${friendly(item.status)}</span></td><td>${categoryLabel(item.category)}</td><td>${departmentLabel(item.destination_department)}</td><td>${friendly(item.current_channel)}</td><td>${brDate(item.created_at)}</td><td>${brDate(item.expires_at)}<strong class="ttl-value" data-expires="${item.expires_at}" data-status="${item.status}">${ttl(item.expires_at, item.status)}</strong></td>`;
      row.addEventListener('click', () => show(item.id, row));
      tableBody.appendChild(row);
    });
    const queryId = new URLSearchParams(location.search).get('session');
    const targetRow = queryId && tableBody.querySelector(`[data-id="${CSS.escape(queryId)}"]`);
    if (targetRow) show(queryId, targetRow);
  }

  async function show(id, row) {
    const full = await api(`/api/sessions/${id}`);
    tableBody.querySelectorAll('tr').forEach(item => item.classList.remove('selected'));
    row?.classList.add('selected');
    document.getElementById('json-protocol').textContent = full.protocol;
    jsonCode.textContent = JSON.stringify(full, null, 2);
  }

  document.getElementById('debug-refresh').addEventListener('click', () => load().catch(error => toast(error.message, true)));
  document.getElementById('copy-json').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(jsonCode.textContent); toast('JSON copiado.'); }
    catch { toast('Não foi possível copiar o JSON.', true); }
  });
  let resetEndpoint = '/api/demo/reset';
  function openConfirmation(mode) {
    const isReset = mode === 'reset';
    resetEndpoint = isReset ? '/api/demo/reset' : '/api/demo/clear';
    document.getElementById('reset-title').textContent = isReset ? 'Reiniciar demonstração?' : 'Limpar dados da demonstração?';
    document.getElementById('reset-description').textContent = isReset
      ? 'Todas as CCEs, eventos e gravações serão removidos. Os clientes fictícios serão preservados e a demonstração ficará pronta para recomeçar.'
      : 'Todas as CCEs, eventos e gravações serão removidos. Os clientes fictícios serão preservados.';
    document.getElementById('confirm-reset').textContent = isReset ? 'Sim, reiniciar' : 'Sim, limpar';
    modal.showModal();
  }
  document.getElementById('debug-clear').addEventListener('click', () => openConfirmation('clear'));
  document.getElementById('debug-reset').addEventListener('click', () => openConfirmation('reset'));
  document.getElementById('cancel-reset').addEventListener('click', () => modal.close());
  document.getElementById('confirm-reset').addEventListener('click', async () => {
    const button = document.getElementById('confirm-reset'); button.disabled = true;
    try {
      await api(resetEndpoint, { method: 'POST' });
      localStorage.clear(); modal.close();
      document.getElementById('json-protocol').textContent = 'Selecione uma CCE';
      jsonCode.textContent = '{\n  "mensagem": "Selecione uma sessão na tabela"\n}';
      await load(); toast('Demonstração reiniciada.');
    } catch (error) { toast(error.message, true); }
    finally { button.disabled = false; }
  });
  setInterval(() => document.querySelectorAll('.ttl-value').forEach(cell => { cell.textContent = ttl(cell.dataset.expires, cell.dataset.status); }), 1000);
  load().catch(error => toast(error.message, true));
})();
