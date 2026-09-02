from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.context_service import parse_context_response


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
