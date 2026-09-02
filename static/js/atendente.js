(() => {
  const { api, showAlert, hideAlert, friendly, brDate, brTime, formatEntity, initials, formatCpf } = ClaroOne;
  const list = document.getElementById('session-list');
  const content = document.getElementById('cockpit-content');
  const empty = document.getElementById('cockpit-empty');
  const alertBox = document.getElementById('cp-alert');
  const modal = document.getElementById('transcript-modal');
  let sessions = [];
  let selected = null;

  const maskCpf = cpf => { const f = formatCpf(cpf); return `***.${f.slice(4, 11)}-**`; };
  async function loadSessions(preferredId) {
    sessions = await api('/api/sessions?include_closed=false');
    document.getElementById('session-count').textContent = sessions.length;
    list.innerHTML = '';
    if (!sessions.length) { list.innerHTML = '<div class="sidebar-loading">Nenhuma CCE relevante.</div>'; return; }
    sessions.forEach(item => {
      const button = document.createElement('button'); button.className = `session-item${item.id === selected?.id ? ' active' : ''}`;
      button.innerHTML = `<span><b>${item.protocol}</b><time>${brTime(item.updated_at)}</time></span><strong>${item.customer_name}</strong><small>${item.problem || item.summary || friendly(item.status)}</small>`;
      button.addEventListener('click', () => selectSession(item.id)); list.appendChild(button);
    });
    const target = preferredId || new URLSearchParams(location.search).get('session') || sessions[0].id;
    await selectSession(target);
  }

  async function selectSession(id) {
    try {
      selected = await api(`/api/sessions/${id}`);
      [...list.children].forEach((node, index) => node.classList?.toggle('active', sessions[index]?.id === id));
      render(); empty.classList.add('hidden'); content.classList.remove('hidden');
    } catch (error) { ClaroOne.toast(error.message, true); }
  }

  function set(id, value) { document.getElementById(id).textContent = value ?? '—'; }
  function render() {
    hideAlert(alertBox);
    set('cp-initials', initials(selected.customer_name)); set('cp-name', selected.customer_name); set('cp-cpf', maskCpf(selected.cpf)); set('cp-protocol', selected.protocol);
    set('cp-status', friendly(selected.status)); set('cp-origin', friendly(selected.channel_origin)); set('cp-channel', friendly(selected.current_channel));
    set('cp-intent', friendly(selected.intent)); set('cp-problem', selected.problem || 'Não identificado'); set('cp-summary', selected.summary || 'Contexto ainda não processado.');
    set('cp-category', friendly(selected.category)); set('cp-destination', friendly(selected.destination_department)); set('cp-priority', friendly(selected.priority)); set('cp-action', friendly(selected.suggested_action));
    const entities = document.getElementById('cp-entities'); entities.innerHTML = '';
    const entries = Object.entries(selected.structured_context || {}).filter(([,value]) => value !== null);
    if (!entries.length) entities.innerHTML = '<p class="muted-empty">Nenhuma entidade extraída.</p>';
    entries.forEach(([key,value]) => { const card = document.createElement('div'); card.className = 'entity-card'; const label = document.createElement('small'); label.textContent = friendly(key); const strong = document.createElement('strong'); strong.textContent = formatEntity(key,value); card.append(label,strong); entities.appendChild(card); });
    const timeline = document.getElementById('cp-timeline'); timeline.innerHTML = '';
    (selected.events || []).forEach(event => { const item = document.createElement('div'); item.className = 'timeline-item'; item.innerHTML = `<time>${brTime(event.created_at)}</time><span class="timeline-marker"><i></i></span><span><b>${friendly(event.channel).toUpperCase()}</b><small>${event.description}</small></span>`; timeline.appendChild(item); });
    document.getElementById('cp-handoff').disabled = ['RESOLVIDA','EXPIRADA'].includes(selected.status);
    document.getElementById('cp-resolve').disabled = ['RESOLVIDA','EXPIRADA'].includes(selected.status);
  }

  document.getElementById('view-transcript').addEventListener('click', () => {
    modal.innerHTML = `<div class="modal-heading"><div><span class="eyebrow">IA DE TRANSCRIÇÃO · ÁUDIO → TEXTO</span><h2>Transcrição original</h2></div><button aria-label="Fechar">×</button></div><p>Transcrição gerada pela IA de voz</p><blockquote></blockquote>`;
    modal.querySelector('blockquote').textContent = selected.transcript || 'Nenhuma transcrição disponível.';
    modal.querySelector('button').addEventListener('click', () => modal.close()); modal.showModal();
  });
  document.getElementById('cp-handoff').addEventListener('click', async () => { try { selected = await api(`/api/sessions/${selected.id}/handoff`, {method:'POST'}); selected.events = await api(`/api/sessions/${selected.id}/events`); render(); showAlert(alertBox, 'Atendimento assumido. O handoff foi registrado na timeline.', true); await loadSessions(selected.id); } catch(error){showAlert(alertBox,error.message);} });
  document.getElementById('cp-resolve').addEventListener('click', async () => { if(!confirm('Marcar esta sessão como resolvida? Ela não poderá mais ser retomada.')) return; try { await api(`/api/sessions/${selected.id}/resolve`, {method:'POST'}); ClaroOne.toast('Sessão resolvida.'); content.classList.add('hidden'); empty.classList.remove('hidden'); selected=null; await loadSessions(); } catch(error){showAlert(alertBox,error.message);} });
  loadSessions().catch(error => { list.innerHTML = `<div class="sidebar-loading">${error.message}</div>`; });
})();
