from __future__ import annotations

import json
import logging
import re
from typing import Any

from groq import Groq
from pydantic import ValidationError

from config import settings
from schemas import ContextCase


logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você é a IA DE CONTEXTO do protótipo acadêmico Claro One.
Sua função é analisar uma interação de atendimento já finalizada. Você NÃO conversa com o cliente.

Receba o setor escolhido na URA e a transcrição. O setor é apenas contexto, não verdade absoluta.
1. Entenda o problema principal.
2. Gere um resumo curto e objetivo em português do Brasil.
3. Extraia somente entidades explicitamente presentes.
4. Não invente valores, produtos, datas, causas ou fatos.
5. Use null quando uma informação não existir ou não estiver suficientemente suportada.
6. Escolha um setor de destino coerente e sugira a próxima ação.
7. Responda exclusivamente no formato estruturado solicitado.

Padronização operacional:
- Use categorias como FATURAMENTO, INTERNET, TELEFONIA, CANCELAMENTO ou OUTROS quando aplicáveis.
- Use destinos como FINANCEIRO, SUPORTE_TECNICO, TELEFONIA, RETENCAO_CANCELAMENTO ou ATENDIMENTO_GERAL.
- Item não reconhecido em fatura é contestação de faturamento, ainda que o produto mencione internet.
- Falha de conexão, modem, sinal ou serviço indisponível pertence a INTERNET / SUPORTE_TECNICO.
- Problema de linha ou chamadas pertence a TELEFONIA. Pedido de cancelamento pertence a CANCELAMENTO.
- Use identificadores MAIUSCULOS_COM_UNDERLINE para intent, category, destination_department e suggested_action.
- Cada entidade deve ter um nome curto e um valor JSON simples. Não inclua entidades sem apoio no texto.
- A prioridade deve ser BAIXA, NORMAL, ALTA ou URGENTE e considerar impacto e tom explicitamente demonstrados.
"""

CONTEXT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent": {"type": ["string", "null"]},
        "category": {"type": ["string", "null"]},
        "problem": {"type": ["string", "null"]},
        "summary": {"type": ["string", "null"]},
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": ["string", "number", "boolean", "null"]},
                },
                "required": ["name", "value"],
                "additionalProperties": False,
            },
        },
        "destination_department": {"type": ["string", "null"]},
        "suggested_action": {"type": ["string", "null"]},
        "priority": {"type": "string", "enum": ["BAIXA", "NORMAL", "ALTA", "URGENTE"]},
    },
    "required": [
        "intent",
        "category",
        "problem",
        "summary",
        "entities",
        "destination_department",
        "suggested_action",
        "priority",
    ],
    "additionalProperties": False,
}

DEMO_CASE = ContextCase(
    intent="CONTESTACAO_FATURA",
    category="FATURAMENTO",
    problem="Cobrança não reconhecida",
    summary="Cliente contesta cobrança de R$ 35,00 por pacote adicional de internet que afirma não ter contratado.",
    entities={
        "valor": 35.0,
        "produto": "Pacote adicional de internet",
        "reconhece_contratacao": False,
    },
    destination_department="FINANCEIRO",
    suggested_action="ANALISAR_ESTORNO",
    priority="NORMAL",
)


class ContextServiceError(Exception):
    pass


def _create_client() -> Groq:
    if not settings.groq_api_key:
        raise ContextServiceError(
            "A chave GROQ_API_KEY não está configurada. Adicione a chave ao arquivo .env."
        )
    return Groq(api_key=settings.groq_api_key, timeout=settings.groq_timeout_seconds)


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1)
    else:
        start = cleaned.find("{")
        if start < 0:
            raise ValueError("Nenhum objeto JSON encontrado")
        depth = 0
        in_string = False
        escaped = False
        end = None
        for index, char in enumerate(cleaned[start:], start=start):
            if escaped:
                escaped = False
                continue
            if char == "\\" and in_string:
                escaped = True
                continue
            if char == '"':
                in_string = not in_string
            elif not in_string:
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        end = index + 1
                        break
        if end is None:
            raise ValueError("Objeto JSON incompleto")
        cleaned = cleaned[start:end]
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("A resposta não é um objeto JSON")
    return value


def _normalize_entities(payload: dict[str, Any]) -> dict[str, Any]:
    entities = payload.get("entities")
    if not isinstance(entities, list):
        return payload
    normalized = dict(payload)
    normalized["entities"] = {
        str(item["name"]): item.get("value")
        for item in entities
        if isinstance(item, dict) and item.get("name")
    }
    return normalized


def parse_context_response(text: str) -> ContextCase:
    return ContextCase.model_validate(_normalize_entities(_extract_json(text)))


def _friendly_api_error(exc: Exception) -> ContextServiceError:
    status_code = getattr(exc, "status_code", None)
    error_name = type(exc).__name__
    if status_code in {401, 403} or error_name == "AuthenticationError":
        return ContextServiceError(
            "A chave da Groq é inválida ou não possui acesso. Verifique GROQ_API_KEY no arquivo .env."
        )
    if status_code == 429 or error_name == "RateLimitError":
        return ContextServiceError(
            "O limite de uso da Groq foi atingido. Aguarde alguns instantes e tente novamente."
        )
    if error_name in {"APITimeoutError", "TimeoutException", "ReadTimeout"}:
        return ContextServiceError(
            "A contextualização excedeu o tempo de resposta da Groq. Tente novamente."
        )
    if error_name in {"APIConnectionError", "ConnectError", "NetworkError"}:
        return ContextServiceError(
            "Não foi possível conectar à Groq. Verifique sua internet e tente novamente."
        )
    if status_code == 400:
        return ContextServiceError(
            "A Groq recusou o formato do contexto. Verifique o modelo configurado e tente novamente."
        )
    return ContextServiceError(
        "A Groq não conseguiu interpretar o atendimento. Tente novamente."
    )


def health_check() -> tuple[str, bool]:
    if not settings.groq_api_key:
        return "not_configured", False
    try:
        models = _create_client().models.list()
        available = {item.id for item in getattr(models, "data", [])}
        required = {settings.groq_transcription_model, settings.groq_context_model}
        return ("ok" if required.issubset(available) else "model_missing"), True
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        if status_code in {401, 403} or type(exc).__name__ == "AuthenticationError":
            return "authentication_error", True
        if status_code == 429 or type(exc).__name__ == "RateLimitError":
            return "rate_limited", True
        return "unavailable", True


def _generate(messages: list[dict[str, str]]) -> str:
    try:
        response = _create_client().chat.completions.create(
            model=settings.groq_context_model,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "claro_one_context_case",
                    "strict": True,
                    "schema": CONTEXT_JSON_SCHEMA,
                },
            },
            reasoning_effort="low",
            temperature=0.1,
            max_completion_tokens=900,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Resposta vazia")
        return content
    except ContextServiceError:
        raise
    except Exception as exc:
        logger.exception("Falha na contextualização pela Groq")
        raise _friendly_api_error(exc) from exc


def analyze_context(transcript: str, initial_department: str) -> ContextCase:
    if not transcript.strip():
        raise ContextServiceError("Não há transcrição para interpretar.")
    if settings.demo_fallback:
        logger.warning("DEMO_FALLBACK ativo: utilizando contexto explícito de demonstração")
        return DEMO_CASE

    user_prompt = (
        f"SETOR ESCOLHIDO NA URA: {initial_department}\n\n"
        f"TRANSCRIÇÃO DA INTERAÇÃO:\n{transcript}"
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    first_response = _generate(messages)
    try:
        return parse_context_response(first_response)
    except (ValueError, json.JSONDecodeError, ValidationError):
        logger.warning("Resposta estruturada inválida; solicitando uma única correção")

    correction_messages = messages + [
        {"role": "assistant", "content": first_response},
        {
            "role": "user",
            "content": (
                "Corrija a resposta. Problema, resumo e setor de destino devem ser preenchidos quando "
                "a interação descreve uma solicitação. Use apenas fatos apoiados no texto."
            ),
        },
    ]
    corrected = _generate(correction_messages)
    try:
        return parse_context_response(corrected)
    except (ValueError, json.JSONDecodeError, ValidationError) as exc:
        logger.exception("Groq retornou contexto inválido após uma correção")
        raise ContextServiceError(
            "A IA de contexto respondeu em formato inválido. Tente processar novamente."
        ) from exc
