"""Integration-tier fixtures: a test here never reaches a real host (`BUG-182`)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_range_coverage import (
    FakeRangeCoverage,
    fully_covered,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_symbol_metadata_provider import (
    FakeSymbolMetadataProvider,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.mock_klines import (
    MOCK_KLINE_COUNT,
    SEEDED_SYMBOLS,
)
from Sagittarius_Elite_Warrior.tests.unit import network_block


@pytest.fixture(autouse=True)
def _block_non_loopback_connections(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """`BUG-182` — no integration test reaches a real host, and it fails when one
    tried, wherever the refusal was caught.

    The booted app keeps every real adapter behind a port the test does not
    substitute, and nothing said so when one of them went to binance.com: its
    worker caught the error, logged a 451 warning and the suite stayed green.
    So the refusal is recorded, not only raised. A loopback fake server
    (`test_trade_mode_against_fake_server.py`) is still allowed.
    """
    refused = network_block.install(monkeypatch)
    yield
    assert not refused, f"the test tried to reach {sorted(set(refused))}"


#: The window the scripted coverage answer reports as complete. Any two
#: instants in the right order would do — a screen renders them, it does not
#: compute with them, and `mock_klines.build_mock_klines` decides what is
#: actually stored.
_COVERED_FROM = datetime(2024, 1, 1, tzinfo=UTC)
_COVERED_TO = datetime(2024, 1, 2, tzinfo=UTC)


@pytest.fixture
def range_coverage():
    """The coverage probe every Backtest integration test reads.

    `EPIC-025` PR 1.2 — scripted to "fully covered" for the shard the seeded
    history fills, because that is the state these tests were written
    against: the mocked dispatcher used to answer exactly this.
    """
    fake = FakeRangeCoverage()
    covered = fully_covered(_COVERED_FROM, _COVERED_TO, candles=MOCK_KLINE_COUNT)
    for symbol in SEEDED_SYMBOLS:
        for interval in (TimeFrame.ONE_MINUTE, TimeFrame.ONE_SECOND):
            fake.answer_with(covered, symbol=symbol, interval=interval)
    return fake


@pytest.fixture
def symbol_metadata():
    """The exchange-filters read every Watchlist integration test goes through:
    a catalog that lists nothing, so prices round by magnitude."""
    return FakeSymbolMetadataProvider()
