from __future__ import annotations

from types import SimpleNamespace

import pytest

from config import settings
from services import transcription_service
from services.transcription_service import TranscriptionError, TranscriptionProviderError


def webm_bytes(size: int = 512) -> bytes:
    return b"\x1a\x45\xdf\xa3" + b"\x00" * (size - 4)


def test_missing_audio_has_friendly_error(tmp_path):
    with pytest.raises(TranscriptionError, match="não foi encontrada"):
        transcription_service.transcribe_audio(tmp_path / "inexistente.wav")


def test_invalid_content_is_rejected_even_with_audio_extension(tmp_path):
    path = tmp_path / "falso.webm"
    path.write_bytes(b"texto" * 100)
    with pytest.raises(TranscriptionError, match="não corresponde"):
        transcription_service.validate_audio_file(path)


def test_valid_webm_signature_is_accepted(tmp_path):
    path = tmp_path / "gravacao.webm"
    path.write_bytes(webm_bytes())
    transcription_service.validate_audio_file(path)


def test_empty_or_too_short_recording_is_rejected(tmp_path):
    path = tmp_path / "vazio.webm"
    path.write_bytes(b"\x1a\x45\xdf\xa3")
    with pytest.raises(TranscriptionError, match="curta demais"):
        transcription_service.validate_audio_file(path)


def test_missing_key_is_clear(tmp_path):
    path = tmp_path / "gravacao.webm"
    path.write_bytes(webm_bytes())
    original = settings.groq_api_key
    object.__setattr__(settings, "groq_api_key", "")
    try:
        with pytest.raises(TranscriptionProviderError, match="GROQ_API_KEY"):
            transcription_service.transcribe_audio(path)
    finally:
        object.__setattr__(settings, "groq_api_key", original)


def test_transcription_is_simulated_without_api_call(monkeypatch, tmp_path):
    path = tmp_path / "gravacao.webm"
    path.write_bytes(webm_bytes())

    class Transcriptions:
        @staticmethod
        def create(**kwargs):
            assert kwargs["model"] == settings.groq_transcription_model
            assert kwargs["language"] == "pt"
            assert kwargs["file"][0].endswith(".webm")
            return SimpleNamespace(text="Minha internet está sem funcionar.")

    fake_client = SimpleNamespace(audio=SimpleNamespace(transcriptions=Transcriptions()))
    monkeypatch.setattr(transcription_service, "_create_client", lambda: fake_client)
    assert transcription_service.transcribe_audio(path) == "Minha internet está sem funcionar."


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
    assert expected in str(transcription_service._friendly_api_error(error))
