from __future__ import annotations

import pytest

from services.transcription_service import TranscriptionError, dependency_available, transcribe_audio


def test_faster_whisper_dependency_is_installed():
    assert dependency_available() is True


def test_missing_audio_has_friendly_error_without_loading_model(tmp_path):
    with pytest.raises(TranscriptionError, match="não foi encontrada"):
        transcribe_audio(tmp_path / "inexistente.wav")
