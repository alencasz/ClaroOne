from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator

from models import CATEGORY_DESTINATIONS, DestinationDepartment, ServiceCategory


class SessionCreate(BaseModel):
    cpf: str
    initial_department: str


class SessionResume(BaseModel):
    channel: Literal["TELEFONE", "WHATSAPP", "MINHA_CLARO"]


class MessageSessionCreate(BaseModel):
    cpf: str
    message: str = Field(min_length=3, max_length=2000)

    @field_validator("message")
    @classmethod
    def message_must_have_content(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Escreva uma mensagem com pelo menos 3 caracteres.")
        return value


class HumanRoute(BaseModel):
    channel: Literal["TELEFONE", "WHATSAPP", "COCKPIT"]


class ContextCase(BaseModel):
    intent: str | None = None
    category: ServiceCategory = ServiceCategory.OUTROS
    problem: str | None = None
    summary: str | None = None
    structured_context: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("structured_context", "entities"),
    )
    destination_department: DestinationDepartment = DestinationDepartment.OUTROS
    suggested_action: str | None = None
    priority: Literal["BAIXA", "NORMAL", "ALTA", "URGENTE"] = "NORMAL"

    @model_validator(mode="before")
    @classmethod
    def normalize_taxonomy(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        category = str(normalized.get("category") or "").strip().upper()
        destination = str(normalized.get("destination_department") or "").strip().upper()
        expected_destination = CATEGORY_DESTINATIONS.get(category)
        if expected_destination is None or destination != expected_destination:
            normalized["category"] = ServiceCategory.OUTROS.value
            normalized["destination_department"] = DestinationDepartment.OUTROS.value
        else:
            normalized["category"] = category
            normalized["destination_department"] = destination
        return normalized

    @field_validator("structured_context", mode="before")
    @classmethod
    def entities_must_be_object(cls, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_missing_priority(cls, value: Any) -> Any:
        if value is None or str(value).strip().lower() in {"", "null", "none"}:
            return "NORMAL"
        return str(value).strip().upper()

    @model_validator(mode="after")
    def case_must_contain_actionable_context(self) -> "ContextCase":
        required = (self.problem, self.summary, self.destination_department)
        if any(not value or str(value).strip().lower() == "null" for value in required):
            raise ValueError("O case precisa conter problema, resumo e setor de destino.")
        return self

    @property
    def entities(self) -> dict[str, Any]:
        """Compatibilidade com chamadas internas e testes criados antes do novo nome."""
        return self.structured_context
