from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from config import settings


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS customers (
    cpf TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cce_sessions (
    id TEXT PRIMARY KEY,
    protocol TEXT NOT NULL UNIQUE,
    cpf TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    status TEXT NOT NULL,
    channel_origin TEXT NOT NULL,
    current_channel TEXT NOT NULL,
    initial_department TEXT NOT NULL,
    audio_path TEXT,
    transcript TEXT,
    intent TEXT,
    category TEXT,
    problem TEXT,
    summary TEXT,
    structured_context TEXT NOT NULL DEFAULT '{}',
    destination_department TEXT,
    suggested_action TEXT,
    priority TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    FOREIGN KEY (cpf) REFERENCES customers(cpf)
);

CREATE INDEX IF NOT EXISTS idx_sessions_cpf_updated
ON cce_sessions(cpf, updated_at DESC);

CREATE TABLE IF NOT EXISTS cce_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    event_type TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES cce_sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_events_session_created
ON cce_events(session_id, created_at ASC);
"""


DEMO_CUSTOMERS = (
    ("12345678900", "Lucas de Alencar"),
    ("98765432100", "Marina Costa"),
    ("11122233344", "Rafael Nogueira"),
    ("22233344455", "Ana Beatriz Moura"),
    ("33344455566", "Bruno Tavares Lima"),
    ("44455566677", "Camila Ribeiro Nunes"),
    ("55566677788", "Diego Martins Rocha"),
    ("66677788899", "Elisa Fernandes Prado"),
    ("77788899900", "Felipe Andrade Melo"),
    ("88899900011", "Gabriela Souza Pires"),
    ("99900011122", "Henrique Barros Dias"),
    ("10120230344", "Isabela Monteiro Luz"),
)


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(settings.database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    connection = connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def seed_customers(connection: sqlite3.Connection) -> None:
    connection.executemany(
        "INSERT OR IGNORE INTO customers (cpf, name) VALUES (?, ?)", DEMO_CUSTOMERS
    )


def initialize_database() -> None:
    with get_connection() as connection:
        connection.executescript(SCHEMA)
        seed_customers(connection)


def database_health() -> bool:
    try:
        with get_connection() as connection:
            connection.execute("SELECT 1").fetchone()
        return True
    except sqlite3.Error:
        return False
