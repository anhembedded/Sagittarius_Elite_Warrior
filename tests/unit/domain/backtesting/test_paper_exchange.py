"""Tests for PaperExchange (BOT-021)."""

from datetime import UTC, datetime
from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.domain.backtesting.exit_reason import ExitReason
from Sagittarius_Elite_Warrior.src.domain.backtesting.paper_exchange import (
    PaperExchange,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)

_T1 = datetime(2024, 1, 1, tzinfo=UTC)
_T2 = datetime(2024, 1, 1, 1, 0, tzinfo=UTC)


def _signal(
    action: SignalAction, reason: str = "test", metadata: dict[str, Any] | None = None
) -> Signal:
    return Signal(
        symbol="BTCUSDT",
        action=action,
        reason=reason,
        price=0.0,
        time=_T1,
        metadata=metadata or {},
    )


def test_constructor_rejects_non_positive_initial_balance():
    with pytest.raises(ValueError, match="initial_balance"):
        PaperExchange(symbol="BTCUSDT", initial_balance=0.0)


def test_constructor_rejects_negative_fee_percent():
    with pytest.raises(ValueError, match="fee_percent"):
        PaperExchange(symbol="BTCUSDT", initial_balance=1000.0, fee_percent=-1.0)


def test_equity_is_the_cash_balance_when_flat():
    exchange = PaperExchange(symbol="BTCUSDT", initial_balance=1000.0, fee_percent=1.0)

    assert exchange.equity(mark_price=999.0) == 1000.0
    assert exchange.is_in_position is False


def test_buy_then_sell_computes_quantity_fees_and_pnl_by_hand():
    # Arrange — hand-computed: entry_fee = 1000*1% = 10; capital = 990;
    # quantity = 990/100 = 9.9. Exit: proceeds = 9.9*110 = 1089;
    # exit_fee = 1089*1% = 10.89; balance = 1078.11;
    # pnl = 1078.11 - 1000 = 78.11; pnl_percent = 7.811%.
    exchange = PaperExchange(symbol="BTCUSDT", initial_balance=1000.0, fee_percent=1.0)

    opened = exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)

    assert opened is None
    assert exchange.is_in_position is True
    assert exchange.balance == 0.0
    assert exchange.equity(mark_price=110.0) == pytest.approx(9.9 * 110.0)

    trade = exchange.fill(_signal(SignalAction.SELL), price=110.0, time=_T2)

    assert trade is not None
    assert exchange.is_in_position is False
    assert trade.symbol == "BTCUSDT"
    assert trade.entry_time == _T1
    assert trade.entry_price == 100.0
    assert trade.exit_time == _T2
    assert trade.exit_price == 110.0
    assert trade.quantity == pytest.approx(9.9)
    assert trade.pnl == pytest.approx(78.11)
    assert trade.pnl_percent == pytest.approx(7.811)
    assert trade.fees_paid == pytest.approx(10.0 + 10.89)
    assert exchange.balance == pytest.approx(1078.11)
    assert exchange.trades == [trade]


def test_buy_while_already_in_position_is_a_no_op():
    exchange = PaperExchange(symbol="BTCUSDT", initial_balance=1000.0, fee_percent=0.0)
    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)
    quantity_after_first_buy = exchange.equity(mark_price=100.0) / 100.0

    exchange.fill(_signal(SignalAction.BUY), price=50.0, time=_T2)

    assert exchange.equity(mark_price=100.0) / 100.0 == pytest.approx(
        quantity_after_first_buy
    )
    assert exchange.trades == []


def test_sell_with_no_open_position_is_a_no_op():
    exchange = PaperExchange(symbol="BTCUSDT", initial_balance=1000.0, fee_percent=0.0)

    trade = exchange.fill(_signal(SignalAction.SELL), price=100.0, time=_T1)

    assert trade is None
    assert exchange.balance == 1000.0
    assert exchange.trades == []


def test_force_close_with_no_open_position_is_a_no_op():
    exchange = PaperExchange(symbol="BTCUSDT", initial_balance=1000.0, fee_percent=0.0)

    assert exchange.force_close(price=100.0, time=_T1) is None
    assert exchange.trades == []


def test_force_close_realizes_a_still_open_position_as_a_trade():
    exchange = PaperExchange(symbol="BTCUSDT", initial_balance=1000.0, fee_percent=0.0)
    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)

    trade = exchange.force_close(price=120.0, time=_T2)

    assert trade is not None
    assert exchange.is_in_position is False
    assert trade.exit_price == 120.0
    assert trade.pnl == pytest.approx(200.0)  # 1000 -> 10 qty -> 1200 - 1000
    assert exchange.trades == [trade]


def test_trades_returns_a_copy():
    exchange = PaperExchange(symbol="BTCUSDT", initial_balance=1000.0, fee_percent=0.0)
    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)
    exchange.fill(_signal(SignalAction.SELL), price=110.0, time=_T2)

    exchange.trades.append("injected")

    assert "injected" not in exchange.trades


# ================= BOT-045: Trade Journal Detail =================


def test_a_trade_closed_by_a_sell_signal_records_strategy_signal_as_exit_reason():
    exchange = PaperExchange(symbol="BTCUSDT", initial_balance=1000.0, fee_percent=0.0)
    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)

    trade = exchange.fill(_signal(SignalAction.SELL), price=110.0, time=_T2)

    assert trade.exit_reason is ExitReason.STRATEGY_SIGNAL


def test_a_trade_closed_by_force_close_records_end_of_backtest_as_exit_reason():
    exchange = PaperExchange(symbol="BTCUSDT", initial_balance=1000.0, fee_percent=0.0)
    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)

    trade = exchange.force_close(price=110.0, time=_T2)

    assert trade.exit_reason is ExitReason.END_OF_BACKTEST


def test_entry_reason_comes_from_the_opening_signal_not_the_closing_one():
    exchange = PaperExchange(symbol="BTCUSDT", initial_balance=1000.0, fee_percent=0.0)
    exchange.fill(
        _signal(SignalAction.BUY, reason="EMA Crossover 3/5 crossed above"),
        price=100.0,
        time=_T1,
    )

    trade = exchange.fill(
        _signal(SignalAction.SELL, reason="EMA Crossover 3/5 crossed below"),
        price=110.0,
        time=_T2,
    )

    assert trade.entry_reason == "EMA Crossover 3/5 crossed above"


def test_metadata_from_the_opening_signal_carries_through_to_the_trade():
    exchange = PaperExchange(symbol="BTCUSDT", initial_balance=1000.0, fee_percent=0.0)
    exchange.fill(
        _signal(SignalAction.BUY, metadata={"qml_score": 92}), price=100.0, time=_T1
    )

    trade = exchange.fill(_signal(SignalAction.SELL), price=110.0, time=_T2)

    assert trade.metadata == {"qml_score": 92}
