"""`FilterPrecisions` (`EPIC-033N`): a venue's cached filters answer a
symbol's tick and step as display precisions; an unknown symbol, or a filter
that restricts nothing, answers `None` and the formatter's magnitude rule
stands. Read through trading's real in-memory cache, the one a venue builds."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.filter_precisions import (
    FilterPrecisions,
    precision_of,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import Precision


def _metadata(symbol: str, tick: str, step: str) -> SymbolOrderMetadata:
    return SymbolOrderMetadata(
        symbol=symbol,
        status="TRADING",
        step_size=Decimal(step),
        tick_size=Decimal(tick),
        min_notional=Decimal(5),
        quantity_precision=None,
        price_precision=None,
        fetched_at=datetime(2026, 10, 6, tzinfo=UTC),
    )


@pytest.fixture
def cache() -> InMemorySymbolOrderMetadataCache:
    filled = InMemorySymbolOrderMetadataCache()
    filled.put(_metadata("BTCUSDT", "0.10", "0.001"))
    return filled


def test_a_cached_symbol_answers_its_tick_and_step(cache):
    precisions = FilterPrecisions(cache)

    assert precisions.tick("BTCUSDT") == Precision(Decimal("0.10"))
    assert precisions.step("BTCUSDT") == Precision(Decimal("0.001"))


def test_a_symbol_not_cached_is_unknown(cache):
    precisions = FilterPrecisions(cache)

    assert precisions.tick("NEWUSDT") is None
    assert precisions.step("NEWUSDT") is None


@pytest.mark.parametrize("size", [Decimal(0), Decimal(-1), Decimal("NaN"), 0.0])
def test_a_size_that_restricts_nothing_says_nothing_of_decimals(size):
    """Binance writes "0" for a filter that does not restrict."""
    assert precision_of(size) is None


def test_a_float_size_is_read_as_the_text_it_prints():
    assert precision_of(0.01) == Precision(Decimal("0.01"))
