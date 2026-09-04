from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Any

from config import settings
from database import get_connection, seed_customers
from models import DEPARTMENTS, RESUMABLE_STATUSES
from schemas import ContextCase
from utils import normalize_cpf, now_local


class CCEError(Exception):
    pass


class NotFoundError(CCEError):
    pass


class SessionUnavailableError(CCEError):
    pass


def _row_to_session(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    try:
        result["structured_context"] = json.loads(result.get("structured_context") or "{}")
    except json.JSONDecodeError:
        result["structured_context"] = {}
    return result


def _protocol() -> str:
    return f"CCE-{uuid.uuid4().hex[:8].upper()}"


def create_event(
    session_id: str,
    channel: str,
    event_type: str,
    description: str,
    connection: sqlite3.Connection | None = None,
) -> None:
    if connection is None:
        with get_connection() as owned_connection:
            create_event(session_id, channel, event_type, description, owned_connection)
        return
    connection.execute(
        """INSERT INTO cce_events
           (session_id, channel, event_type, description, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (session_id, channel, event_type, description, now_local().isoformat()),
    )


def get_customer(cpf: str) -> dict[str, str] | None:
    normalized = normalize_cpf(cpf)
    with get_connection() as connection:
        row = connection.execute(
            "SELECT cpf, name FROM customers WHERE cpf = ?", (normalized,)
        ).fetchone()
    return dict(row) if row else None


def create_session(cpf: str, initial_department: str) -> dict[str, Any]:
    normalized = normalize_cpf(cpf)
    department = initial_department.strip().upper()
    if department not in DEPARTMENTS:
        raise CCEError("Selecione um setor válido.")
    customer = get_customer(normalized)
    if not customer:
        raise NotFoundError("Cliente fictício não encontrado.")
    if find_active_session(normalized):
        raise SessionUnavailableError(
            "Já existe uma sessão ativa. Continue ou remova o contexto anterior antes de começar outra."
        )

    session_id = str(uuid.uuid4())
    timestamp = now_local()
    expires_at = timestamp + timedelta(hours=settings.cce_ttl_hours)
    with get_connection() as connection:
        connection.execute(
            """INSERT INTO cce_sessions (
                id, protocol, cpf, customer_name, status, channel_origin,
                current_channel, initial_department, structured_context,
                created_at, updated_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                _protocol(),
                normalized,
                customer["name"],
                "EM_ATENDIMENTO",
                "TELEFONE",
                "TELEFONE",
                department,
                "{}",
                timestamp.isoformat(),
                timestamp.isoformat(),
                expires_at.isoformat(),
            ),
        )
        create_event(session_id, "TELEFONE", "CUSTOMER_AUTHENTICATED", "Cliente autenticado", connection)
        create_event(
            session_id,
            "URA",
            "DEPARTMENT_SELECTED",
            f"{DEPARTMENTS[department]} selecionado",
            connection,
        )
        create_event(session_id, "TELEFONE", "SESSION_CREATED", "CCE criada", connection)
    return get_session(session_id)


def create_message_session(cpf: str, message: str) -> dict[str, Any]:
    normalized = normalize_cpf(cpf)
    customer = get_customer(normalized)
    if not customer:
        raise NotFoundError("Cliente fictício não encontrado.")
    if find_active_session(normalized):
        raise SessionUnavailableError(
            "Já existe uma sessão ativa. Continue ou remova o contexto anterior antes de começar outra."
        )
    message = message.strip()
    if len(message) < 3:
        raise CCEError("Escreva uma mensagem para iniciar o atendimento.")

    session_id = str(uuid.uuid4())
    timestamp = now_local()
    expires_at = timestamp + timedelta(hours=settings.cce_ttl_hours)
    with get_connection() as connection:
        connection.execute(
            """INSERT INTO cce_sessions (
                id, protocol, cpf, customer_name, status, channel_origin,
                current_channel, initial_department, transcript, structured_context,
                created_at, updated_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                _protocol(),
                normalized,
                customer["name"],
                "PROCESSANDO",
                "WHATSAPP",
                "WHATSAPP",
                "ATENDIMENTO_DIGITAL",
                message,
                "{}",
                timestamp.isoformat(),
                timestamp.isoformat(),
                expires_at.isoformat(),
            ),
        )
        create_event(session_id, "WHATSAPP", "CUSTOMER_AUTHENTICATED", "Cliente autenticado", connection)
        create_event(session_id, "WHATSAPP", "SESSION_CREATED", "CCE criada a partir da mensagem", connection)
        create_event(session_id, "WHATSAPP", "MESSAGE_RECEIVED", "Mensagem inicial recebida", connection)
        create_event(
            session_id,
            "IA_CONTEXTO",
            "CONTEXT_PROCESSING_STARTED",
            "Interpretação da mensagem iniciada",
            connection,
        )
    return get_session(session_id, check_expiration=False)


def get_session(session_id: str, check_expiration: bool = True) -> dict[str, Any]:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM cce_sessions WHERE id = ?", (session_id,)).fetchone()
    session = _row_to_session(row)
    if not session:
        raise NotFoundError("CCE não encontrada.")
    if check_expiration:
        session = expire_if_needed(session)
    return session


def expire_if_needed(session: dict[str, Any]) -> dict[str, Any]:
    if session["status"] in {"RESOLVIDA", "EXPIRADA"}:
        return session
    expires_at = datetime.fromisoformat(session["expires_at"])
    if expires_at <= now_local():
        with get_connection() as connection:
            connection.execute(
                "UPDATE cce_sessions SET status = 'EXPIRADA', updated_at = ? WHERE id = ?",
                (now_local().isoformat(), session["id"]),
            )
            create_event(session["id"], "SISTEMA", "SESSION_EXPIRED", "CCE expirada", connection)
        session["status"] = "EXPIRADA"
    return session


def find_active_session(cpf: str) -> dict[str, Any] | None:
    normalized = normalize_cpf(cpf)
    with get_connection() as connection:
        rows = connection.execute(
            """SELECT * FROM cce_sessions
               WHERE cpf = ? AND status IN ('SUSPENSA', 'RETOMADA', 'EM_ATENDIMENTO_HUMANO')
               ORDER BY updated_at DESC""",
            (normalized,),
        ).fetchall()
    for row in rows:
        session = expire_if_needed(_row_to_session(row))
        if session["status"] not in {"RESOLVIDA", "EXPIRADA"}:
            return session
    return None


def list_sessions(include_closed: bool = True) -> list[dict[str, Any]]:
    query = "SELECT * FROM cce_sessions"
    if not include_closed:
        query += " WHERE status NOT IN ('RESOLVIDA', 'EXPIRADA')"
    query += " ORDER BY updated_at DESC"
    with get_connection() as connection:
        rows = connection.execute(query).fetchall()
    return [expire_if_needed(_row_to_session(row)) for row in rows]


def update_session(session_id: str, **fields: Any) -> dict[str, Any]:
    allowed = {
        "status", "current_channel", "audio_path", "transcript", "intent", "category",
        "problem", "summary", "structured_context", "destination_department",
        "suggested_action", "priority", "expires_at",
    }
    values = {key: value for key, value in fields.items() if key in allowed}
    if not values:
        return get_session(session_id)
    if "structured_context" in values:
        values["structured_context"] = json.dumps(values["structured_context"], ensure_ascii=False)
    values["updated_at"] = now_local().isoformat()
    assignments = ", ".join(f"{key} = ?" for key in values)
    with get_connection() as connection:
        cursor = connection.execute(
            f"UPDATE cce_sessions SET {assignments} WHERE id = ?",
            (*values.values(), session_id),
        )
        if cursor.rowcount == 0:
            raise NotFoundError("CCE não encontrada.")
    return get_session(session_id, check_expiration=False)


def register_audio(session_id: str, audio_path: str) -> dict[str, Any]:
    session = get_session(session_id)
    if session["status"] in {"RESOLVIDA", "EXPIRADA"}:
        raise SessionUnavailableError("Esta CCE não pode mais receber áudio.")
    if session.get("transcript"):
        raise SessionUnavailableError("A gravação desta CCE já foi processada.")
    result = update_session(session_id, audio_path=audio_path)
    create_event(session_id, "TELEFONE", "AUDIO_RECEIVED", "Gravação da ligação recebida")
    return result


def start_call(session_id: str) -> dict[str, Any]:
    session = get_session(session_id)
    if session["status"] != "EM_ATENDIMENTO" or session.get("audio_path"):
        raise SessionUnavailableError("Esta ligação não pode ser iniciada novamente.")
    events = get_timeline(session_id)
    if any(event["event_type"] == "CALL_STARTED" for event in events):
        return session
    create_event(session_id, "TELEFONE", "CALL_STARTED", "Ligação iniciada")
    return get_session(session_id, check_expiration=False)


def start_processing(session_id: str) -> dict[str, Any]:
    session = get_session(session_id)
    if not session.get("audio_path"):
        raise CCEError("Adicione uma gravação para processar o atendimento.")
    if session.get("transcript"):
        raise SessionUnavailableError("Esta gravação já foi transcrita e não será processada novamente.")
    update_session(session_id, status="PROCESSANDO")
    events = get_timeline(session_id)
    if not any(event["event_type"] == "CALL_FINISHED" for event in events):
        create_event(session_id, "TELEFONE", "CALL_FINISHED", "Ligação encerrada")
    create_event(session_id, "IA_TRANSCRICAO", "TRANSCRIPTION_STARTED", "Transcrição iniciada")
    return get_session(session_id, check_expiration=False)


def store_transcript(session_id: str, transcript: str) -> dict[str, Any]:
    result = update_session(session_id, transcript=transcript)
    create_event(session_id, "IA_TRANSCRICAO", "TRANSCRIPTION_COMPLETED", "Transcrição concluída")
    return result


def store_context(
    session_id: str,
    case: ContextCase,
    status: str = "SUSPENSA",
    register_suspension: bool = True,
) -> dict[str, Any]:
    result = update_session(
        session_id,
        status=status,
        intent=case.intent,
        category=case.category,
        problem=case.problem,
        summary=case.summary,
        structured_context=case.structured_context,
        destination_department=case.destination_department,
        suggested_action=case.suggested_action,
        priority=case.priority,
    )
    create_event(session_id, "IA_CONTEXTO", "CONTEXT_IDENTIFIED", "Contexto estruturado identificado")
    if register_suspension:
        create_event(session_id, "SISTEMA", "SESSION_SUSPENDED", "CCE mantida ativa para continuidade")
    return result


def mark_context_processing(session_id: str) -> None:
    get_session(session_id)
    create_event(session_id, "IA_CONTEXTO", "CONTEXT_PROCESSING_STARTED", "Interpretação do contexto iniciada")


def resume_session(session_id: str, channel: str) -> dict[str, Any]:
    channel = channel.upper()
    if channel not in {"TELEFONE", "WHATSAPP", "MINHA_CLARO"}:
        raise CCEError("Canal de retomada inválido.")
    session = get_session(session_id)
    if session["status"] not in RESUMABLE_STATUSES:
        raise SessionUnavailableError("Esta sessão não está disponível para retomada.")
    renewed = now_local() + timedelta(hours=settings.cce_ttl_hours)
    result = update_session(
        session_id, status="RETOMADA", current_channel=channel, expires_at=renewed.isoformat()
    )
    create_event(session_id, channel, "SESSION_RESUMED", f"Sessão retomada no canal {channel}")
    create_event(session_id, channel, "CHANNEL_CHANGED", f"Canal atual alterado para {channel}")
    return result


def route_to_human(session_id: str, channel: str) -> dict[str, Any]:
    channel = channel.upper()
    if channel not in {"TELEFONE", "WHATSAPP", "COCKPIT"}:
        raise CCEError("Canal de atendimento humano inválido.")
    session = get_session(session_id)
    if session["status"] in {"RESOLVIDA", "EXPIRADA"}:
        raise SessionUnavailableError("Esta sessão não está disponível.")
    if session["status"] == "EM_ATENDIMENTO_HUMANO" and session["current_channel"] == channel:
        return session
    result = update_session(
        session_id,
        status="EM_ATENDIMENTO_HUMANO",
        current_channel=channel,
    )
    create_event(session_id, channel, "HUMAN_HANDOFF", "Encaminhamento para especialista iniciado")
    return result


def handoff_session(session_id: str) -> dict[str, Any]:
    result = route_to_human(session_id, "COCKPIT")
    return result


def delete_session(session_id: str) -> dict[str, Any]:
    session = get_session(session_id, check_expiration=False)
    with get_connection() as connection:
        connection.execute("DELETE FROM cce_sessions WHERE id = ?", (session_id,))
    return session


def resolve_session(session_id: str) -> dict[str, Any]:
    session = get_session(session_id)
    if session["status"] == "EXPIRADA":
        raise SessionUnavailableError("Uma sessão expirada não pode ser resolvida.")
    if session["status"] != "RESOLVIDA":
        update_session(session_id, status="RESOLVIDA")
        create_event(session_id, "COCKPIT", "SESSION_RESOLVED", "Atendimento marcado como resolvido")
    return get_session(session_id, check_expiration=False)


def get_timeline(session_id: str) -> list[dict[str, Any]]:
    get_session(session_id, check_expiration=False)
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM cce_events WHERE session_id = ? ORDER BY created_at ASC, id ASC",
            (session_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def reset_demo() -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM cce_events")
        connection.execute("DELETE FROM cce_sessions")
        seed_customers(connection)
