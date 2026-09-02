from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class SessionCreate(BaseModel):
    cpf: str
    initial_department: str


class SessionResume(BaseModel):
    channel: Literal["WHATSAPP", "MINHA_CLARO"]


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
