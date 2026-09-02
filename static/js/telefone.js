(() => {
  const { api, jsonRequest, showAlert, hideAlert, onlyDigits, initials, friendly } = ClaroOne;
  const alertBox = document.getElementById('phone-alert');
  const cpfInput = document.getElementById('phone-cpf');
  let customer = null;
  let session = null;
  let audioFile = null;
  let timerHandle = null;
  let startedAt = null;
  let ttlHandle = null;
  let failedStage = null;

  function step(name) {
    document.querySelectorAll('.phone-step').forEach(section => section.classList.toggle('active', section.dataset.step === name));
    hideAlert(alertBox);
  }

  function loading(button, state, label) {
    button.disabled = state;
    if (!button.dataset.label) button.dataset.label = button.textContent;
    button.textContent = state ? label : button.dataset.label;
  }

  document.getElementById('device-time').textContent = new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' }).format(new Date());

  document.getElementById('phone-cpf-submit').addEventListener('click', async () => {
    const button = document.getElementById('phone-cpf-submit');
    try {
      loading(button, true, 'Localizando...'); hideAlert(alertBox);
      customer = await api(`/api/customers/${encodeURIComponent(cpfInput.value)}`);
      localStorage.setItem('claroOneCpf', customer.cpf);
      document.getElementById('phone-customer-name').textContent = customer.name;
      step('ura');
    } catch (error) { showAlert(alertBox, error.message); }
    finally { loading(button, false); }
  });

  document.querySelector('[data-back="cpf"]').addEventListener('click', () => step('cpf'));
  document.querySelectorAll('.ura-grid button').forEach(button => button.addEventListener('click', async () => {
    try {
      button.disabled = true;
      session = await api('/api/sessions', jsonRequest('POST', { cpf: customer.cpf, initial_department: button.dataset.department }));
      localStorage.setItem('claroOneSession', session.id);
      document.getElementById('call-customer-name').textContent = customer.name;
      document.getElementById('call-department').textContent = button.querySelector('span').textContent;
      document.getElementById('phone-avatar').textContent = initials(customer.name);
      step('call'); startTimer();
    } catch (error) { showAlert(alertBox, error.message); button.disabled = false; }
  }));

  function startTimer() {
    startedAt = Date.now();
    timerHandle = setInterval(() => {
      const total = Math.floor((Date.now() - startedAt) / 1000);
      const minutes = String(Math.floor(total / 60)).padStart(2, '0');
      const seconds = String(total % 60).padStart(2, '0');
      document.getElementById('call-timer').textContent = `${minutes}:${seconds}`;
    }, 1000);
  }

  document.getElementById('audio-file').addEventListener('change', event => {
    audioFile = event.target.files[0] || null;
    const selected = document.getElementById('file-selected');
    selected.classList.toggle('hidden', !audioFile);
    if (audioFile) document.getElementById('file-name').textContent = audioFile.name;
  });

  const processRows = name => document.querySelector(`[data-process="${name}"]`);
  function processState(name, state, label) {
    const row = processRows(name);
    row.className = state;
    row.querySelector('em').textContent = label || ({ done: 'Concluído', processing: 'Processando', error: 'Erro' }[state] || 'Aguardando');
  }

  document.getElementById('end-call').addEventListener('click', beginProcessing);
  document.getElementById('retry-processing').addEventListener('click', () => runIAs(failedStage));

  async function beginProcessing() {
    if (!audioFile) { showAlert(alertBox, 'Adicione uma gravação para processar o atendimento.'); return; }
    const button = document.getElementById('end-call');
    loading(button, true, 'Enviando gravação...');
    try {
      const form = new FormData(); form.append('audio', audioFile);
      await api(`/api/sessions/${session.id}/audio`, { method: 'POST', body: form });
      clearInterval(timerHandle); step('processing'); processState('audio', 'done');
      await runIAs('transcription');
    } catch (error) { showAlert(alertBox, error.message); }
    finally { loading(button, false); }
  }

  async function runIAs(startAt = 'transcription') {
    const retry = document.getElementById('retry-processing');
    retry.classList.add('hidden'); hideAlert(alertBox);
    try {
      if (startAt === 'transcription') {
        processState('transcription', 'processing', 'Transcrevendo');
        await api(`/api/sessions/${session.id}/transcribe`, { method: 'POST' });
        processState('transcription', 'done'); processState('transcribed', 'done');
      }
      failedStage = 'context';
      processState('context', 'processing', 'Analisando');
      const result = await api(`/api/sessions/${session.id}/contextualize`, { method: 'POST' });
      session = result.session;
      processState('context', 'done'); processState('structured', 'done'); processState('updated', 'done');
      setTimeout(showResult, 450);
    } catch (error) {
      failedStage = processRows('transcription').classList.contains('processing') ? 'transcription' : 'context';
      processState(failedStage, 'error', 'Falhou');
      showAlert(alertBox, error.message);
      retry.textContent = failedStage === 'transcription' ? 'Tentar transcrição novamente' : 'Tentar contextualização novamente';
      retry.classList.remove('hidden');
    }
  }

  function showResult() {
    document.getElementById('result-protocol').textContent = session.protocol;
    document.getElementById('result-problem').textContent = session.problem || 'Não identificado';
    document.getElementById('result-summary').textContent = session.summary || 'Não identificado';
    document.getElementById('result-destination').textContent = friendly(session.destination_department);
    const suffix = `?cpf=${encodeURIComponent(session.cpf)}`;
    document.getElementById('go-whatsapp').href = `/whatsapp${suffix}`;
    document.getElementById('go-minha-claro').href = `/minha-claro${suffix}`;
    document.getElementById('view-cce').href = `/debug?session=${session.id}`;
    step('result'); startTtl();
  }

  function startTtl() {
    const render = () => {
      const seconds = Math.max(0, Math.floor((new Date(session.expires_at) - Date.now()) / 1000));
      const h = String(Math.floor(seconds / 3600)).padStart(2, '0');
      const m = String(Math.floor(seconds % 3600 / 60)).padStart(2, '0');
      const s = String(seconds % 60).padStart(2, '0');
      document.getElementById('result-ttl').textContent = `${h}:${m}:${s}`;
    };
    render(); ttlHandle = setInterval(render, 1000);
  }
})();
