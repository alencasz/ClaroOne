from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from config import settings
from database import database_health
from schemas import HumanRoute, MessageSessionCreate, SessionCreate, SessionResume
from services import cce_service, context_service, transcription_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


def _public_session(session: dict) -> dict:
    result = dict(session)
    result["audio_available"] = bool(result.pop("audio_path", None))
    return result


def _clear_uploads() -> None:
    for path in settings.upload_dir.iterdir():
        if path.is_file() and path.name != ".gitkeep":
            path.unlink()


def _handle_domain_error(exc: Exception) -> HTTPException:
    if isinstance(exc, cce_service.NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, cce_service.SessionUnavailableError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, (cce_service.CCEError, ValueError)):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail="Não foi possível concluir a operação.")


@router.get("/health")
def health():
    ollama_ok, ollama_state = context_service.health_check()
    return {
        "backend": "ok",
        "database": "ok" if database_health() else "error",
        "ollama": "ok" if ollama_ok else ollama_state,
        "ollama_model": settings.ollama_model,
        "whisper": transcription_service.model_status(),
        "whisper_model": settings.whisper_model,
        "demo_fallback": settings.demo_fallback,
    }


@router.get("/customers/{cpf}")
def customer(cpf: str):
    try:
        found = cce_service.get_customer(cpf)
    except ValueError as exc:
        raise _handle_domain_error(exc) from exc
    if not found:
        raise HTTPException(status_code=404, detail="Cliente fictício não encontrado.")
    return found


@router.post("/sessions", status_code=201)
def create_session(payload: SessionCreate):
    try:
        return _public_session(cce_service.create_session(payload.cpf, payload.initial_department))
    except Exception as exc:
        raise _handle_domain_error(exc) from exc


@router.post("/sessions/message", status_code=201)
def create_session_from_message(payload: MessageSessionCreate):
    session: dict | None = None
    try:
        session = cce_service.create_message_session(payload.cpf, payload.message)
        case = context_service.analyze_context(payload.message, "ATENDIMENTO DIGITAL / WHATSAPP")
        updated = cce_service.store_context(
            session["id"],
            case,
            status="EM_ATENDIMENTO_HUMANO",
            register_suspension=False,
        )
        cce_service.create_event(
            session["id"],
            "WHATSAPP",
            "HUMAN_HANDOFF",
            "Conversa encaminhada ao setor responsável",
        )
        return {"case": case.model_dump(), "session": _public_session(updated)}
    except context_service.ContextServiceError as exc:
        if session:
            cce_service.delete_session(session["id"])
        logger.exception("Erro ao interpretar mensagem inicial do WhatsApp")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        if session:
            cce_service.delete_session(session["id"])
        raise _handle_domain_error(exc) from exc


@router.get("/sessions")
def sessions(include_closed: bool = True):
    return [_public_session(session) for session in cce_service.list_sessions(include_closed=include_closed)]


@router.get("/sessions/active/{cpf}")
def active_session(cpf: str):
    try:
        session = cce_service.find_active_session(cpf)
    except Exception as exc:
        raise _handle_domain_error(exc) from exc
    if not session:
        raise HTTPException(status_code=404, detail="Não encontramos nenhum atendimento recente.")
    return _public_session(session)


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    try:
        session = cce_service.get_session(session_id)
        session["events"] = cce_service.get_timeline(session_id)
        return _public_session(session)
    except Exception as exc:
        raise _handle_domain_error(exc) from exc


@router.post("/sessions/{session_id}/audio")
async def upload_audio(session_id: str, audio: UploadFile = File(...)):
    suffix = Path(audio.filename or "").suffix.lower()
    if suffix not in transcription_service.SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Formato inválido. Envie um arquivo WAV, MP3 ou M4A.")
    internal_path = settings.upload_dir / f"{uuid.uuid4().hex}{suffix}"
    size = 0
    try:
        with internal_path.open("wb") as destination:
            while chunk := await audio.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"A gravação deve ter no máximo {settings.max_upload_bytes // 1024 // 1024} MB.",
                    )
                destination.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="O arquivo de áudio está vazio.")
        transcription_service.validate_audio_file(internal_path)
        session = cce_service.register_audio(session_id, str(internal_path))
        return {"message": "Áudio recebido.", "filename": audio.filename, "session": _public_session(session)}
    except HTTPException:
        internal_path.unlink(missing_ok=True)
        raise
    except transcription_service.TranscriptionError as exc:
        internal_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        internal_path.unlink(missing_ok=True)
        raise _handle_domain_error(exc) from exc
    finally:
        await audio.close()


@router.post("/sessions/{session_id}/transcribe")
def transcribe(session_id: str):
    try:
        session = cce_service.start_processing(session_id)
        transcript = transcription_service.transcribe_audio(session["audio_path"])
        updated = cce_service.store_transcript(session_id, transcript)
        return {"transcript": transcript, "session": _public_session(updated)}
    except transcription_service.TranscriptionError as exc:
        logger.exception("Erro amigável de transcrição na sessão %s", session_id)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise _handle_domain_error(exc) from exc


@router.post("/sessions/{session_id}/contextualize")
def contextualize(session_id: str):
    try:
        session = cce_service.get_session(session_id)
        if not session.get("transcript"):
            raise cce_service.CCEError("Transcreva a gravação antes de interpretar o contexto.")
        cce_service.mark_context_processing(session_id)
        case = context_service.analyze_context(session["transcript"], session["initial_department"])
        updated = cce_service.store_context(session_id, case)
        return {"case": case.model_dump(), "session": _public_session(updated)}
    except context_service.ContextServiceError as exc:
        logger.exception("Erro amigável de contexto na sessão %s", session_id)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise _handle_domain_error(exc) from exc


@router.post("/sessions/{session_id}/resume")
def resume(session_id: str, payload: SessionResume):
    try:
        return _public_session(cce_service.resume_session(session_id, payload.channel))
    except Exception as exc:
        raise _handle_domain_error(exc) from exc


@router.post("/sessions/{session_id}/route-human")
def route_to_human(session_id: str, payload: HumanRoute):
    try:
        return _public_session(cce_service.route_to_human(session_id, payload.channel))
    except Exception as exc:
        raise _handle_domain_error(exc) from exc


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    try:
        removed = cce_service.delete_session(session_id)
        audio_path = removed.get("audio_path")
        if audio_path:
            path = Path(audio_path).resolve()
            if path.parent == settings.upload_dir.resolve() and path.is_file():
                path.unlink()
        return {"message": "Contexto anterior removido. Um novo atendimento pode ser iniciado."}
    except Exception as exc:
        raise _handle_domain_error(exc) from exc


@router.post("/sessions/{session_id}/handoff")
def handoff(session_id: str):
    try:
        return _public_session(cce_service.handoff_session(session_id))
    except Exception as exc:
        raise _handle_domain_error(exc) from exc


@router.post("/sessions/{session_id}/resolve")
def resolve(session_id: str):
    try:
        return _public_session(cce_service.resolve_session(session_id))
    except Exception as exc:
        raise _handle_domain_error(exc) from exc


@router.get("/sessions/{session_id}/events")
def events(session_id: str):
    try:
        return cce_service.get_timeline(session_id)
    except Exception as exc:
        raise _handle_domain_error(exc) from exc


@router.post("/demo/reset")
def reset_demo():
    try:
        cce_service.reset_demo()
        _clear_uploads()
        return {"message": "Demonstração reiniciada. Clientes fictícios preservados."}
    except Exception as exc:
        logger.exception("Falha ao reiniciar demonstração")
        raise HTTPException(status_code=500, detail="Não foi possível reiniciar a demonstração.") from exc


@router.post("/demo/clear")
def clear_demo_data():
    try:
        cce_service.reset_demo()
        _clear_uploads()
        return {"message": "Dados da demonstração removidos. Clientes fictícios preservados."}
    except Exception as exc:
        logger.exception("Falha ao limpar dados da demonstração")
        raise HTTPException(status_code=500, detail="Não foi possível limpar os dados.") from exc
