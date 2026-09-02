from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from threading import Lock

from config import settings


logger = logging.getLogger(__name__)
_model = None
_model_lock = Lock()

SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".m4a"}
DEMO_TRANSCRIPT = (
    "Olá, estou entrando em contato porque vi na minha fatura uma cobrança de trinta e cinco "
    "reais referente a um pacote adicional de internet. Eu não contratei esse pacote e gostaria "
    "de contestar essa cobrança."
)


class TranscriptionError(Exception):
    pass


def dependency_available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def model_status() -> str:
    if not dependency_available():
        return "dependency_missing"
    return "loaded" if _model is not None else "configured"


def validate_audio_file(audio_path: str | Path) -> None:
    path = Path(audio_path)
    if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise TranscriptionError("A gravação não foi encontrada ou possui formato inválido.")
    try:
        import av

        with av.open(str(path)) as container:
            if not any(stream.type == "audio" for stream in container.streams):
                raise TranscriptionError("O arquivo enviado não contém uma faixa de áudio.")
    except TranscriptionError:
        raise
    except Exception as exc:
        raise TranscriptionError(
            "A gravação não pôde ser lida. Envie um arquivo de áudio WAV, MP3 ou M4A válido."
        ) from exc


def _get_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            try:
                from faster_whisper import WhisperModel

                _model = WhisperModel(settings.whisper_model, device="cpu", compute_type="int8")
            except Exception as exc:
                logger.exception("Não foi possível carregar o faster-whisper")
                raise TranscriptionError(
                    "A IA de transcrição não pôde ser carregada. Verifique a instalação e o modelo configurado."
                ) from exc
    return _model


def transcribe_audio(audio_path: str | Path) -> str:
    path = Path(audio_path)
    validate_audio_file(path)

    if settings.demo_fallback:
        logger.warning("DEMO_FALLBACK ativo: utilizando transcrição explícita de demonstração")
        return DEMO_TRANSCRIPT

    try:
        model = _get_model()
        segments, _info = model.transcribe(str(path), language="pt", vad_filter=True)
        transcript = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
    except TranscriptionError:
        raise
    except Exception as exc:
        logger.exception("Falha ao transcrever áudio")
        raise TranscriptionError(
            "Não foi possível transcrever a gravação. Verifique se o arquivo de áudio é válido."
        ) from exc

    if not transcript:
        raise TranscriptionError("A gravação não contém fala reconhecível em português.")
    return transcript
