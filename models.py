from __future__ import annotations

from enum import StrEnum

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


class ServiceCategory(StrEnum):
    FATURAMENTO = "FATURAMENTO"
    INTERNET = "INTERNET"
    TELEFONIA = "TELEFONIA"
    CANCELAMENTO = "CANCELAMENTO"
    OUTROS = "OUTROS"


class DestinationDepartment(StrEnum):
    FINANCEIRO = "FINANCEIRO"
    SUPORTE_TECNICO = "SUPORTE_TECNICO"
    SUPORTE_TELEFONIA = "SUPORTE_TELEFONIA"
    RETENCAO_CANCELAMENTO = "RETENCAO_CANCELAMENTO"
    OUTROS = "OUTROS"


CATEGORY_DESTINATIONS = {
    ServiceCategory.FATURAMENTO.value: DestinationDepartment.FINANCEIRO.value,
    ServiceCategory.INTERNET.value: DestinationDepartment.SUPORTE_TECNICO.value,
    ServiceCategory.TELEFONIA.value: DestinationDepartment.SUPORTE_TELEFONIA.value,
    ServiceCategory.CANCELAMENTO.value: DestinationDepartment.RETENCAO_CANCELAMENTO.value,
    ServiceCategory.OUTROS.value: DestinationDepartment.OUTROS.value,
}

CATEGORY_LABELS = {
    ServiceCategory.FATURAMENTO.value: "Faturamento",
    ServiceCategory.INTERNET.value: "Internet",
    ServiceCategory.TELEFONIA.value: "Telefonia",
    ServiceCategory.CANCELAMENTO.value: "Cancelamento",
    ServiceCategory.OUTROS.value: "Atendimento geral",
}

DESTINATION_LABELS = {
    DestinationDepartment.FINANCEIRO.value: "Financeiro",
    DestinationDepartment.SUPORTE_TECNICO.value: "Suporte técnico",
    DestinationDepartment.SUPORTE_TELEFONIA.value: "Suporte de telefonia",
    DestinationDepartment.RETENCAO_CANCELAMENTO.value: "Retenção e cancelamento",
    DestinationDepartment.OUTROS.value: "Atendimento geral",
}
