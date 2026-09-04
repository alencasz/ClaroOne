(() => {
  const { api, jsonRequest, showAlert, hideAlert, queryCpf, formatCpf, friendly, categoryLabel, departmentLabel, brDate } = ClaroOne;
  const alertBox = document.getElementById('wa-alert');
  const cpfInput = document.getElementById('wa-cpf');
  const messageInput = document.getElementById('wa-message-input');
  const sendButton = document.getElementById('wa-send');
  let customer = null;
  let session = null;

  function step(name) {
    document.querySelectorAll('.wa-step').forEach(section => section.classList.toggle('active', section.dataset.step === name));
    const composing = name === 'compose';
    messageInput.disabled = !composing;
    sendButton.disabled = !composing;
    hideAlert(alertBox);
    if (composing) setTimeout(() => messageInput.focus(), 50);
  }

  async function search() {
    const button = document.getElementById('wa-search');
    button.disabled = true;
    hideAlert(alertBox);
    try {
      customer = await api(`/api/customers/${encodeURIComponent(cpfInput.value)}`);
      localStorage.setItem('claroOneCpf', customer.cpf);
      try {
        session = await api(`/api/sessions/active/${encodeURIComponent(customer.cpf)}`);
        document.getElementById('wa-cpf-bubble').textContent = formatCpf(session.cpf);
        document.getElementById('wa-problem').textContent = session.problem || session.summary || 'Atendimento em andamento';
        document.getElementById('wa-origin').textContent = friendly(session.channel_origin);
        document.getElementById('wa-category').textContent = categoryLabel(session.category);
        document.getElementById('wa-destination-found').textContent = departmentLabel(session.destination_department);
        document.getElementById('wa-when').textContent = brDate(session.created_at);
        document.getElementById('wa-status').textContent = friendly(session.status);
        step('found');
      } catch (activeError) {
        if (activeError.status !== 404) throw activeError;
        session = null;
        step('empty');
      }
    } catch (error) {
      showAlert(alertBox, error.message);
    } finally {
      button.disabled = false;
    }
  }

  function openComposer() {
    document.getElementById('wa-compose-name').textContent = customer.name.split(' ')[0];
    messageInput.value = '';
    step('compose');
  }

  async function replaceWithNewConversation() {
    if (!confirm('O atendimento atual será removido. Deseja iniciar uma nova conversa?')) return;
    const button = document.getElementById('wa-new');
    button.disabled = true;
    try {
      await api(`/api/sessions/${session.id}`, { method: 'DELETE' });
      session = null;
      localStorage.removeItem('claroOneSession');
      openComposer();
    } catch (error) {
      showAlert(alertBox, error.message);
    } finally {
      button.disabled = false;
    }
  }

  async function resumeConversation() {
    const button = document.getElementById('wa-resume');
    button.disabled = true;
    try {
      session = await api(`/api/sessions/${session.id}/resume`, jsonRequest('POST', { channel: 'WHATSAPP' }));
      session = await api(`/api/sessions/${session.id}/route-human`, jsonRequest('POST', { channel: 'WHATSAPP' }));
      document.getElementById('wa-resumed-problem').textContent = session.problem || session.summary;
      document.getElementById('wa-destination').textContent = departmentLabel(session.destination_department);
      document.getElementById('wa-agent-text').textContent = `Olá, ${session.customer_name.split(' ')[0]}. Já recebi o contexto do seu atendimento. Podemos continuar daqui.`;
      step('resumed');
      setTimeout(() => {
        document.querySelector('.system-message:not(.context-loading)')?.classList.add('hidden');
        document.getElementById('wa-agent-message').classList.remove('hidden');
      }, 1100);
    } catch (error) {
      showAlert(alertBox, error.message);
      button.disabled = false;
    }
  }

  async function sendMessage() {
    const message = messageInput.value.trim();
    if (message.length < 3) {
      showAlert(alertBox, 'Escreva uma mensagem com pelo menos 3 caracteres.');
      return;
    }
    messageInput.disabled = true;
    sendButton.disabled = true;
    document.getElementById('wa-new-message').textContent = message;
    step('creating');
    try {
      const result = await api('/api/sessions/message', jsonRequest('POST', { cpf: customer.cpf, message }));
      session = result.session;
      localStorage.setItem('claroOneSession', session.id);
      document.getElementById('wa-created-message').textContent = message;
      document.getElementById('wa-created-problem').textContent = session.problem || session.summary || 'Solicitação identificada';
      document.getElementById('wa-created-destination').textContent = departmentLabel(session.destination_department);
      document.getElementById('wa-created-agent').textContent = `Olá, ${customer.name.split(' ')[0]}. Já recebi o contexto da sua mensagem e podemos continuar daqui.`;
      step('created');
    } catch (error) {
      step('compose');
      messageInput.value = message;
      showAlert(alertBox, error.message);
    }
  }

  document.getElementById('wa-search').addEventListener('click', search);
  cpfInput.addEventListener('keydown', event => { if (event.key === 'Enter') search(); });
  document.getElementById('wa-resume').addEventListener('click', resumeConversation);
  document.getElementById('wa-new').addEventListener('click', replaceWithNewConversation);
  document.getElementById('wa-empty-new').addEventListener('click', openComposer);
  sendButton.addEventListener('click', sendMessage);
  messageInput.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendMessage(); }
  });

  const initialCpf = queryCpf();
  if (initialCpf) { cpfInput.value = formatCpf(initialCpf); search(); }
})();
