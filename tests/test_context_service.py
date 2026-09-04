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
  "structured_context": {"luz_modem": "vermelha", "reinicializacoes": 2},
  "destination_department": "SUPORTE_TECNICO",
  "suggested_action": "DIAGNOSTICAR_CONEXAO",
  "priority": "NORMAL"
}"""


def test_parse_plain_json():
    case = parse_context_response(VALID)
    assert case.category == "INTERNET"
    assert case.entities["reinicializacoes"] == 2
    assert "structured_context" in case.model_dump()
    assert "entities" not in case.model_dump()


def test_parse_json_inside_markdown_and_surrounding_text():
    case = parse_context_response(f"Resultado:\n```json\n{VALID}\n```\nFim")
    assert case.intent == "SUPORTE_INTERNET"


def test_parse_structured_output_entity_list():
    payload = json.loads(VALID)
    payload["structured_context"] = [
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
            '"structured_context":{},"destination_department":null,"suggested_action":null,"priority":"NORMAL"}'
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


def test_provider_rejected_json_uses_single_correction_attempt(monkeypatch):
    calls = 0

    class RejectedJson(Exception):
        status_code = 400
        body = {
            "code": "json_validate_failed",
            "failed_generation": VALID[:-1] + ",}",
        }

    class Completions:
        @staticmethod
        def create(**_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RejectedJson()
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=VALID))]
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    monkeypatch.setattr(context_service, "_create_client", lambda: fake_client)
    case = context_service.analyze_context("Minha internet não funciona.", "INTERNET")
    assert calls == 2
    assert case.category == "INTERNET"


def test_structured_schema_is_strict_and_dynamic():
    schema = context_service.CONTEXT_JSON_SCHEMA
    assert schema["additionalProperties"] is False
    assert schema["properties"]["structured_context"]["type"] == "array"
    assert schema["properties"]["structured_context"]["items"]["additionalProperties"] is False
    assert schema["properties"]["category"]["enum"] == [
        "FATURAMENTO", "INTERNET", "TELEFONIA", "CANCELAMENTO", "OUTROS"
    ]
    assert schema["properties"]["destination_department"]["enum"] == [
        "FINANCEIRO", "SUPORTE_TECNICO", "SUPORTE_TELEFONIA",
        "RETENCAO_CANCELAMENTO", "OUTROS"
    ]


@pytest.mark.parametrize(
    ("category", "destination"),
    [
        ("FATURAMENTO", "FINANCEIRO"),
        ("INTERNET", "SUPORTE_TECNICO"),
        ("TELEFONIA", "SUPORTE_TELEFONIA"),
        ("CANCELAMENTO", "RETENCAO_CANCELAMENTO"),
        ("OUTROS", "OUTROS"),
    ],
)
def test_allowed_ai_classifications_are_preserved(category, destination):
    payload = json.loads(VALID)
    payload.update(category=category, destination_department=destination)
    case = parse_context_response(json.dumps(payload))
    assert case.category == category
    assert case.destination_department == destination


@pytest.mark.parametrize(
    ("transcript", "category", "destination"),
    [
        ("Existe uma cobrança que não reconheço na minha fatura.", "FATURAMENTO", "FINANCEIRO"),
        ("Minha internet está sem funcionar e o modem está com a luz vermelha.", "INTERNET", "SUPORTE_TECNICO"),
        ("Não consigo realizar ligações e minha linha está sem sinal.", "TELEFONIA", "SUPORTE_TELEFONIA"),
        ("Quero cancelar definitivamente meu plano.", "CANCELAMENTO", "RETENCAO_CANCELAMENTO"),
        ("Quero atualizar meus dados cadastrais.", "OUTROS", "OUTROS"),
    ],
)
def test_contextualization_pipeline_for_five_categories_uses_mocked_ai(
    monkeypatch, transcript, category, destination
):
    payload = json.loads(VALID)
    payload.update(
        category=category,
        destination_department=destination,
        problem="Solicitação identificada",
        summary=transcript,
    )
    monkeypatch.setattr(context_service, "_generate", lambda _messages: json.dumps(payload))
    case = context_service.analyze_context(transcript, "OUTROS")
    assert case.category == category
    assert case.destination_department == destination


@pytest.mark.parametrize(
    ("category", "destination"),
    [
        ("DESCONHECIDA", "FINANCEIRO"),
        ("FATURAMENTO", "DEPARTAMENTO_INEXISTENTE"),
        ("INTERNET", "FINANCEIRO"),
        (None, None),
    ],
)
def test_unknown_or_incoherent_taxonomy_is_safely_normalized(category, destination):
    payload = json.loads(VALID)
    payload.update(category=category, destination_department=destination)
    payload["summary"] = "Resumo que deve ser preservado."
    payload["structured_context"] = {"informacao": "preservada"}
    case = parse_context_response(json.dumps(payload))
    assert case.category == "OUTROS"
    assert case.destination_department == "OUTROS"
    assert case.summary == "Resumo que deve ser preservado."
    assert case.structured_context == {"informacao": "preservada"}


def test_legacy_entities_name_remains_readable():
    payload = json.loads(VALID)
    payload["entities"] = payload.pop("structured_context")
    case = parse_context_response(json.dumps(payload))
    assert case.structured_context["luz_modem"] == "vermelha"


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
