(() => {
  const { api, jsonRequest, showAlert, hideAlert, queryCpf, formatCpf, friendly, brDate } = ClaroOne;
  const alertBox = document.getElementById('wa-alert');
  const cpfInput = document.getElementById('wa-cpf');
  let session = null;

  function step(name) {
    document.querySelectorAll('.wa-step').forEach(section => section.classList.toggle('active', section.dataset.step === name));
    hideAlert(alertBox);
  }

  async function search() {
    const cpf = cpfInput.value;
    const button = document.getElementById('wa-search');
    button.disabled = true; hideAlert(alertBox);
    try {
      session = await api(`/api/sessions/active/${encodeURIComponent(cpf)}`);
      localStorage.setItem('claroOneCpf', session.cpf);
      document.getElementById('wa-cpf-bubble').textContent = formatCpf(session.cpf);
      document.getElementById('wa-problem').textContent = session.problem || session.summary || 'Atendimento em andamento';
      document.getElementById('wa-origin').textContent = friendly(session.channel_origin);
      document.getElementById('wa-department').textContent = friendly(session.initial_department);
      document.getElementById('wa-when').textContent = brDate(session.created_at);
      document.getElementById('wa-status').textContent = friendly(session.status);
      step('found');
    } catch (error) {
      if (error.status === 404) step('empty'); else showAlert(alertBox, error.message);
    } finally { button.disabled = false; }
  }

  document.getElementById('wa-search').addEventListener('click', search);
  cpfInput.addEventListener('keydown', event => { if (event.key === 'Enter') search(); });
  document.getElementById('wa-resume').addEventListener('click', async () => {
    const button = document.getElementById('wa-resume'); button.disabled = true;
    try {
      session = await api(`/api/sessions/${session.id}/resume`, jsonRequest('POST', { channel: 'WHATSAPP' }));
      document.getElementById('wa-resumed-problem').textContent = session.problem || session.summary;
      document.getElementById('wa-destination').textContent = friendly(session.destination_department || session.initial_department);
      document.getElementById('wa-agent-text').textContent = `Olá, ${session.customer_name.split(' ')[0]}. Já recebi o contexto do seu atendimento. Podemos continuar daqui.`;
      step('resumed');
      setTimeout(() => {
        document.querySelector('.system-message').classList.add('hidden');
        document.getElementById('wa-agent-message').classList.remove('hidden');
      }, 1300);
    } catch (error) { showAlert(alertBox, error.message); button.disabled = false; }
  });

  function newFlow() { step('search'); cpfInput.value = ''; }
  document.getElementById('wa-new').addEventListener('click', newFlow);
  document.getElementById('wa-empty-new').addEventListener('click', newFlow);
  const initialCpf = queryCpf(); if (initialCpf) { cpfInput.value = formatCpf(initialCpf); search(); }
})();
