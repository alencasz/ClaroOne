from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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
    category: str | None = None
    problem: str | None = None
    summary: str | None = None
    entities: dict[str, Any] = Field(default_factory=dict)
    destination_department: str | None = None
    suggested_action: str | None = None
    priority: Literal["BAIXA", "NORMAL", "ALTA", "URGENTE"] = "NORMAL"

    @field_validator("entities", mode="before")
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
