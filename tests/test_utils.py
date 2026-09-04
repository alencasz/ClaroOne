from __future__ import annotations

import pytest

from utils import format_cpf, format_currency, friendly_label, mask_cpf, normalize_cpf


def test_normalize_formatted_and_plain_cpf():
    assert normalize_cpf("123.456.789-00") == "12345678900"
    assert normalize_cpf("12345678900") == "12345678900"


def test_reject_invalid_cpf_length():
    with pytest.raises(ValueError):
        normalize_cpf("123")


def test_format_and_mask_cpf():
    assert format_cpf("12345678900") == "123.456.789-00"
    assert mask_cpf("12345678900") == "***.456.789-**"


def test_brazilian_currency():
    assert format_currency(35) == "R$ 35,00"


def test_taxonomy_has_friendly_labels():
    assert friendly_label("OUTROS") == "Atendimento geral"
    assert friendly_label("SUPORTE_TELEFONIA") == "Suporte de telefonia"
