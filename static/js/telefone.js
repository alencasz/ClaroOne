(() => {
  const { api, jsonRequest, showAlert, hideAlert, initials, friendly } = ClaroOne;
  const alertBox = document.getElementById('phone-alert');
  const cpfInput = document.getElementById('phone-cpf');
  const callState = document.getElementById('call-state');
  const callStateText = document.getElementById('call-state-text');
  const microphoneStatus = document.getElementById('microphone-status');
  const startCallButton = document.getElementById('start-call');
  const endCallButton = document.getElementById('end-call');
  const cancelCallButton = document.getElementById('cancel-call');
  const processFileButton = document.getElementById('process-file');
  const audioInput = document.getElementById('audio-file');
  const uploadBox = document.querySelector('.upload-box');
  let customer = null;
  let session = null;
  let audioFile = null;
  let recordedDurationMs = null;
  let mediaRecorder = null;
  let mediaStream = null;
  let recordedChunks = [];
  let timerHandle = null;
  let startedAt = null;
  let ttlHandle = null;
  let failedStage = null;
  let processingLocked = false;
  let callRegistered = false;

  function step(name) {
    document.querySelectorAll('.phone-step').forEach(section => section.classList.toggle('active', section.dataset.step === name));
    hideAlert(alertBox);
  }

  function loading(button, state, label) {
    button.disabled = state;
    if (!button.dataset.label) button.dataset.label = button.textContent;
    button.textContent = state ? label : button.dataset.label;
  }

  function setCallState(state, text) {
    callState.className = `call-state ${state}`;
    callStateText.textContent = text;
  }

  function stopTimer() {
    clearInterval(timerHandle);
    timerHandle = null;
  }

  function startTimer() {
    stopTimer();
    startedAt = Date.now();
    const render = () => {
      const total = Math.floor((Date.now() - startedAt) / 1000);
      const minutes = String(Math.floor(total / 60)).padStart(2, '0');
      const seconds = String(total % 60).padStart(2, '0');
      document.getElementById('call-timer').textContent = `${minutes}:${seconds}`;
    };
    render();
    timerHandle = setInterval(render, 250);
  }

  function stopMicrophoneTracks() {
    if (mediaStream) mediaStream.getTracks().forEach(track => track.stop());
    mediaStream = null;
  }

  function resetCallUi() {
    stopTimer();
    stopMicrophoneTracks();
    mediaRecorder = null;
    recordedChunks = [];
    audioFile = null;
    recordedDurationMs = null;
    processingLocked = false;
    callRegistered = false;
    audioInput.value = '';
    document.getElementById('call-timer').textContent = '00:00';
    document.getElementById('file-selected').classList.add('hidden');
    startCallButton.classList.remove('hidden');
    endCallButton.classList.add('hidden');
    cancelCallButton.classList.add('hidden');
    processFileButton.classList.add('hidden');
    uploadBox.classList.remove('disabled');
    audioInput.disabled = false;
    microphoneStatus.classList.remove('active');
    microphoneStatus.querySelector('span').textContent = 'Microfone ainda não iniciado';
    setCallState('preparing', 'PREPARANDO LIGAÇÃO');
    document.querySelectorAll('.processing-list li').forEach(row => {
      row.className = '';
      row.querySelector('em').textContent = 'Aguardando';
    });
  }

  document.getElementById('device-time').textContent = new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' }).format(new Date());

  document.getElementById('phone-cpf-submit').addEventListener('click', async () => {
    const button = document.getElementById('phone-cpf-submit');
    try {
      loading(button, true, 'Localizando...'); hideAlert(alertBox);
      customer = await api(`/api/customers/${encodeURIComponent(cpfInput.value)}`);
      localStorage.setItem('claroOneCpf', customer.cpf);
      document.getElementById('phone-customer-name').textContent = customer.name;
      try {
        session = await api(`/api/sessions/active/${encodeURIComponent(customer.cpf)}`);
        document.getElementById('phone-existing-protocol').textContent = session.protocol;
        document.getElementById('phone-existing-problem').textContent = session.problem || session.summary || 'Atendimento em andamento';
        document.getElementById('phone-existing-origin').textContent = friendly(session.channel_origin);
        document.getElementById('phone-existing-destination').textContent = friendly(session.destination_department || session.initial_department);
        step('existing');
      } catch (activeError) {
        if (activeError.status === 404) { session = null; step('ura'); }
        else throw activeError;
      }
    } catch (error) { showAlert(alertBox, error.message); }
    finally { loading(button, false); }
  });

  document.querySelectorAll('[data-back="cpf"]').forEach(button => button.addEventListener('click', () => step('cpf')));
  document.getElementById('phone-continue-session').addEventListener('click', async () => {
    const button = document.getElementById('phone-continue-session');
    try {
      loading(button, true, 'Recuperando contexto...');
      session = await api(`/api/sessions/${session.id}/resume`, jsonRequest('POST', { channel: 'TELEFONE' }));
      session = await api(`/api/sessions/${session.id}/route-human`, jsonRequest('POST', { channel: 'TELEFONE' }));
      document.getElementById('phone-routed-problem').textContent = session.problem || session.summary || 'Atendimento em andamento';
      document.getElementById('phone-routed-destination').textContent = friendly(session.destination_department || session.initial_department);
      document.getElementById('phone-routed-cockpit').href = `/atendente?session=${session.id}`;
      step('routed');
    } catch (error) { showAlert(alertBox, error.message); }
    finally { loading(button, false); }
  });

  document.getElementById('phone-new-session').addEventListener('click', async () => {
    if (!confirm('O contexto atual será removido. Deseja começar um novo atendimento?')) return;
    const button = document.getElementById('phone-new-session');
    try {
      loading(button, true, 'Removendo contexto...');
      await api(`/api/sessions/${session.id}`, { method: 'DELETE' });
      session = null;
      localStorage.removeItem('claroOneSession');
      step('ura');
    } catch (error) { showAlert(alertBox, error.message); }
    finally { loading(button, false); }
  });

  document.querySelectorAll('.ura-grid button').forEach(button => button.addEventListener('click', async () => {
    const uraButtons = document.querySelectorAll('.ura-grid button');
    uraButtons.forEach(item => { item.disabled = true; });
    try {
      session = await api('/api/sessions', jsonRequest('POST', { cpf: customer.cpf, initial_department: button.dataset.department }));
      localStorage.setItem('claroOneSession', session.id);
      document.getElementById('call-customer-name').textContent = customer.name;
      document.getElementById('call-department').textContent = button.querySelector('span').textContent;
      document.getElementById('phone-avatar').textContent = initials(customer.name);
      resetCallUi();
      step('call');
    } catch (error) {
      showAlert(alertBox, error.message);
      uraButtons.forEach(item => { item.disabled = false; });
    }
  }));

  function chooseRecorderType() {
    const candidates = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/ogg',
      'audio/mp4'
    ];
    if (typeof MediaRecorder.isTypeSupported !== 'function') return '';
    return candidates.find(type => MediaRecorder.isTypeSupported(type)) || '';
  }

  function recorderExtension(mimeType) {
    if (mimeType.includes('ogg')) return '.ogg';
    if (mimeType.includes('mp4')) return '.m4a';
    return '.webm';
  }

  function microphoneErrorMessage(error) {
    if (['NotAllowedError', 'SecurityError'].includes(error.name)) {
      return 'A permissão do microfone foi negada. Permita o acesso no navegador ou use o upload manual.';
    }
    if (['NotFoundError', 'DevicesNotFoundError'].includes(error.name)) {
      return 'Nenhum microfone foi encontrado. Conecte um microfone ou use o upload manual.';
    }
    if (['NotReadableError', 'TrackStartError'].includes(error.name)) {
      return 'O microfone está ocupado ou indisponível. Feche outros aplicativos e tente novamente.';
    }
    return 'Não foi possível iniciar o microfone. Use o upload manual ou tente outro navegador.';
  }

  async function registerCallStart() {
    if (callRegistered) return;
    await api(`/api/sessions/${session.id}/call/start`, { method: 'POST' });
    callRegistered = true;
  }

  startCallButton.addEventListener('click', async () => {
    if (processingLocked || (mediaRecorder && mediaRecorder.state !== 'inactive')) {
      showAlert(alertBox, 'A ligação já está em andamento.');
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      showAlert(alertBox, 'Este navegador não suporta gravação pelo microfone. Use o upload manual.');
      return;
    }
    try {
      loading(startCallButton, true, 'Solicitando microfone...');
      hideAlert(alertBox);
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = chooseRecorderType();
      mediaRecorder = mimeType ? new MediaRecorder(mediaStream, { mimeType }) : new MediaRecorder(mediaStream);
      recordedChunks = [];
      mediaRecorder.addEventListener('dataavailable', event => {
        if (event.data?.size) recordedChunks.push(event.data);
      });
      mediaRecorder.addEventListener('error', event => {
        stopTimer();
        stopMicrophoneTracks();
        processingLocked = false;
        setCallState('preparing', 'GRAVAÇÃO INTERROMPIDA');
        microphoneStatus.classList.remove('active');
        microphoneStatus.querySelector('span').textContent = 'Microfone interrompido';
        startCallButton.classList.remove('hidden');
        endCallButton.classList.add('hidden');
        cancelCallButton.classList.add('hidden');
        showAlert(alertBox, microphoneErrorMessage(event.error || new Error()));
      });
      await registerCallStart();
      audioFile = null;
      audioInput.value = '';
      document.getElementById('file-selected').classList.add('hidden');
      processFileButton.classList.add('hidden');
      uploadBox.classList.add('disabled');
      audioInput.disabled = true;
      mediaRecorder.start(250);
      startTimer();
      setCallState('recording', 'LIGAÇÃO EM ANDAMENTO');
      microphoneStatus.classList.add('active');
      microphoneStatus.querySelector('span').textContent = 'Microfone ativo · gravando';
      startCallButton.classList.add('hidden');
      endCallButton.classList.remove('hidden');
      cancelCallButton.classList.remove('hidden');
    } catch (error) {
      stopMicrophoneTracks();
      mediaRecorder = null;
      showAlert(alertBox, error.status ? error.message : microphoneErrorMessage(error));
    } finally {
      loading(startCallButton, false);
    }
  });

  function stopRecording() {
    return new Promise((resolve, reject) => {
      const recorder = mediaRecorder;
      if (!recorder || recorder.state === 'inactive') {
        reject(new Error('A gravação não foi iniciada.'));
        return;
      }
      recorder.addEventListener('stop', () => {
        const mimeType = recorder.mimeType || recordedChunks[0]?.type || 'audio/webm';
        const blob = new Blob(recordedChunks, { type: mimeType });
        mediaRecorder = null;
        recordedChunks = [];
        resolve({ blob, mimeType });
      }, { once: true });
      try { recorder.stop(); }
      catch (error) { reject(error); }
    });
  }

  audioInput.addEventListener('change', event => {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      event.target.value = '';
      showAlert(alertBox, 'Encerre ou cancele a gravação do microfone antes de escolher um arquivo.');
      return;
    }
    audioFile = event.target.files[0] || null;
    recordedDurationMs = null;
    const selected = document.getElementById('file-selected');
    selected.classList.toggle('hidden', !audioFile);
    processFileButton.classList.toggle('hidden', !audioFile);
    if (audioFile) {
      document.getElementById('file-name').textContent = audioFile.name;
      setCallState('preparing', 'GRAVAÇÃO PRONTA');
    }
  });

  const processRows = name => document.querySelector(`[data-process="${name}"]`);
  function processState(name, state, label) {
    const row = processRows(name);
    row.className = state;
    row.querySelector('em').textContent = label || ({ done: 'Concluído', processing: 'Processando', error: 'Erro' }[state] || 'Aguardando');
  }

  endCallButton.addEventListener('click', beginProcessing);
  processFileButton.addEventListener('click', beginProcessing);
  document.getElementById('retry-processing').addEventListener('click', () => {
    if (failedStage === 'upload') beginProcessing();
    else runIAs(failedStage);
  });
  document.getElementById('choose-another-audio').addEventListener('click', () => {
    audioFile = null;
    recordedDurationMs = null;
    processingLocked = false;
    audioInput.value = '';
    document.getElementById('file-selected').classList.add('hidden');
    document.getElementById('retry-processing').classList.add('hidden');
    document.getElementById('choose-another-audio').classList.add('hidden');
    startCallButton.classList.remove('hidden');
    endCallButton.classList.add('hidden');
    cancelCallButton.classList.add('hidden');
    processFileButton.classList.add('hidden');
    uploadBox.classList.remove('disabled');
    audioInput.disabled = false;
    microphoneStatus.classList.remove('active');
    microphoneStatus.querySelector('span').textContent = 'Microfone ainda não iniciado';
    setCallState('preparing', 'PREPARANDO LIGAÇÃO');
    document.querySelectorAll('.processing-list li').forEach(row => {
      row.className = '';
      row.querySelector('em').textContent = 'Aguardando';
    });
    step('call');
  });

  async function prepareRecordedAudio() {
    if (!mediaRecorder || mediaRecorder.state === 'inactive') return;
    const duration = Date.now() - startedAt;
    setCallState('preparing', 'FINALIZANDO GRAVAÇÃO');
    const recording = await stopRecording();
    stopTimer();
    stopMicrophoneTracks();
    if (duration < 1000) throw new Error('A gravação é curta demais. Fale por pelo menos 1 segundo.');
    if (recording.blob.size < 256) throw new Error('A gravação está vazia. Verifique o microfone e tente novamente.');
    recordedDurationMs = Math.round(duration);
    audioFile = recording.blob;
    audioFile.uploadName = `gravacao${recorderExtension(recording.mimeType)}`;
  }

  async function beginProcessing() {
    if (processingLocked) return;
    processingLocked = true;
    const actionButton = mediaRecorder?.state === 'recording' ? endCallButton : processFileButton;
    loading(actionButton, true, 'Finalizando...');
    try {
      if (mediaRecorder?.state === 'recording') await prepareRecordedAudio();
      if (!audioFile) throw new Error('Inicie a ligação ou adicione uma gravação para processar o atendimento.');
      await registerCallStart();
      step('processing');
      document.getElementById('choose-another-audio').classList.add('hidden');
      failedStage = 'upload';
      processState('audio', 'processing', 'Enviando');
      const form = new FormData();
      form.append('audio', audioFile, audioFile.uploadName || audioFile.name);
      if (recordedDurationMs !== null) form.append('duration_ms', String(recordedDurationMs));
      await api(`/api/sessions/${session.id}/audio`, { method: 'POST', body: form });
      processState('audio', 'done', 'Recebido');
      failedStage = 'transcription';
      await runIAs('transcription');
    } catch (error) {
      stopTimer();
      stopMicrophoneTracks();
      if (document.querySelector('[data-step="processing"]').classList.contains('active')) {
        processState('audio', 'error', 'Falhou');
        const retry = document.getElementById('retry-processing');
        retry.textContent = 'Tentar envio novamente';
        retry.classList.remove('hidden');
        document.getElementById('choose-another-audio').classList.remove('hidden');
      } else {
        setCallState('preparing', 'PREPARANDO LIGAÇÃO');
        startCallButton.classList.remove('hidden');
        endCallButton.classList.add('hidden');
        cancelCallButton.classList.add('hidden');
        uploadBox.classList.remove('disabled');
        audioInput.disabled = false;
        microphoneStatus.classList.remove('active');
        microphoneStatus.querySelector('span').textContent = 'Microfone ainda não iniciado';
      }
      showAlert(alertBox, error.message || 'Não foi possível enviar a gravação. Verifique sua internet.');
      processingLocked = false;
    } finally {
      loading(actionButton, false);
    }
  }

  async function runIAs(startAt = 'transcription') {
    const retry = document.getElementById('retry-processing');
    retry.classList.add('hidden'); hideAlert(alertBox);
    processingLocked = true;
    try {
      if (startAt === 'transcription') {
        processState('transcription', 'processing', 'Transcrevendo');
        await api(`/api/sessions/${session.id}/transcribe`, { method: 'POST' });
        processState('transcription', 'done');
        processState('transcribed', 'done');
      }
      failedStage = 'context';
      processState('context', 'processing', 'Analisando');
      const result = await api(`/api/sessions/${session.id}/contextualize`, { method: 'POST' });
      session = result.session;
      processState('context', 'done');
      processState('structured', 'done');
      processState('updated', 'done');
      showResult();
    } catch (error) {
      failedStage = processRows('transcription').classList.contains('processing') ? 'transcription' : 'context';
      processState(failedStage, 'error', 'Falhou');
      showAlert(alertBox, error.message);
      retry.textContent = failedStage === 'transcription' ? 'Tentar transcrição novamente' : 'Tentar contextualização novamente';
      retry.classList.remove('hidden');
      processingLocked = false;
    }
  }

  async function cancelCall() {
    if (processingLocked) return;
    if (!confirm('Cancelar esta ligação e remover a CCE iniciada?')) return;
    processingLocked = true;
    try {
      if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
      stopTimer();
      stopMicrophoneTracks();
      await api(`/api/sessions/${session.id}`, { method: 'DELETE' });
      localStorage.removeItem('claroOneSession');
      session = null;
      document.querySelectorAll('.ura-grid button').forEach(item => { item.disabled = false; });
      step('ura');
    } catch (error) {
      showAlert(alertBox, error.message);
    } finally {
      processingLocked = false;
    }
  }

  cancelCallButton.addEventListener('click', cancelCall);

  function showResult() {
    processingLocked = false;
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
    clearInterval(ttlHandle);
    const render = () => {
      const seconds = Math.max(0, Math.floor((new Date(session.expires_at) - Date.now()) / 1000));
      const h = String(Math.floor(seconds / 3600)).padStart(2, '0');
      const m = String(Math.floor(seconds % 3600 / 60)).padStart(2, '0');
      const s = String(seconds % 60).padStart(2, '0');
      document.getElementById('result-ttl').textContent = `${h}:${m}:${s}`;
    };
    render(); ttlHandle = setInterval(render, 1000);
  }

  window.addEventListener('pagehide', stopMicrophoneTracks);
})();
