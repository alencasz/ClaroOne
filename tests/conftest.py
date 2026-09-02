from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings
from database import initialize_database


@pytest.fixture(autouse=True)
def isolated_database(tmp_path):
    original = settings.database_path
    object.__setattr__(settings, "database_path", tmp_path / "test.db")
    initialize_database()
    yield
    object.__setattr__(settings, "database_path", original)
