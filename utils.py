from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from config import settings


TZ = ZoneInfo(settings.timezone)


def now_local() -> datetime:
    return datetime.now(TZ)


def normalize_cpf(cpf: str) -> str:
    digits = re.sub(r"\D", "", cpf or "")
    if len(digits) != 11:
        raise ValueError("Informe um CPF com 11 dígitos.")
    return digits


def format_cpf(cpf: str) -> str:
    digits = normalize_cpf(cpf)
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"


def mask_cpf(cpf: str) -> str:
    digits = normalize_cpf(cpf)
    return f"***.{digits[3:6]}.{digits[6:9]}-**"


def format_datetime(value: str | datetime | None) -> str:
    if not value:
        return "—"
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=TZ)
    return parsed.astimezone(TZ).strftime("%d/%m/%Y às %H:%M")


def format_time(value: str | datetime | None) -> str:
    if not value:
        return "—"
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=TZ)
    return parsed.astimezone(TZ).strftime("%H:%M")


def friendly_label(value: str | None) -> str:
    if not value:
        return "Não identificado"
    return value.replace("_", " ").strip().title()


def format_currency(value: Any) -> str:
    try:
        number = Decimal(str(value))
    except Exception:
        return str(value)
    formatted = f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def slugify_filename_suffix(filename: str) -> str:
    name = unicodedata.normalize("NFKD", filename)
    return re.sub(r"[^a-z0-9.]", "", name.lower())
