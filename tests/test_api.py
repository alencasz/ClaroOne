from __future__ import annotations

from fastapi.testclient import TestClient

from app import app
from schemas import ContextCase
from services.context_service import ContextServiceError


def test_pages_open_and_session_api_normalizes_cpf():
    with TestClient(app) as client:
        for path in ("/", "/telefone", "/whatsapp", "/minha-claro", "/atendente", "/debug"):
            response = client.get(path)
            assert response.status_code == 200
            assert "Protótipo acadêmico" in response.text

        response = client.post(
            "/api/sessions",
            json={"cpf": "123.456.789-00", "initial_department": "FATURAMENTO"},
        )
        assert response.status_code == 201
        session = response.json()
        assert session["cpf"] == "12345678900"
        assert "audio_path" not in session
        assert session["audio_available"] is False

        timeline = client.get(f"/api/sessions/{session['id']}/events").json()
        assert len(timeline) == 4


def test_invalid_upload_format_is_friendly():
    with TestClient(app) as client:
        session = client.post(
            "/api/sessions",
            json={"cpf": "12345678900", "initial_department": "INTERNET"},
        ).json()
        response = client.post(
            f"/api/sessions/{session['id']}/audio",
            files={"audio": ("anotacoes.txt", b"nao e audio", "text/plain")},
        )
        assert response.status_code == 400
        assert "WAV, MP3 ou M4A" in response.json()["detail"]


def test_fake_wav_is_rejected_before_whisper_loading():
    with TestClient(app) as client:
        session = client.post(
            "/api/sessions",
            json={"cpf": "12345678900", "initial_department": "INTERNET"},
        ).json()
        response = client.post(
            f"/api/sessions/{session['id']}/audio",
            files={"audio": ("gravacao.wav", b"isto nao e um wav", "audio/wav")},
        )
        assert response.status_code == 422
        assert "áudio" in response.json()["detail"]


def test_whatsapp_can_create_context_then_continue_by_phone(monkeypatch):
    def fake_analysis(message: str, department: str) -> ContextCase:
        assert "internet" in message.lower()
        assert department == "ATENDIMENTO DIGITAL / WHATSAPP"
        return ContextCase(
            intent="SUPORTE_INTERNET",
            category="INTERNET",
            problem="Internet sem funcionar",
            summary="Cliente informa indisponibilidade da internet.",
            entities={"desde": "ontem"},
            destination_department="SUPORTE_TECNICO",
            suggested_action="DIAGNOSTICAR_CONEXAO",
            priority="NORMAL",
        )

    monkeypatch.setattr("routes.api.context_service.analyze_context", fake_analysis)
    with TestClient(app) as client:
        response = client.post(
            "/api/sessions/message",
            json={
                "cpf": "123.456.789-00",
                "message": "Minha internet está sem funcionar desde ontem.",
            },
        )
        assert response.status_code == 201
        session = response.json()["session"]
        assert session["channel_origin"] == "WHATSAPP"
        assert session["current_channel"] == "WHATSAPP"
        assert session["status"] == "EM_ATENDIMENTO_HUMANO"
        assert session["transcript"] == "Minha internet está sem funcionar desde ontem."
        assert session["audio_available"] is False

        found = client.get("/api/sessions/active/12345678900")
        assert found.status_code == 200
        assert found.json()["id"] == session["id"]

        resumed = client.post(
            f"/api/sessions/{session['id']}/resume",
            json={"channel": "TELEFONE"},
        )
        assert resumed.status_code == 200
        assert resumed.json()["current_channel"] == "TELEFONE"
        routed = client.post(
            f"/api/sessions/{session['id']}/route-human",
            json={"channel": "TELEFONE"},
        )
        assert routed.status_code == 200
        assert routed.json()["status"] == "EM_ATENDIMENTO_HUMANO"

        event_types = [
            event["event_type"]
            for event in client.get(f"/api/sessions/{session['id']}/events").json()
        ]
        assert "MESSAGE_RECEIVED" in event_types
        assert "TRANSCRIPTION_STARTED" not in event_types
        assert "CONTEXT_IDENTIFIED" in event_types
        assert event_types[-2:] == ["CHANNEL_CHANGED", "HUMAN_HANDOFF"]


def test_new_service_deletes_previous_context(monkeypatch):
    monkeypatch.setattr(
        "routes.api.context_service.analyze_context",
        lambda _message, _department: ContextCase(
            intent="SEGUNDA_VIA",
            category="FATURAMENTO",
            problem="Solicitação de segunda via",
            summary="Cliente solicita segunda via da fatura.",
            destination_department="FINANCEIRO",
            suggested_action="EXIBIR_FATURA",
            priority="NORMAL",
        ),
    )
    with TestClient(app) as client:
        session = client.post(
            "/api/sessions/message",
            json={"cpf": "12345678900", "message": "Quero a segunda via da fatura."},
        ).json()["session"]

        duplicate = client.post(
            "/api/sessions",
            json={"cpf": "12345678900", "initial_department": "INTERNET"},
        )
        assert duplicate.status_code == 409

        removed = client.delete(f"/api/sessions/{session['id']}")
        assert removed.status_code == 200
        assert client.get("/api/sessions/active/12345678900").status_code == 404

        replacement = client.post(
            "/api/sessions",
            json={"cpf": "12345678900", "initial_department": "INTERNET"},
        )
        assert replacement.status_code == 201
        assert client.get(f"/api/sessions/{session['id']}").status_code == 404


def test_minha_claro_contains_manual_navigation_without_creating_context():
    with TestClient(app) as client:
        response = client.get("/minha-claro")
        assert response.status_code == 200
        for area in ("billing", "payments", "internet", "phone", "plans"):
            assert f'data-area="{area}"' in response.text
        assert client.get("/api/sessions/active/12345678900").status_code == 404


def test_whatsapp_ai_failure_does_not_leave_orphan_session(monkeypatch):
    def unavailable_context(_message: str, _department: str):
        raise ContextServiceError("IA de contextualização indisponível.")

    monkeypatch.setattr("routes.api.context_service.analyze_context", unavailable_context)
    with TestClient(app) as client:
        response = client.post(
            "/api/sessions/message",
            json={"cpf": "12345678900", "message": "Minha linha não realiza chamadas."},
        )
        assert response.status_code == 503
        assert client.get("/api/sessions/active/12345678900").status_code == 404
        assert client.get("/api/sessions").json() == []
