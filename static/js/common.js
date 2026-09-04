(() => {
  const onlyDigits = value => String(value || '').replace(/\D/g, '').slice(0, 11);
  const formatCpf = value => {
    const digits = onlyDigits(value);
    return digits
      .replace(/^(\d{3})(\d)/, '$1.$2')
      .replace(/^(\d{3})\.(\d{3})(\d)/, '$1.$2.$3')
      .replace(/\.(\d{3})(\d)/, '.$1-$2');
  };

  document.querySelectorAll('.cpf-input').forEach(input => {
    input.addEventListener('input', () => { input.value = formatCpf(input.value); });
  });

  async function api(url, options = {}) {
    const response = await fetch(url, options);
    const contentType = response.headers.get('content-type') || '';
    const data = contentType.includes('application/json') ? await response.json() : null;
    if (!response.ok) {
      const error = new Error(data?.detail || 'Não foi possível concluir a operação.');
      error.status = response.status;
      throw error;
    }
    return data;
  }

  function jsonRequest(method, body) {
    return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
  }

  function showAlert(element, message, success = false) {
    element.textContent = message;
    element.classList.toggle('success', success);
    element.classList.remove('hidden');
  }

  function hideAlert(element) { element.classList.add('hidden'); }

  function toast(message, isError = false) {
    const region = document.getElementById('toast-region');
    const item = document.createElement('div');
    item.className = `toast${isError ? ' error' : ''}`;
    item.textContent = message;
    region.appendChild(item);
    setTimeout(() => item.remove(), 3500);
  }

  function friendly(value) {
    if (!value) return 'Não identificado';
    return String(value).replaceAll('_', ' ').toLowerCase().replace(/(^|\s)\S/g, c => c.toUpperCase());
  }

  const categoryLabels = Object.freeze({
    FATURAMENTO: 'Faturamento',
    INTERNET: 'Internet',
    TELEFONIA: 'Telefonia',
    CANCELAMENTO: 'Cancelamento',
    OUTROS: 'Atendimento geral'
  });
  const departmentLabels = Object.freeze({
    FINANCEIRO: 'Financeiro',
    SUPORTE_TECNICO: 'Suporte técnico',
    SUPORTE_TELEFONIA: 'Suporte de telefonia',
    RETENCAO_CANCELAMENTO: 'Retenção e cancelamento',
    OUTROS: 'Atendimento geral'
  });
  const categoryAreas = Object.freeze({
    FATURAMENTO: 'billing',
    INTERNET: 'internet',
    TELEFONIA: 'phone',
    CANCELAMENTO: 'cancel',
    OUTROS: 'generic'
  });

  function categoryLabel(value) { return categoryLabels[value] || friendly(value); }
  function departmentLabel(value) { return departmentLabels[value] || friendly(value); }
  function categoryArea(value) { return categoryAreas[value] || 'generic'; }

  function brDate(value) {
    if (!value) return '—';
    return new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short', timeZone: 'America/Sao_Paulo' }).format(new Date(value));
  }

  function brTime(value) {
    if (!value) return '—';
    return new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit', timeZone: 'America/Sao_Paulo' }).format(new Date(value));
  }

  function currency(value) {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number(value));
  }

  function formatEntity(key, value) {
    if (typeof value === 'boolean') return value ? 'Sim' : 'Não';
    if (/valor|preco|preço|cobranca|cobrança/i.test(key) && !Number.isNaN(Number(value))) return currency(value);
    if (Array.isArray(value)) return value.join(', ');
    if (typeof value === 'object' && value !== null) return JSON.stringify(value);
    return String(value);
  }

  function initials(name) { return String(name || '').split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase(); }

  function queryCpf() { return new URLSearchParams(location.search).get('cpf') || localStorage.getItem('claroOneCpf') || ''; }

  window.ClaroOne = { api, jsonRequest, showAlert, hideAlert, toast, friendly, categoryLabel, departmentLabel, categoryArea, brDate, brTime, currency, formatEntity, formatCpf, onlyDigits, initials, queryCpf };
})();
