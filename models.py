from __future__ import annotations

SESSION_STATUSES = {
    "EM_ATENDIMENTO",
    "PROCESSANDO",
    "SUSPENSA",
    "RETOMADA",
    "EM_ATENDIMENTO_HUMANO",
    "RESOLVIDA",
    "EXPIRADA",
}

RESUMABLE_STATUSES = {"SUSPENSA", "RETOMADA", "EM_ATENDIMENTO_HUMANO"}
CHANNELS = {"TELEFONE", "WHATSAPP", "MINHA_CLARO", "COCKPIT", "URA", "SISTEMA"}

DEPARTMENTS = {
    "INTERNET": "Internet",
    "TELEFONIA": "Telefonia",
    "FATURAMENTO": "Fatura e pagamentos",
    "CANCELAMENTO": "Cancelamento",
    "OUTROS": "Outros",
}
