from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from config import settings
from services import context_service
from services.context_service import ContextServiceError, parse_context_response


VALID = """{
  "intent": "SUPORTE_INTERNET",
  "category": "INTERNET",
  "problem": "Conexão indisponível",
  "summary": "Internet sem funcionar desde ontem.",
  "entities": {"luz_modem": "vermelha", "reinicializacoes": 2},
  "destination_department": "SUPORTE_TECNICO",
  "suggested_action": "DIAGNOSTICAR_CONEXAO",
  "priority": "NORMAL"
}"""


def test_parse_plain_json():
    case = parse_context_response(VALID)
    assert case.category == "INTERNET"
    assert case.entities["reinicializacoes"] == 2


def test_parse_json_inside_markdown_and_surrounding_text():
    case = parse_context_response(f"Resultado:\n```json\n{VALID}\n```\nFim")
    assert case.intent == "SUPORTE_INTERNET"


def test_parse_structured_output_entity_list():
    payload = json.loads(VALID)
    payload["entities"] = [
        {"name": "luz_modem", "value": "vermelha"},
        {"name": "reinicializacoes", "value": 2},
    ]
    case = parse_context_response(json.dumps(payload))
    assert case.entities == {"luz_modem": "vermelha", "reinicializacoes": 2}


def test_reject_invalid_priority():
    with pytest.raises(ValidationError):
        parse_context_response(VALID.replace('"NORMAL"', '"QUALQUER"'))


def test_normalize_null_priority_returned_by_model():
    case = parse_context_response(VALID.replace('"NORMAL"', '"null"'))
    assert case.priority == "NORMAL"


def test_reject_semantically_empty_json():
    with pytest.raises(ValidationError, match="problema, resumo e setor"):
        parse_context_response(
            '{"intent":null,"category":null,"problem":null,"summary":null,'
            '"entities":{},"destination_department":null,"suggested_action":null,"priority":"NORMAL"}'
        )


def test_missing_key_is_clear():
    original = settings.groq_api_key
    object.__setattr__(settings, "groq_api_key", "")
    try:
        with pytest.raises(ContextServiceError, match="GROQ_API_KEY"):
            context_service.analyze_context("Quero cancelar meu plano.", "CANCELAMENTO")
    finally:
        object.__setattr__(settings, "groq_api_key", original)


def test_contextualization_is_simulated_without_api_call(monkeypatch):
    captured = {}

    class Completions:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=VALID))]
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    monkeypatch.setattr(context_service, "_create_client", lambda: fake_client)
    case = context_service.analyze_context(
        "Minha internet está sem funcionar desde ontem.", "FATURAMENTO"
    )
    assert case.category == "INTERNET"
    assert case.destination_department == "SUPORTE_TECNICO"
    assert captured["model"] == settings.groq_context_model
    assert captured["response_format"]["type"] == "json_schema"
    assert captured["response_format"]["json_schema"]["strict"] is True


def test_structured_schema_is_strict_and_dynamic():
    schema = context_service.CONTEXT_JSON_SCHEMA
    assert schema["additionalProperties"] is False
    assert schema["properties"]["entities"]["type"] == "array"
    assert schema["properties"]["entities"]["items"]["additionalProperties"] is False


def test_health_without_key_does_not_call_external_api(monkeypatch):
    original = settings.groq_api_key
    object.__setattr__(settings, "groq_api_key", "")
    monkeypatch.setattr(
        context_service,
        "_create_client",
        lambda: pytest.fail("O health não deveria chamar a API sem chave"),
    )
    try:
        assert context_service.health_check() == ("not_configured", False)
    finally:
        object.__setattr__(settings, "groq_api_key", original)


@pytest.mark.parametrize(
    ("error_name", "status_code", "expected"),
    [
        ("AuthenticationError", 401, "chave da Groq é inválida"),
        ("APITimeoutError", None, "excedeu o tempo"),
        ("RateLimitError", 429, "limite de uso"),
    ],
)
def test_provider_errors_are_friendly(error_name, status_code, expected):
    error_type = type(error_name, (Exception,), {})
    error = error_type()
    if status_code is not None:
        error.status_code = status_code
    assert expected in str(context_service._friendly_api_error(error))
