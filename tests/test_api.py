from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app import app
from schemas import ContextCase
from services.context_service import ContextServiceError


def webm_bytes(size: int = 512) -> bytes:
    return b"\x1a\x45\xdf\xa3" + b"\x00" * (size - 4)


def internet_case() -> ContextCase:
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
        assert len(timeline) == 3

        started = client.post(f"/api/sessions/{session['id']}/call/start")
        assert started.status_code == 200
        timeline = client.get(f"/api/sessions/{session['id']}/events").json()
        assert timeline[-1]["event_type"] == "CALL_STARTED"


def test_header_has_only_home_brand_and_cockpit_while_home_keeps_channel_cards():
    with TestClient(app) as client:
        for path in ("/", "/telefone", "/whatsapp", "/minha-claro", "/atendente", "/debug"):
            response = client.get(path)
            assert response.status_code == 200
            header = re.search(r'<header class="topbar">(.*?)</header>', response.text, re.DOTALL)
            assert header
            markup = header.group(1)
            assert 'class="brand" href="/"' in markup
            assert 'href="/atendente"' in markup
            assert 'href="/telefone"' not in markup
            assert 'href="/whatsapp"' not in markup
            assert 'href="/minha-claro"' not in markup

        home = client.get("/").text
        for channel_path in ("/telefone", "/whatsapp", "/minha-claro", "/atendente"):
            assert f'class="channel-card' in home
            assert f'href="{channel_path}"' in home
        stylesheet = client.get("/static/css/global.css").text
        assert ".topnav { display: none;" not in stylesheet


def test_channel_templates_expose_shared_friendly_taxonomy_fields():
    with TestClient(app) as client:
        whatsapp = client.get("/whatsapp").text
        assert 'id="wa-category"' in whatsapp
        assert 'id="wa-destination-found"' in whatsapp
        minha_claro = client.get("/minha-claro").text
        assert 'id="mc-category"' in minha_claro
        assert 'id="mc-destination"' in minha_claro
        cockpit = client.get("/atendente").text
        assert 'id="cp-category"' in cockpit
        assert 'id="cp-destination"' in cockpit
        assert '<option value="OUTROS">Outros</option>' in cockpit
        debug = client.get("/debug").text
        assert "Categoria" in debug and "Destino" in debug
        common_js = client.get("/static/js/common.js").text
        assert "OUTROS: 'Atendimento geral'" in common_js


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
        assert "WEBM ou OGG" in response.json()["detail"]


def test_fake_wav_is_rejected_before_external_processing():
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
        assert "gravação" in response.json()["detail"]


def test_empty_and_too_short_browser_recordings_are_rejected():
    with TestClient(app) as client:
        session = client.post(
            "/api/sessions",
            json={"cpf": "12345678900", "initial_department": "INTERNET"},
        ).json()
        empty = client.post(
            f"/api/sessions/{session['id']}/audio",
            files={"audio": ("gravacao.webm", b"", "audio/webm")},
        )
        assert empty.status_code == 400
        assert "vazio" in empty.json()["detail"]

        too_short = client.post(
            f"/api/sessions/{session['id']}/audio",
            data={"duration_ms": "400"},
            files={"audio": ("gravacao.webm", webm_bytes(), "audio/webm")},
        )
        assert too_short.status_code == 400
        assert "curta demais" in too_short.json()["detail"]


def test_complete_audio_context_and_channel_flow_without_external_api(monkeypatch):
    transcript = "Minha internet está sem funcionar desde ontem e o modem está vermelho."
    monkeypatch.setattr(
        "routes.api.transcription_service.transcribe_audio",
        lambda _path: transcript,
    )
    monkeypatch.setattr(
        "routes.api.context_service.analyze_context",
        lambda received, _department: internet_case() if received == transcript else None,
    )

    with TestClient(app) as client:
        session = client.post(
            "/api/sessions",
            json={"cpf": "12345678900", "initial_department": "INTERNET"},
        ).json()
        assert client.post(f"/api/sessions/{session['id']}/call/start").status_code == 200
        uploaded = client.post(
            f"/api/sessions/{session['id']}/audio",
            data={"duration_ms": "2500"},
            files={"audio": ("gravacao.webm", webm_bytes(), "audio/webm")},
        )
        assert uploaded.status_code == 200
        assert uploaded.json()["session"]["audio_available"] is True

        transcribed = client.post(f"/api/sessions/{session['id']}/transcribe")
        assert transcribed.status_code == 200
        assert transcribed.json()["transcript"] == transcript
        contextualized = client.post(f"/api/sessions/{session['id']}/contextualize")
        assert contextualized.status_code == 200
        result = contextualized.json()["session"]
        assert result["status"] == "SUSPENSA"
        assert result["category"] == "INTERNET"
        assert result["destination_department"] == "SUPORTE_TECNICO"

        whatsapp = client.post(
            f"/api/sessions/{session['id']}/resume", json={"channel": "WHATSAPP"}
        )
        assert whatsapp.status_code == 200
        minha_claro = client.post(
            f"/api/sessions/{session['id']}/resume", json={"channel": "MINHA_CLARO"}
        )
        assert minha_claro.status_code == 200
        assert minha_claro.json()["current_channel"] == "MINHA_CLARO"
        assert client.get(f"/atendente?session={session['id']}").status_code == 200

        event_types = [
            event["event_type"]
            for event in client.get(f"/api/sessions/{session['id']}/events").json()
        ]
        assert event_types[:4] == [
            "CUSTOMER_AUTHENTICATED",
            "DEPARTMENT_SELECTED",
            "SESSION_CREATED",
            "CALL_STARTED",
        ]
        assert "TRANSCRIPTION_COMPLETED" in event_types
        assert "CONTEXT_IDENTIFIED" in event_types
        assert event_types.count("SESSION_RESUMED") == 2

        duplicate = client.post(f"/api/sessions/{session['id']}/transcribe")
        assert duplicate.status_code == 409


def test_whatsapp_can_create_context_then_continue_by_phone(monkeypatch):
    def fake_analysis(message: str, department: str) -> ContextCase:
        assert "internet" in message.lower()
        assert department == "ATENDIMENTO DIGITAL / WHATSAPP"
        return internet_case()

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


def test_health_check_shape_without_exposing_key(monkeypatch):
    monkeypatch.setattr("routes.api.context_service.health_check", lambda: ("ok", True))
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload == {
            "backend": "ok",
            "database": "ok",
            "groq": "ok",
            "groq_key_configured": True,
            "transcription_model": "whisper-large-v3-turbo",
            "context_model": "openai/gpt-oss-20b",
            "demo_fallback": False,
        }
        assert "api_key" not in payload


def test_reset_removes_sessions_and_preserves_real_seed_customers(monkeypatch):
    monkeypatch.setattr("routes.api.context_service.analyze_context", lambda *_args: internet_case())
    with TestClient(app) as client:
        created = client.post(
            "/api/sessions/message",
            json={"cpf": "12345678900", "message": "Minha internet não funciona."},
        )
        assert created.status_code == 201
        assert client.get("/api/sessions").json()
        reset = client.post("/api/demo/reset")
        assert reset.status_code == 200
        assert client.get("/api/sessions").json() == []
        from database import DEMO_CUSTOMERS

        expected = dict(DEMO_CUSTOMERS)
        assert len(expected) >= 12
        for cpf, name in expected.items():
            assert client.get(f"/api/customers/{cpf}").json()["name"] == name
