(() => {
  const { api, toast } = ClaroOne;
  const healthList = document.getElementById('health-list');
  const guidance = document.getElementById('health-guidance');

  function setStatus(index, text, kind) {
    const badge = healthList.children[index].querySelector('b');
    badge.textContent = text;
    badge.className = `status-dot ${kind}`;
  }

  async function loadHealth() {
    try {
      const health = await api('/api/health');
      setStatus(0, health.backend === 'ok' ? 'Operacional' : 'Erro', health.backend === 'ok' ? 'ok' : 'error');
      setStatus(1, health.database === 'ok' ? 'Conectado' : 'Erro', health.database === 'ok' ? 'ok' : 'error');
      const whisperReady = ['configured', 'loaded'].includes(health.whisper);
      setStatus(2, whisperReady ? `${health.whisper_model} configurado` : 'Dependência ausente', whisperReady ? 'ok' : 'error');
      setStatus(3, health.ollama === 'ok' ? `${health.ollama_model} disponível` : health.ollama === 'model_missing' ? 'Modelo ausente' : 'Indisponível', health.ollama === 'ok' ? 'ok' : 'warning');
      if (health.ollama !== 'ok') {
        guidance.textContent = 'IA de contextualização indisponível. Inicie o Ollama para habilitar o processamento.';
        guidance.classList.remove('hidden');
      } else guidance.classList.add('hidden');
    } catch (error) {
      [0, 1, 2, 3].forEach(i => setStatus(i, 'Indisponível', 'error'));
    }
  }

  document.getElementById('refresh-health').addEventListener('click', loadHealth);
  document.getElementById('home-reset').addEventListener('click', async () => {
    if (!confirm('Reiniciar a demonstração? Todas as CCEs e eventos serão removidos.')) return;
    try {
      await api('/api/demo/reset', { method: 'POST' });
      localStorage.removeItem('claroOneCpf');
      localStorage.removeItem('claroOneSession');
      toast('Demonstração reiniciada.');
    } catch (error) { toast(error.message, true); }
  });
  loadHealth();
})();
