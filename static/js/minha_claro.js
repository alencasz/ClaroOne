(() => {
  const { api, jsonRequest, showAlert, hideAlert, queryCpf, formatCpf, friendly, formatEntity, initials, currency } = ClaroOne;
  const alertBox = document.getElementById('mc-alert');
  const cpfInput = document.getElementById('mc-cpf');
  let session = null;

  function step(name) {
    document.querySelectorAll('.mc-step').forEach(section => section.classList.toggle('active', section.dataset.step === name));
    hideAlert(alertBox);
  }

  function areaType(item) {
    const haystack = [item.intent, item.category, item.initial_department, item.destination_department].join(' ').toUpperCase();
    if (/FATUR|COBRAN|FINANCE/.test(haystack)) return 'billing';
    if (/INTERNET|CONEXAO|CONEXÃO|BANDA_LARGA/.test(haystack)) return 'internet';
    if (/TELEFON|LINHA|MOVEL|MÓVEL/.test(haystack)) return 'phone';
    if (/CANCEL/.test(haystack)) return 'cancel';
    return 'generic';
  }

  async function search() {
    const button = document.getElementById('mc-search'); button.disabled = true;
    try {
      session = await api(`/api/sessions/active/${encodeURIComponent(cpfInput.value)}`);
      localStorage.setItem('claroOneCpf', session.cpf);
      document.getElementById('mc-name').textContent = session.customer_name;
      document.getElementById('mc-initials').textContent = initials(session.customer_name);
      document.getElementById('mc-protocol').textContent = session.protocol;
      const type = areaType(session);
      const titles = { billing: 'Encontramos uma solicitação relacionada à sua fatura.', internet: 'Encontramos um atendimento sobre sua internet.', phone: 'Encontramos um atendimento relacionado à sua linha.', cancel: 'Encontramos uma solicitação sobre seu plano.', generic: 'Encontramos um atendimento em andamento.' };
      document.getElementById('mc-context-title').textContent = titles[type];
      document.getElementById('mc-problem').textContent = session.problem || session.summary;
      const preview = document.getElementById('mc-entity-preview'); preview.innerHTML = '';
      Object.entries(session.structured_context || {}).filter(([,v]) => v !== null).slice(0, 3).forEach(([key, value]) => {
        const div = document.createElement('div'); div.innerHTML = `<small>${friendly(key)}</small><strong>${formatEntity(key, value)}</strong>`; preview.appendChild(div);
      });
      step('found');
    } catch (error) { showAlert(alertBox, error.message); }
    finally { button.disabled = false; }
  }

  document.getElementById('mc-search').addEventListener('click', search);
  cpfInput.addEventListener('keydown', event => { if (event.key === 'Enter') search(); });
  document.getElementById('mc-continue').addEventListener('click', async () => {
    const button = document.getElementById('mc-continue'); button.disabled = true;
    try {
      session = await api(`/api/sessions/${session.id}/resume`, jsonRequest('POST', { channel: 'MINHA_CLARO' }));
      renderAdaptive(); step('adaptive');
    } catch (error) { showAlert(alertBox, error.message); button.disabled = false; }
  });
  document.getElementById('mc-back').addEventListener('click', () => step('found'));

  function renderAdaptive() {
    const type = areaType(session);
    const entity = session.structured_context || {};
    const configurations = {
      billing: { icon: '▤', label: 'FATURAS', title: 'Fatura atual', trail: ['Início', 'Faturas', 'Fatura atual'], item: entity.produto || 'Item relacionado à solicitação', status: 'Contestação em andamento', detailLabel: 'Valor relacionado', detail: entity.valor !== undefined && entity.valor !== null ? currency(entity.valor) : 'Consulte os detalhes' },
      internet: { icon: '⌁', label: 'INTERNET', title: 'Status da conexão', trail: ['Início', 'Internet', 'Suporte'], item: entity.equipamento || 'Diagnóstico de conexão', status: 'Atendimento em andamento', detailLabel: 'Situação informada', detail: session.problem },
      phone: { icon: '▯', label: 'MINHA LINHA', title: 'Atendimento da linha', trail: ['Início', 'Minha linha', 'Suporte'], item: entity.linha || 'Linha vinculada ao CPF', status: 'Atendimento relacionado à linha', detailLabel: 'Situação informada', detail: session.problem },
      cancel: { icon: '⊘', label: 'PLANO E SERVIÇOS', title: 'Solicitação em andamento', trail: ['Início', 'Plano e serviços', 'Solicitação'], item: entity.plano || entity.produto || 'Plano atual', status: 'Solicitação de cancelamento em andamento', detailLabel: 'Próxima ação', detail: friendly(session.suggested_action) },
      generic: { icon: '◫', label: 'ATENDIMENTO', title: friendly(session.category || 'Solicitação'), trail: ['Início', 'Atendimento', 'Solicitação'], item: session.problem || 'Solicitação em andamento', status: 'Contexto recuperado', detailLabel: 'Setor responsável', detail: friendly(session.destination_department) }
    };
    const c = configurations[type];
    const safe = value => String(value || '—').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));
    document.getElementById('adaptive-content').innerHTML = `
      <div class="adaptive-hero"><div class="adaptive-icon">${c.icon}</div><div><span>${safe(c.label)}</span><h2>${safe(c.title)}</h2></div></div>
      <div class="breadcrumb">${c.trail.map((x,i) => `${i ? '<i>›</i>' : ''}<b>${safe(x)}</b>`).join('')}</div>
      <article class="service-detail"><header><strong>${safe(c.item)}</strong><span>CONTEXTO RECUPERADO</span></header><div class="service-line"><div><small>${safe(c.detailLabel)}</small><strong>${safe(c.detail)}</strong></div></div><div class="service-line"><div><small>Status</small><strong>${safe(c.status)}</strong></div><b>Em análise</b></div></article>
      <div class="case-progress"><b>CCE · ${safe(session.protocol)}</b>Você chegou diretamente aqui porque o contexto do atendimento anterior foi preservado.</div>
      <p class="adapted-summary">${safe(session.summary)}</p>`;
  }
  const initialCpf = queryCpf(); if (initialCpf) { cpfInput.value = formatCpf(initialCpf); search(); }
})();
