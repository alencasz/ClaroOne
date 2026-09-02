from __future__ import annotations

from fastapi.testclient import TestClient

from app import app


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
