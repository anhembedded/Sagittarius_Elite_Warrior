"""`EPIC-028J` — `FakeAccountActivity`'s helpers answer what they say, so a
desk test that leans on them cannot pass against a fake that ignores them
(`BUG-120`, `test_fake_helpers_are_verified.py`)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_page import (
    HISTORY_PAGE_SIZE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_request import (
    HistoryRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_activity import (
    FakeAccountActivity,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from ..ui.desk.account_tabs_fixtures import order, order_record, trade_record

_SINCE = datetime(2026, 9, 24, tzinfo=UTC)


def test_an_unseeded_account_has_no_summary_and_nothing_open() -> None:
    fake = FakeAccountActivity()

    assert fake.summary() is None
    assert fake.open_orders() == ()


def test_the_seeded_summary_and_open_orders_are_answered() -> None:
    fake = FakeAccountActivity()
    summary = AccountSummary(
        venue=TradingVenue.SPOT_TESTNET, available_balance=Decimal(5), equity=None
    )
    fake.holding_summary(summary)
    fake.holding_open_orders([order()])

    assert fake.summary() is summary
    assert [o.client_order_id for o in fake.open_orders()] == ["SEW-btc"]


def test_a_history_is_cut_into_pages_and_filtered_by_symbol() -> None:
    fake = FakeAccountActivity()
    fake.holding_history(
        [order_record("BTCUSDT")] * (HISTORY_PAGE_SIZE + 1) + [order_record("ETHUSDT")],
        [trade_record("ETHUSDT")],
        scanned_symbols=("BTCUSDT", "ETHUSDT"),
        notices=("a gap",),
    )

    every = fake.order_history(HistoryRequest(symbol=None, since=_SINCE, page=1))
    btc = fake.order_history(HistoryRequest(symbol="BTCUSDT", since=_SINCE))
    trades = fake.trade_history(HistoryRequest(symbol="BTCUSDT", since=_SINCE))

    assert (len(every.rows), every.total_rows) == (2, HISTORY_PAGE_SIZE + 2)
    assert every.scanned_symbols == ("BTCUSDT", "ETHUSDT")
    assert every.notices == ("a gap",)
    assert (btc.total_rows, btc.scanned_symbols) == (
        HISTORY_PAGE_SIZE + 1,
        ("BTCUSDT",),
    )
    assert trades.rows == ()
    assert [r.page for r in fake.order_requests] == [1, 0]
    assert len(fake.trade_requests) == 1


def test_a_seeded_error_is_raised_by_both_histories() -> None:
    fake = FakeAccountActivity()
    fake.history_raises(AccountHistoryUnavailableError("down"))

    for read in (fake.order_history, fake.trade_history):
        with pytest.raises(AccountHistoryUnavailableError):
            read(HistoryRequest(symbol=None, since=_SINCE))
