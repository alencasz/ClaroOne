from __future__ import annotations

from datetime import timedelta

import pytest

from schemas import ContextCase
from services import cce_service
from utils import now_local


def contextualized_session():
    session = cce_service.create_session("123.456.789-00", "FATURAMENTO")
    cce_service.update_session(session["id"], transcript="Cobrança não reconhecida de 35 reais")
    return cce_service.store_context(
        session["id"],
        ContextCase(
            intent="CONTESTACAO_FATURA",
            category="FATURAMENTO",
            problem="Cobrança não reconhecida",
            summary="Cliente contesta cobrança.",
            entities={"valor": 35},
            destination_department="FINANCEIRO",
            suggested_action="ANALISAR_ESTORNO",
            priority="NORMAL",
        ),
    )


def test_create_cce_and_real_events():
    session = cce_service.create_session("12345678900", "FATURAMENTO")
    assert session["status"] == "EM_ATENDIMENTO"
    assert session["protocol"].startswith("CCE-")
    assert session["customer_name"] == "Lucas de Alencar"
    events = cce_service.get_timeline(session["id"])
    assert [event["event_type"] for event in events] == [
        "CUSTOMER_AUTHENTICATED", "DEPARTMENT_SELECTED", "SESSION_CREATED", "CALL_STARTED"
    ]


def test_find_active_contextualized_cce():
    expected = contextualized_session()
    found = cce_service.find_active_session("123.456.789-00")
    assert found is not None
    assert found["id"] == expected["id"]


def test_expired_session_is_not_resumable():
    session = contextualized_session()
    cce_service.update_session(session["id"], expires_at=(now_local() - timedelta(seconds=1)).isoformat())
    assert cce_service.find_active_session(session["cpf"]) is None
    with pytest.raises(cce_service.SessionUnavailableError):
        cce_service.resume_session(session["id"], "WHATSAPP")
    assert cce_service.get_session(session["id"])["status"] == "EXPIRADA"


def test_resume_renews_ttl():
    session = contextualized_session()
    old_expiration = session["expires_at"]
    resumed = cce_service.resume_session(session["id"], "WHATSAPP")
    assert resumed["status"] == "RETOMADA"
    assert resumed["current_channel"] == "WHATSAPP"
    assert resumed["expires_at"] >= old_expiration


def test_resolved_session_cannot_be_found_or_resumed():
    session = contextualized_session()
    resolved = cce_service.resolve_session(session["id"])
    assert resolved["status"] == "RESOLVIDA"
    assert cce_service.find_active_session(session["cpf"]) is None
    with pytest.raises(cce_service.SessionUnavailableError):
        cce_service.resume_session(session["id"], "MINHA_CLARO")
