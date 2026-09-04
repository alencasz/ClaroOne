from __future__ import annotations

from pathlib import Path
import re

from database import DEMO_CUSTOMERS, get_connection, initialize_database
from services import cce_service
from utils import format_cpf


ROOT = Path(__file__).resolve().parents[1]


def test_seed_has_at_least_twelve_unique_normalized_customers():
    cpfs = [cpf for cpf, _name in DEMO_CUSTOMERS]
    assert len(DEMO_CUSTOMERS) >= 12
    assert len(cpfs) == len(set(cpfs))
    assert all(len(cpf) == 11 and cpf.isdigit() for cpf in cpfs)
    assert dict(DEMO_CUSTOMERS)["12345678900"] == "Lucas de Alencar"


def test_seed_is_idempotent():
    initialize_database()
    initialize_database()
    with get_connection() as connection:
        rows = connection.execute("SELECT cpf, name FROM customers").fetchall()
    assert len(rows) == len(DEMO_CUSTOMERS)
    assert len({row["cpf"] for row in rows}) == len(rows)


def test_reset_recreates_all_seed_customers_without_duplication():
    cce_service.create_session("12345678900", "FATURAMENTO")
    cce_service.reset_demo()
    with get_connection() as connection:
        customers = connection.execute("SELECT cpf, name FROM customers").fetchall()
        session_count = connection.execute("SELECT COUNT(*) FROM cce_sessions").fetchone()[0]
        event_count = connection.execute("SELECT COUNT(*) FROM cce_events").fetchone()[0]
    assert {(row["cpf"], row["name"]) for row in customers} == set(DEMO_CUSTOMERS)
    assert session_count == 0
    assert event_count == 0


def test_quick_guide_lists_exact_seed_customers():
    guide = (ROOT / "LEIA_PRIMEIRO.txt").read_text(encoding="utf-8")
    for cpf, name in DEMO_CUSTOMERS:
        assert f"{format_cpf(cpf)} - {name}" in guide
    listed_cpfs = re.findall(r"^\d{3}\.\d{3}\.\d{3}-\d{2} - ", guide, re.MULTILINE)
    assert len(listed_cpfs) == len(DEMO_CUSTOMERS)


def test_technical_documentation_has_required_sections():
    documentation = (ROOT / "DOCUMENTACAO_TECNICA.txt").read_text(encoding="utf-8")
    for section in range(1, 17):
        assert f"{section}. " in documentation
    assert "OUTROS -> OUTROS" in documentation
    assert "whisper-large-v3-turbo" in documentation
    assert "openai/gpt-oss-20b" in documentation
