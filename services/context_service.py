from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from pydantic import ValidationError

from config import settings
from schemas import ContextCase


logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """/no_think
Você é a IA DE CONTEXTO do protótipo acadêmico Claro One.
Sua função é analisar uma interação de atendimento já finalizada. Você NÃO conversa com o cliente.

Receba o setor escolhido na URA e a transcrição. O setor é apenas contexto, não verdade absoluta.
1. Entenda o problema principal.
2. Gere um resumo curto e objetivo.
3. Extraia somente entidades explicitamente presentes.
4. Não invente valores, produtos, datas, causas ou fatos.
5. Use null quando uma informação não existir ou não estiver suficientemente suportada.
6. Escolha um setor de destino coerente e sugira a próxima ação.
7. Retorne SOMENTE um objeto JSON válido, sem markdown, comentários ou texto adicional.

Padronização para consistência operacional:
- Use categorias como FATURAMENTO, INTERNET, TELEFONIA, CANCELAMENTO ou OUTROS quando aplicáveis.
- Use destinos em português, como FINANCEIRO, SUPORTE_TECNICO, TELEFONIA,
  RETENCAO_CANCELAMENTO ou ATENDIMENTO_GERAL.
- Uma cobrança que o cliente afirma não reconhecer é uma contestação, não mero controle de custo.
- Se o problema é um item cobrado na fatura, classifique como faturamento e encaminhe ao FINANCEIRO,
  mesmo quando o produto cobrado tiver palavras como internet, dados ou telefonia.
- Use SUPORTE_TECNICO para falha de conexão, modem, sinal ou indisponibilidade do serviço;
  TELEFONIA para problema de linha ou chamadas; e RETENCAO_CANCELAMENTO para pedido de cancelamento.
- Para contestação de cobrança, prefira intent CONTESTACAO_FATURA e uma ação de análise da cobrança.
- Para internet indisponível ou modem com falha, prefira intent SUPORTE_INTERNET; não use intenção de
  contestação de fatura quando a conversa não menciona cobrança, preço, pagamento ou fatura.
- Normalize números explicitamente falados para número JSON e respostas sim/não para booleano.
- A ação sugerida é um identificador em português, não uma instrução conversacional.
- Nunca devolva todos os campos como null quando a mensagem descreve uma solicitação. Informações
  claramente escritas pelo cliente devem aparecer no problema, resumo, categoria e destino.

Formato obrigatório:
{
  "intent": string|null,
  "category": string|null,
  "problem": string|null,
  "summary": string|null,
  "entities": object,
  "destination_department": string|null,
  "suggested_action": string|null,
  "priority": "BAIXA"|"NORMAL"|"ALTA"|"URGENTE"
}
Use identificadores técnicos curtos em MAIÚSCULAS_COM_UNDERLINE para intent, category,
destination_department e suggested_action. Preserve tipos JSON nas entidades (número, booleano, texto ou null)."""

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


def parse_context_response(text: str) -> ContextCase:
    return ContextCase.model_validate(_extract_json(text))


def health_check() -> tuple[bool, str]:
    try:
        response = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=1.5)
        response.raise_for_status()
        models = [model.get("name", "") for model in response.json().get("models", [])]
        configured = settings.ollama_model
        exact_or_tagged = any(name == configured or name.split(":")[0] == configured for name in models)
        return exact_or_tagged, "ok" if exact_or_tagged else "model_missing"
    except Exception:
        return False, "unavailable"


def _generate(messages: list[dict[str, str]]) -> str:
    try:
        response = httpx.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": messages,
                "stream": False,
                "format": "json",
                "think": False,
                "keep_alive": "10m",
                "options": {"temperature": 0.1, "num_predict": 450},
            },
            timeout=httpx.Timeout(120.0, connect=3.0),
        )
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        if not content:
            raise ValueError("Ollama retornou conteúdo vazio")
        return content
    except httpx.ConnectError as exc:
        raise ContextServiceError(
            "IA de contextualização indisponível. Inicie o Ollama para habilitar o processamento."
        ) from exc
    except httpx.TimeoutException as exc:
        raise ContextServiceError("A IA de contextualização excedeu o tempo de resposta.") from exc
    except httpx.HTTPStatusError as exc:
        logger.exception("Ollama respondeu com erro HTTP")
        raise ContextServiceError(
            f"O Ollama não conseguiu usar o modelo {settings.ollama_model}. Verifique se ele está instalado."
        ) from exc
    except (ValueError, KeyError) as exc:
        raise ContextServiceError("O Ollama retornou uma resposta vazia ou inesperada.") from exc


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
        logger.warning("JSON inicial do Ollama inválido; solicitando uma única correção")

    correction_messages = messages + [
        {"role": "assistant", "content": first_response},
        {
            "role": "user",
            "content": (
                "A resposta anterior está inválida, incompleta ou semanticamente vazia. Analise de fato "
                "a transcrição recebida. Não devolva problema, resumo ou destino como null quando o cliente "
                "descreveu uma solicitação. Devolva somente um objeto JSON válido com todos os campos."
            ),
        },
    ]
    corrected = _generate(correction_messages)
    try:
        return parse_context_response(corrected)
    except (ValueError, json.JSONDecodeError, ValidationError) as exc:
        logger.exception("Ollama retornou JSON inválido após uma correção")
        raise ContextServiceError(
            "A IA de contexto respondeu em formato inválido. Tente processar novamente."
        ) from exc
