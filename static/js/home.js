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
      const groqReady = health.groq === 'ok';
      setStatus(2, groqReady ? 'Disponível' : health.groq === 'not_configured' ? 'Chave ausente' : 'Indisponível', groqReady ? 'ok' : 'warning');
      setStatus(3, groqReady ? 'Disponível' : health.groq === 'model_missing' ? 'Modelo ausente' : health.groq === 'authentication_error' ? 'Chave inválida' : 'Indisponível', groqReady ? 'ok' : 'warning');
      if (!groqReady) {
        guidance.textContent = health.groq === 'not_configured'
          ? 'Configure GROQ_API_KEY no arquivo .env para habilitar o processamento.'
          : 'Groq indisponível. Verifique a chave, a internet e os modelos configurados.';
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
