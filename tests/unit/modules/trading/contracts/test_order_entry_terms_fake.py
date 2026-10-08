"""The fake's own helpers, verified (`test_fake_helpers_are_verified.py`): a test
that changes a symbol's status or delists it must be able to rely on them."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_entry_terms import (
    OrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_rules_unavailable_error import (
    SymbolRulesUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
)

_SYMBOL = "BTCUSDT"


def _entry() -> OrderEntryTerms:
    rules = SymbolOrderMetadata(
        symbol=_SYMBOL,
        status="TRADING",
        step_size=Decimal("0.001"),
        tick_size=Decimal("0.01"),
        min_notional=Decimal(5),
        quantity_precision=None,
        price_precision=None,
        fetched_at=datetime(2026, 10, 8, tzinfo=UTC),
    )
    return OrderEntryTerms(
        rules, CommissionRate(_SYMBOL, Decimal("0.001"), Decimal("0.001"))
    )


def test_answer_with_replaces_what_the_symbol_has_from_then_on() -> None:
    terms = FakeOrderEntryTerms(_entry())
    broken = replace(_entry().rules, status="BREAK")

    terms.answer_with(OrderEntryTerms(broken, _entry().commission))

    assert terms.terms_for(_SYMBOL).rules.status == "BREAK"


def test_unlist_makes_the_venue_not_know_the_symbol() -> None:
    terms = FakeOrderEntryTerms(_entry())

    terms.unlist(_SYMBOL)

    with pytest.raises(SymbolRulesUnavailableError):
        terms.terms_for(_SYMBOL)
