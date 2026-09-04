(() => {
  const { api, jsonRequest, showAlert, hideAlert, queryCpf, formatCpf, friendly, formatEntity, initials, currency } = ClaroOne;
  const categoryLabel = ClaroOne.categoryLabel || friendly;
  const departmentLabel = ClaroOne.departmentLabel || friendly;
  const categoryArea = ClaroOne.categoryArea || (() => 'generic');
  const alertBox = document.getElementById('mc-alert');
  const cpfInput = document.getElementById('mc-cpf');
  const ongoingCard = document.getElementById('mc-ongoing-card');
  const manualHome = document.getElementById('mc-manual-home');
  let customer = null;
  let session = null;

  function step(name) {
    document.querySelectorAll('.mc-step').forEach(section => section.classList.toggle('active', section.dataset.step === name));
    hideAlert(alertBox);
  }

  function renderCustomer() {
    document.getElementById('mc-name').textContent = customer.name;
    document.getElementById('mc-initials').textContent = initials(customer.name);
  }

  async function search() {
    const button = document.getElementById('mc-search');
    button.disabled = true;
    try {
      customer = await api(`/api/customers/${encodeURIComponent(cpfInput.value)}`);
      localStorage.setItem('claroOneCpf', customer.cpf);
      renderCustomer();
      try {
        session = await api(`/api/sessions/active/${encodeURIComponent(customer.cpf)}`);
        renderContextCard();
        ongoingCard.classList.remove('hidden');
        manualHome.classList.add('hidden');
      } catch (activeError) {
        if (activeError.status !== 404) throw activeError;
        session = null;
        ongoingCard.classList.add('hidden');
        manualHome.classList.remove('hidden');
      }
      step('found');
    } catch (error) {
      showAlert(alertBox, error.message);
    } finally {
      button.disabled = false;
    }
  }

  function renderContextCard() {
    document.getElementById('mc-protocol').textContent = session.protocol;
    const type = categoryArea(session.category);
    const titles = {
      billing: 'Encontramos uma solicitação relacionada à sua fatura.',
      internet: 'Encontramos um atendimento sobre sua internet.',
      phone: 'Encontramos um atendimento relacionado à sua linha.',
      cancel: 'Encontramos uma solicitação sobre seu plano.',
      generic: 'Encontramos um atendimento em andamento.'
    };
    document.getElementById('mc-context-title').textContent = titles[type];
    document.getElementById('mc-problem').textContent = session.problem || session.summary;
    document.getElementById('mc-category').textContent = categoryLabel(session.category);
    document.getElementById('mc-destination').textContent = departmentLabel(session.destination_department);
    const preview = document.getElementById('mc-entity-preview');
    preview.innerHTML = '';
    Object.entries(session.structured_context || {}).filter(([, value]) => value !== null).slice(0, 3).forEach(([key, value]) => {
      const item = document.createElement('div');
      const label = document.createElement('small'); label.textContent = friendly(key);
      const content = document.createElement('strong'); content.textContent = formatEntity(key, value);
      item.append(label, content); preview.appendChild(item);
    });
  }

  async function continueContext() {
    const button = document.getElementById('mc-continue');
    button.disabled = true;
    try {
      session = await api(`/api/sessions/${session.id}/resume`, jsonRequest('POST', { channel: 'MINHA_CLARO' }));
      renderContextArea();
      step('adaptive');
    } catch (error) {
      showAlert(alertBox, error.message);
      button.disabled = false;
    }
  }

  const safe = value => String(value ?? '—').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[char]));
  function pageMarkup(config, contextMessage = '') {
    return `
      <div class="adaptive-hero"><div class="adaptive-icon">${config.icon}</div><div><span>${safe(config.label)}</span><h2>${safe(config.title)}</h2></div></div>
      <div class="breadcrumb">${config.trail.map((item, index) => `${index ? '<i>›</i>' : ''}<b>${safe(item)}</b>`).join('')}</div>
      <article class="service-detail"><header><strong>${safe(config.item)}</strong><span>${safe(config.badge)}</span></header><div class="service-line"><div><small>${safe(config.detailLabel)}</small><strong>${safe(config.detail)}</strong></div></div><div class="service-line"><div><small>Status</small><strong>${safe(config.status)}</strong></div><b>Dados simulados</b></div></article>
      ${contextMessage}`;
  }

  function renderContextArea() {
    const type = categoryArea(session.category);
    const entity = session.structured_context || {};
    const configurations = {
      billing: { icon: '▤', label: 'FATURAS', title: 'Fatura atual', trail: ['Início', 'Faturas', 'Fatura atual'], item: entity.produto || 'Item relacionado à solicitação', badge: 'CONTEXTO RECUPERADO', status: 'Contestação em andamento', detailLabel: 'Valor relacionado', detail: entity.valor !== undefined && entity.valor !== null ? currency(entity.valor) : 'Consulte os detalhes' },
      internet: { icon: '⌁', label: 'INTERNET', title: 'Status da conexão', trail: ['Início', 'Internet', 'Suporte'], item: entity.equipamento || 'Diagnóstico de conexão', badge: 'CONTEXTO RECUPERADO', status: 'Atendimento em andamento', detailLabel: 'Situação informada', detail: session.problem },
      phone: { icon: '▯', label: 'MINHA LINHA', title: 'Atendimento da linha', trail: ['Início', 'Minha linha', 'Suporte'], item: entity.linha || 'Linha vinculada ao CPF', badge: 'CONTEXTO RECUPERADO', status: 'Atendimento relacionado à linha', detailLabel: 'Situação informada', detail: session.problem },
      cancel: { icon: '⊘', label: 'PLANO E SERVIÇOS', title: 'Solicitação em andamento', trail: ['Início', 'Plano e serviços', 'Solicitação'], item: entity.plano || entity.produto || 'Plano atual', badge: 'CONTEXTO RECUPERADO', status: 'Cancelamento em andamento', detailLabel: 'Próxima ação', detail: friendly(session.suggested_action) },
      generic: { icon: '◫', label: 'ATENDIMENTO GERAL', title: categoryLabel(session.category), trail: ['Início', 'Atendimento', 'Solicitação'], item: session.problem || session.summary || 'Solicitação em andamento', badge: 'CONTEXTO RECUPERADO', status: 'Atendimento em andamento', detailLabel: 'Encaminhamento', detail: departmentLabel(session.destination_department) }
    };
    const message = `<div class="case-progress"><b>CCE · ${safe(session.protocol)}</b>Você chegou diretamente aqui porque o contexto do atendimento anterior foi preservado.</div><p class="adapted-summary">${safe(session.summary)}</p>`;
    document.getElementById('adaptive-content').innerHTML = pageMarkup(configurations[type], message);
  }

  function renderManualArea(area) {
    const configurations = {
      billing: { icon: '▤', label: 'FATURAS', title: 'Minhas faturas', trail: ['Início', 'Faturas'], item: 'Fatura atual', badge: 'AUTOATENDIMENTO', detailLabel: 'Opções', detail: 'Consultar fatura e itens', status: 'Área disponível' },
      payments: { icon: '$', label: 'PAGAMENTOS', title: 'Pagamentos', trail: ['Início', 'Pagamentos'], item: 'Formas de pagamento', badge: 'AUTOATENDIMENTO', detailLabel: 'Opções', detail: 'Código de barras e pagamento', status: 'Área disponível' },
      internet: { icon: '⌁', label: 'INTERNET', title: 'Minha internet', trail: ['Início', 'Internet'], item: 'Serviços de internet', badge: 'AUTOATENDIMENTO', detailLabel: 'Opções', detail: 'Status e suporte da conexão', status: 'Dados não consultados' },
      phone: { icon: '▯', label: 'MINHA LINHA', title: 'Minha linha', trail: ['Início', 'Minha linha'], item: 'Serviços da linha', badge: 'AUTOATENDIMENTO', detailLabel: 'Opções', detail: 'Consumo e suporte da linha', status: 'Dados não consultados' },
      plans: { icon: '＋', label: 'PLANOS', title: 'Planos e serviços', trail: ['Início', 'Planos'], item: 'Gerenciar serviços', badge: 'AUTOATENDIMENTO', detailLabel: 'Opções', detail: 'Consultar planos e serviços', status: 'Área disponível' }
    };
    document.getElementById('adaptive-content').innerHTML = pageMarkup(configurations[area]);
    step('adaptive');
  }

  document.getElementById('mc-search').addEventListener('click', search);
  cpfInput.addEventListener('keydown', event => { if (event.key === 'Enter') search(); });
  document.getElementById('mc-continue').addEventListener('click', continueContext);
  document.getElementById('mc-back').addEventListener('click', () => step('found'));
  document.querySelectorAll('.quick-grid button').forEach(button => button.addEventListener('click', () => renderManualArea(button.dataset.area)));

  const initialCpf = queryCpf();
  if (initialCpf) { cpfInput.value = formatCpf(initialCpf); search(); }
})();
