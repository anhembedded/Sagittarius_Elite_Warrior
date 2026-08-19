import logging
from datetime import UTC, datetime
from typing import Any

import pytest

from Sagittarius_Elite_Warrior.src.domain.backtesting.exit_reason import ExitReason
from Sagittarius_Elite_Warrior.src.domain.backtesting.paper_exchange import (
    PaperExchange,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.broker_simulation_config import (
    BrokerSimulationConfig,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.commission_type import (
    CommissionType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_sizing import (
    PositionSizing,
    PositionSizingType,
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
    assert trade is not None
    assert trade.metadata == {"qml_score": 92}


# ================= BOT-104: Position Sizing, Pyramiding & Broker Simulator =================


def test_position_sizing_percent_of_equity_allocates_exact_percentage(caplog):
    caplog.set_level(logging.INFO, logger="App.PaperExchange")

    sizing = PositionSizing(type=PositionSizingType.PERCENT_OF_EQUITY, value=20.0)
    exchange = PaperExchange(
        symbol="BTCUSDT",
        initial_balance=10_000.0,
        fee_percent=0.0,
        position_sizing=sizing,
    )

    # Entry 1: 20% of 10,000 = 2,000 USD -> 20.0 BTC at $100
    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)

    assert exchange.balance == pytest.approx(8_000.0)
    assert exchange.position_count == 1
    assert exchange.equity(mark_price=100.0) == pytest.approx(10_000.0)
    assert exchange.equity(mark_price=150.0) == pytest.approx(8_000.0 + 20.0 * 150.0)

    trade = exchange.fill(_signal(SignalAction.SELL), price=150.0, time=_T2)

    assert trade is not None
    assert trade.quantity == pytest.approx(20.0)
    assert trade.pnl == pytest.approx(1_000.0)  # 20 * 150 - 2000 = +1000
    assert trade.pnl_percent == pytest.approx(50.0)  # +50% on deployed capital
    assert exchange.balance == pytest.approx(11_000.0)
    assert any("[paper-exchange] BUY filled" in rec.message for rec in caplog.records)
    assert any("[paper-exchange] SELL filled" in rec.message for rec in caplog.records)


def test_position_sizing_fixed_cash_allocates_exact_dollar_amount():
    sizing = PositionSizing(type=PositionSizingType.FIXED_CASH, value=2_500.0)
    exchange = PaperExchange(
        symbol="BTCUSDT",
        initial_balance=10_000.0,
        fee_percent=0.0,
        position_sizing=sizing,
    )

    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)

    assert exchange.balance == pytest.approx(7_500.0)
    assert exchange.equity(mark_price=100.0) == pytest.approx(10_000.0)

    trade = exchange.fill(_signal(SignalAction.SELL), price=120.0, time=_T2)

    assert trade is not None
    assert trade.quantity == pytest.approx(25.0)  # 2500 / 100
    assert trade.pnl == pytest.approx(500.0)  # 25 * 120 - 2500 = +500
    assert exchange.balance == pytest.approx(10_500.0)


def test_position_sizing_fixed_contracts_allocates_exact_quantity():
    sizing = PositionSizing(type=PositionSizingType.FIXED_CONTRACTS, value=2.0)
    exchange = PaperExchange(
        symbol="BTCUSDT",
        initial_balance=10_000.0,
        fee_percent=0.0,
        position_sizing=sizing,
    )

    exchange.fill(_signal(SignalAction.BUY), price=1_000.0, time=_T1)

    assert exchange.balance == pytest.approx(8_000.0)  # 10000 - 2 * 1000

    trade = exchange.fill(_signal(SignalAction.SELL), price=1_500.0, time=_T2)

    assert trade is not None
    assert trade.quantity == pytest.approx(2.0)
    assert trade.pnl == pytest.approx(1_000.0)  # 2 * 1500 - 2000 = +1000
    assert exchange.balance == pytest.approx(11_000.0)


def test_pyramiding_allows_multiple_entries_up_to_limit():
    broker_cfg = BrokerSimulationConfig(pyramiding=3, commission_value=0.0)
    sizing = PositionSizing(type=PositionSizingType.FIXED_CASH, value=2_000.0)
    exchange = PaperExchange(
        symbol="BTCUSDT",
        initial_balance=10_000.0,
        position_sizing=sizing,
        broker_config=broker_cfg,
    )

    # 1st entry: 2000 / 100 = 20 qty
    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)
    assert exchange.position_count == 1
    assert exchange.balance == pytest.approx(8_000.0)

    # 2nd entry: 2000 / 110 = 18.1818 qty
    t1_plus = datetime(2024, 1, 1, 0, 30, tzinfo=UTC)
    exchange.fill(_signal(SignalAction.BUY), price=110.0, time=t1_plus)
    assert exchange.position_count == 2
    assert exchange.balance == pytest.approx(6_000.0)

    # 3rd entry: 2000 / 120 = 16.6667 qty
    t1_plus2 = datetime(2024, 1, 1, 0, 45, tzinfo=UTC)
    exchange.fill(_signal(SignalAction.BUY), price=120.0, time=t1_plus2)
    assert exchange.position_count == 3
    assert exchange.balance == pytest.approx(4_000.0)

    # 4th entry: Rejected by pyramiding limit (3 max)
    t1_plus3 = datetime(2024, 1, 1, 0, 50, tzinfo=UTC)
    exchange.fill(_signal(SignalAction.BUY), price=125.0, time=t1_plus3)
    assert exchange.position_count == 3
    assert exchange.balance == pytest.approx(4_000.0)

    # Exit: Closes all 3 positions and yields 3 separate trades
    last_trade = exchange.fill(_signal(SignalAction.SELL), price=130.0, time=_T2)

    assert last_trade is not None
    assert len(exchange.trades) == 3
    assert exchange.is_in_position is False

    # Trade 1: 20 * 130 - 2000 = +600 PnL
    assert exchange.trades[0].entry_price == 100.0
    assert exchange.trades[0].pnl == pytest.approx(600.0)

    # Trade 2: (2000/110) * 130 - 2000 = +363.636 PnL
    assert exchange.trades[1].entry_price == 110.0
    assert exchange.trades[1].pnl == pytest.approx((2000.0 / 110.0) * 130.0 - 2000.0)

    # Trade 3: (2000/120) * 130 - 2000 = +166.667 PnL
    assert exchange.trades[2].entry_price == 120.0
    assert exchange.trades[2].pnl == pytest.approx((2000.0 / 120.0) * 130.0 - 2000.0)


def test_slippage_simulation_applies_friction_to_buy_and_sell():
    # 5 ticks * 0.1 tick_size = $0.50 slippage
    broker_cfg = BrokerSimulationConfig(
        slippage_ticks=5,
        tick_size=0.1,
        commission_value=0.0,
    )
    exchange = PaperExchange(
        symbol="BTCUSDT",
        initial_balance=1_000.0,
        broker_config=broker_cfg,
    )

    # BUY at raw price 100.0 -> effective price = 100.50
    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)

    # SELL at raw price 110.0 -> effective price = 109.50
    trade = exchange.fill(_signal(SignalAction.SELL), price=110.0, time=_T2)

    assert trade is not None
    assert trade.entry_price == pytest.approx(100.50)
    assert trade.exit_price == pytest.approx(109.50)
    # Qty = 1000 / 100.50 = 9.950248. Proceeds = 9.950248 * 109.50 = 1089.5522. PnL = +89.5522
    assert trade.pnl == pytest.approx(1000.0 / 100.50 * 109.50 - 1000.0)


def test_commission_cash_per_order_and_cash_per_contract():
    # $5 fixed fee per order
    order_cfg = BrokerSimulationConfig(
        commission_type=CommissionType.CASH_PER_ORDER,
        commission_value=5.0,
    )
    exchange_order = PaperExchange(
        symbol="BTCUSDT",
        initial_balance=1_000.0,
        broker_config=order_cfg,
    )

    exchange_order.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)
    trade_order = exchange_order.fill(_signal(SignalAction.SELL), price=100.0, time=_T2)

    assert trade_order is not None
    assert trade_order.fees_paid == pytest.approx(10.0)  # $5 entry + $5 exit
    assert trade_order.pnl == pytest.approx(-10.0)

    # $1.00 fee per contract (coin)
    contract_cfg = BrokerSimulationConfig(
        commission_type=CommissionType.CASH_PER_CONTRACT,
        commission_value=1.0,
    )
    exchange_contract = PaperExchange(
        symbol="BTCUSDT",
        initial_balance=1_000.0,
        broker_config=contract_cfg,
    )

    # At $100 price + $1/contract fee -> 1000 / (100 + 1) = 9.90099 qty -> fee = 9.90099
    exchange_contract.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)
    trade_contract = exchange_contract.fill(
        _signal(SignalAction.SELL), price=100.0, time=_T2
    )

    assert trade_contract is not None
    assert trade_contract.fees_paid == pytest.approx(trade_contract.quantity * 2.0)


# ================= BOT-041: Stop Loss / Take Profit + Risk Sizing =================


def test_check_intrabar_stops_closes_at_stop_loss_price_when_low_touches_it():
    # Entry 100, SL 1.2% below -> stop price = 98.8. Bar's low reaches 98.5
    # (through the stop) but the fill is AT the stop price, not the low.
    broker_cfg = BrokerSimulationConfig(commission_value=0.0, stop_loss_pct=1.2)
    exchange = PaperExchange(
        symbol="BTCUSDT", initial_balance=1_000.0, broker_config=broker_cfg
    )
    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)
    assert exchange.is_in_position is True

    trades = exchange.check_intrabar_stops(high=101.0, low=98.5, time=_T2)

    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_price == pytest.approx(98.8)
    assert trade.exit_reason is ExitReason.STOP_LOSS
    # qty = 1000/100 = 10; pnl = 10*98.8 - 1000 = -12.0
    assert trade.pnl == pytest.approx(-12.0)
    assert exchange.is_in_position is False


def test_check_intrabar_stops_closes_at_take_profit_price_when_high_touches_it():
    # Entry 100, TP 3.2% above -> target price = 103.2.
    broker_cfg = BrokerSimulationConfig(commission_value=0.0, take_profit_pct=3.2)
    exchange = PaperExchange(
        symbol="BTCUSDT", initial_balance=1_000.0, broker_config=broker_cfg
    )
    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)

    trades = exchange.check_intrabar_stops(high=104.0, low=99.5, time=_T2)

    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_price == pytest.approx(103.2)
    assert trade.exit_reason is ExitReason.TAKE_PROFIT
    # qty = 10; pnl = 10*103.2 - 1000 = +32.0
    assert trade.pnl == pytest.approx(32.0)


def test_check_intrabar_stops_when_bar_touches_both_stop_loss_wins():
    # Conservative rule (BOT-041 §3): SL and TP both inside the bar's range
    # -> assume stop-loss triggered first, since OHLC can't say which the
    # price actually touched first.
    broker_cfg = BrokerSimulationConfig(
        commission_value=0.0, stop_loss_pct=1.2, take_profit_pct=3.2
    )
    exchange = PaperExchange(
        symbol="BTCUSDT", initial_balance=1_000.0, broker_config=broker_cfg
    )
    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)

    trades = exchange.check_intrabar_stops(high=105.0, low=95.0, time=_T2)

    assert len(trades) == 1
    assert trades[0].exit_reason is ExitReason.STOP_LOSS
    assert trades[0].exit_price == pytest.approx(98.8)


def test_check_intrabar_stops_is_a_no_op_when_neither_sl_nor_tp_is_configured():
    """Default BrokerSimulationConfig (BOT-021 behavior) must not change at
    all — every existing caller that never opted into SL/TP keeps working
    exactly as before this feature existed."""
    exchange = PaperExchange(symbol="BTCUSDT", initial_balance=1_000.0)
    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)

    trades = exchange.check_intrabar_stops(high=1_000.0, low=0.01, time=_T2)

    assert trades == []
    assert exchange.is_in_position is True


def test_check_intrabar_stops_is_a_no_op_when_flat():
    exchange = PaperExchange(
        symbol="BTCUSDT",
        initial_balance=1_000.0,
        broker_config=BrokerSimulationConfig(stop_loss_pct=1.0),
    )

    assert exchange.check_intrabar_stops(high=200.0, low=1.0, time=_T1) == []


def test_check_intrabar_stops_leaves_a_position_open_when_range_does_not_reach_either():
    broker_cfg = BrokerSimulationConfig(
        commission_value=0.0, stop_loss_pct=1.2, take_profit_pct=3.2
    )
    exchange = PaperExchange(
        symbol="BTCUSDT", initial_balance=1_000.0, broker_config=broker_cfg
    )
    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)

    trades = exchange.check_intrabar_stops(high=101.0, low=99.0, time=_T2)

    assert trades == []
    assert exchange.is_in_position is True


def test_check_intrabar_stops_only_closes_the_pyramided_position_that_triggered():
    broker_cfg = BrokerSimulationConfig(
        commission_value=0.0, pyramiding=2, stop_loss_pct=1.2
    )
    sizing = PositionSizing(type=PositionSizingType.FIXED_CASH, value=200.0)
    exchange = PaperExchange(
        symbol="BTCUSDT",
        initial_balance=1_000.0,
        position_sizing=sizing,
        broker_config=broker_cfg,
    )
    # Position 1: entry 100 -> stop 98.8
    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)
    # Position 2: entry 200 -> stop 197.6
    exchange.fill(_signal(SignalAction.BUY), price=200.0, time=_T2)
    assert exchange.position_count == 2

    # low=150 is below position 2's stop (197.6) but well above position
    # 1's (98.8) — a single low value implies the price swept continuously
    # down to it, so only the position whose OWN stop sits within [low,
    # high] triggers, not every position on the book.
    trades = exchange.check_intrabar_stops(high=201.0, low=150.0, time=_T2)

    assert len(trades) == 1
    assert trades[0].entry_price == pytest.approx(200.0)
    assert exchange.position_count == 1
    assert exchange.is_in_position is True


def test_stop_loss_price_stays_off_when_only_take_profit_is_configured():
    """Configuring only one of the two thresholds must not accidentally
    switch the other one on."""
    broker_cfg = BrokerSimulationConfig(commission_value=0.0, take_profit_pct=3.2)
    exchange = PaperExchange(
        symbol="BTCUSDT", initial_balance=1_000.0, broker_config=broker_cfg
    )
    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)

    # A catastrophic drop must NOT close the position — no stop configured.
    trades = exchange.check_intrabar_stops(high=101.0, low=1.0, time=_T2)

    assert trades == []
    assert exchange.is_in_position is True


def test_risk_percent_sizing_computes_quantity_from_stop_distance_by_hand():
    # risk 1% of 10,000 equity = 100 USD max loss. SL 2% below entry (100)
    # -> stop distance = 2.0 per unit. quantity = 100 / 2.0 = 50.
    # capital = 50 * 100 = 5,000 (well within the 10,000 balance).
    sizing = PositionSizing(type=PositionSizingType.RISK_PERCENT, value=1.0)
    broker_cfg = BrokerSimulationConfig(commission_value=0.0, stop_loss_pct=2.0)
    exchange = PaperExchange(
        symbol="BTCUSDT",
        initial_balance=10_000.0,
        position_sizing=sizing,
        broker_config=broker_cfg,
    )

    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)

    assert exchange.balance == pytest.approx(10_000.0 - 5_000.0)
    trades = exchange.check_intrabar_stops(high=101.0, low=97.0, time=_T2)
    assert len(trades) == 1
    # Loss realized at the stop must equal the risked 1% of equity by design.
    assert trades[0].pnl == pytest.approx(-100.0)


def test_risk_percent_sizing_rejects_entry_when_stop_loss_pct_is_not_configured():
    sizing = PositionSizing(type=PositionSizingType.RISK_PERCENT, value=1.0)
    exchange = PaperExchange(
        symbol="BTCUSDT", initial_balance=10_000.0, position_sizing=sizing
    )

    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)

    assert exchange.is_in_position is False
    assert exchange.balance == 10_000.0


def test_broker_simulation_config_rejects_out_of_range_stop_loss_pct():
    with pytest.raises(ValueError, match="stop_loss_pct"):
        BrokerSimulationConfig(stop_loss_pct=100.0)
    with pytest.raises(ValueError, match="stop_loss_pct"):
        BrokerSimulationConfig(stop_loss_pct=0.0)


def test_broker_simulation_config_rejects_non_positive_take_profit_pct():
    with pytest.raises(ValueError, match="take_profit_pct"):
        BrokerSimulationConfig(take_profit_pct=0.0)


def test_position_sizing_rejects_out_of_range_risk_percent():
    with pytest.raises(ValueError, match="Risk percent"):
        PositionSizing(type=PositionSizingType.RISK_PERCENT, value=150.0)


# ================= BOT-050: Short-Selling =================


def test_short_then_cover_computes_quantity_fees_and_pnl_by_hand():
    # Hand-computed, mirrors test_buy_then_sell_... exactly but short wins
    # when price DROPS: entry_fee = 1000*1% = 10; capital = 990 (margin);
    # quantity = 990/100 = 9.9. Cover at 90: notional = 9.9*90 = 891;
    # exit_fee = 891*1% = 8.91; pnl = (100-90)*9.9 - 10 - 8.91 = 80.09;
    # balance = capital_deployed(1000) + pnl(80.09) = 1080.09.
    exchange = PaperExchange(symbol="BTCUSDT", initial_balance=1000.0, fee_percent=1.0)

    opened = exchange.fill(_signal(SignalAction.SHORT), price=100.0, time=_T1)

    assert opened is None
    assert exchange.is_in_position is True
    assert exchange.balance == 0.0

    trade = exchange.fill(_signal(SignalAction.COVER), price=90.0, time=_T2)

    assert trade is not None
    assert exchange.is_in_position is False
    assert trade.side is PositionSide.SHORT
    assert trade.entry_price == 100.0
    assert trade.exit_price == 90.0
    assert trade.quantity == pytest.approx(9.9)
    assert trade.pnl == pytest.approx(80.09)
    assert trade.fees_paid == pytest.approx(10.0 + 8.91)
    assert exchange.balance == pytest.approx(1080.09)


def test_short_loses_when_price_rises_by_hand():
    # Same setup, opposite direction: cover at 110 (price rose against the
    # short). notional = 9.9*110 = 1089; exit_fee = 10.89;
    # pnl = (100-110)*9.9 - 10 - 10.89 = -119.89;
    # balance = 1000 + (-119.89) = 880.11.
    exchange = PaperExchange(symbol="BTCUSDT", initial_balance=1000.0, fee_percent=1.0)
    exchange.fill(_signal(SignalAction.SHORT), price=100.0, time=_T1)

    trade = exchange.fill(_signal(SignalAction.COVER), price=110.0, time=_T2)

    assert trade.pnl == pytest.approx(-119.89)
    assert exchange.balance == pytest.approx(880.11)


def test_cover_with_no_open_short_position_is_a_no_op():
    exchange = PaperExchange(symbol="BTCUSDT", initial_balance=1000.0, fee_percent=0.0)

    trade = exchange.fill(_signal(SignalAction.COVER), price=100.0, time=_T1)

    assert trade is None
    assert exchange.balance == 1000.0
    assert exchange.trades == []


def test_short_while_already_long_is_rejected_not_mixed():
    """BOT-050 §3: PaperExchange never infers a reversal — an opposite-side
    entry while one side is open is rejected outright, not silently mixed
    into the position list. Deliberately generous pyramiding (5) AND small
    (20%) sizing so this test can't pass by accident: with the default
    pyramiding=1 and/or default 100%-of-equity sizing, the 2nd entry would
    already be blocked for a completely different reason (limit reached, or
    zero balance left) even with the opposite-side guard fully disabled —
    both were verified as real false-pass traps while writing this test."""
    broker_cfg = BrokerSimulationConfig(commission_value=0.0, pyramiding=5)
    sizing = PositionSizing(type=PositionSizingType.PERCENT_OF_EQUITY, value=20.0)
    exchange = PaperExchange(
        symbol="BTCUSDT",
        initial_balance=1000.0,
        position_sizing=sizing,
        broker_config=broker_cfg,
    )
    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)
    assert exchange.position_count == 1
    assert exchange.balance > 0  # plenty of balance left for a 2nd entry

    exchange.fill(_signal(SignalAction.SHORT), price=100.0, time=_T2)

    assert exchange.position_count == 1
    trade = exchange.fill(_signal(SignalAction.SELL), price=110.0, time=_T2)
    assert trade is not None
    assert trade.side is PositionSide.LONG


def test_buy_while_already_short_is_rejected_not_mixed():
    broker_cfg = BrokerSimulationConfig(commission_value=0.0, pyramiding=5)
    sizing = PositionSizing(type=PositionSizingType.PERCENT_OF_EQUITY, value=20.0)
    exchange = PaperExchange(
        symbol="BTCUSDT",
        initial_balance=1000.0,
        position_sizing=sizing,
        broker_config=broker_cfg,
    )
    exchange.fill(_signal(SignalAction.SHORT), price=100.0, time=_T1)
    assert exchange.position_count == 1
    assert exchange.balance > 0

    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T2)

    assert exchange.position_count == 1
    trade = exchange.fill(_signal(SignalAction.COVER), price=90.0, time=_T2)
    assert trade is not None
    assert trade.side is PositionSide.SHORT


def test_equity_marks_an_open_short_position_to_market_correctly():
    exchange = PaperExchange(symbol="BTCUSDT", initial_balance=1000.0, fee_percent=0.0)
    exchange.fill(_signal(SignalAction.SHORT), price=100.0, time=_T1)
    # qty = 1000/100 = 10 (all-in, no fee); capital_deployed = 1000, balance = 0

    assert exchange.equity(mark_price=100.0) == pytest.approx(1000.0)
    # Price drops 10 -> short is up 10*10 = 100
    assert exchange.equity(mark_price=90.0) == pytest.approx(1100.0)
    # Price rises 10 -> short is down 10*10 = 100
    assert exchange.equity(mark_price=110.0) == pytest.approx(900.0)


def test_force_close_realizes_a_still_open_short_position_as_a_trade():
    exchange = PaperExchange(symbol="BTCUSDT", initial_balance=1000.0, fee_percent=0.0)
    exchange.fill(_signal(SignalAction.SHORT), price=100.0, time=_T1)

    trade = exchange.force_close(price=90.0, time=_T2)

    assert trade is not None
    assert trade.exit_reason is ExitReason.END_OF_BACKTEST
    assert trade.pnl == pytest.approx(100.0)  # 10 qty * $10 drop
    assert exchange.balance == pytest.approx(1100.0)


def test_short_slippage_reduces_entry_price_and_increases_cover_price():
    """Mirrors test_slippage_simulation_applies_friction_to_buy_and_sell —
    a SHORT entry sells (slippage makes you receive less), a COVER buys
    back (slippage makes you pay more): the opposite sign from LONG at
    both ends."""
    broker_cfg = BrokerSimulationConfig(
        slippage_ticks=5, tick_size=0.1, commission_value=0.0
    )
    exchange = PaperExchange(
        symbol="BTCUSDT", initial_balance=1_000.0, broker_config=broker_cfg
    )

    exchange.fill(_signal(SignalAction.SHORT), price=100.0, time=_T1)
    trade = exchange.fill(_signal(SignalAction.COVER), price=90.0, time=_T2)

    assert trade is not None
    assert trade.entry_price == pytest.approx(99.50)
    assert trade.exit_price == pytest.approx(90.50)


def test_short_trade_records_side_short_and_long_trade_records_side_long():
    exchange = PaperExchange(symbol="BTCUSDT", initial_balance=1000.0, fee_percent=0.0)
    exchange.fill(_signal(SignalAction.SHORT), price=100.0, time=_T1)
    short_trade = exchange.fill(_signal(SignalAction.COVER), price=90.0, time=_T2)
    assert short_trade.side is PositionSide.SHORT

    exchange2 = PaperExchange(symbol="BTCUSDT", initial_balance=1000.0, fee_percent=0.0)
    exchange2.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)
    long_trade = exchange2.fill(_signal(SignalAction.SELL), price=110.0, time=_T2)
    assert long_trade.side is PositionSide.LONG


def test_short_stop_loss_sits_above_entry_and_closes_on_high():
    broker_cfg = BrokerSimulationConfig(commission_value=0.0, stop_loss_pct=1.2)
    exchange = PaperExchange(
        symbol="BTCUSDT", initial_balance=1_000.0, broker_config=broker_cfg
    )
    exchange.fill(_signal(SignalAction.SHORT), price=100.0, time=_T1)

    # SL 1.2% ABOVE entry (100) = 101.2 — a low bar range must NOT trigger it.
    assert exchange.check_intrabar_stops(high=101.0, low=98.0, time=_T2) == []
    trades = exchange.check_intrabar_stops(high=101.5, low=99.0, time=_T2)

    assert len(trades) == 1
    assert trades[0].exit_reason is ExitReason.STOP_LOSS
    assert trades[0].exit_price == pytest.approx(101.2)


def test_short_take_profit_sits_below_entry_and_closes_on_low():
    broker_cfg = BrokerSimulationConfig(commission_value=0.0, take_profit_pct=3.2)
    exchange = PaperExchange(
        symbol="BTCUSDT", initial_balance=1_000.0, broker_config=broker_cfg
    )
    exchange.fill(_signal(SignalAction.SHORT), price=100.0, time=_T1)

    # TP 3.2% BELOW entry (100) = 96.8.
    trades = exchange.check_intrabar_stops(high=100.5, low=96.0, time=_T2)

    assert len(trades) == 1
    assert trades[0].exit_reason is ExitReason.TAKE_PROFIT
    assert trades[0].exit_price == pytest.approx(96.8)


def test_check_intrabar_stops_for_short_when_bar_touches_both_stop_loss_wins():
    broker_cfg = BrokerSimulationConfig(
        commission_value=0.0, stop_loss_pct=1.2, take_profit_pct=3.2
    )
    exchange = PaperExchange(
        symbol="BTCUSDT", initial_balance=1_000.0, broker_config=broker_cfg
    )
    exchange.fill(_signal(SignalAction.SHORT), price=100.0, time=_T1)

    # SL=101.2 above, TP=96.8 below — this bar's range reaches both.
    trades = exchange.check_intrabar_stops(high=105.0, low=95.0, time=_T2)

    assert len(trades) == 1
    assert trades[0].exit_reason is ExitReason.STOP_LOSS
    assert trades[0].exit_price == pytest.approx(101.2)


def test_current_side_is_none_when_flat():
    exchange = PaperExchange(symbol="BTCUSDT", initial_balance=1000.0, fee_percent=0.0)

    assert exchange.current_side is None


def test_current_side_reports_long_or_short_while_open():
    exchange = PaperExchange(symbol="BTCUSDT", initial_balance=1000.0, fee_percent=0.0)
    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)
    assert exchange.current_side is PositionSide.LONG
    exchange.fill(_signal(SignalAction.SELL), price=110.0, time=_T2)
    assert exchange.current_side is None

    exchange.fill(_signal(SignalAction.SHORT), price=100.0, time=_T1)
    assert exchange.current_side is PositionSide.SHORT
    exchange.fill(_signal(SignalAction.COVER), price=90.0, time=_T2)
    assert exchange.current_side is None


def test_risk_percent_sizing_works_symmetrically_for_short_by_hand():
    # risk 1% of 10,000 = 100 USD max loss. SL 2% above entry (100) ->
    # stop distance = 2.0. quantity = 100/2.0 = 50. capital = 5,000.
    sizing = PositionSizing(type=PositionSizingType.RISK_PERCENT, value=1.0)
    broker_cfg = BrokerSimulationConfig(commission_value=0.0, stop_loss_pct=2.0)
    exchange = PaperExchange(
        symbol="BTCUSDT",
        initial_balance=10_000.0,
        position_sizing=sizing,
        broker_config=broker_cfg,
    )

    exchange.fill(_signal(SignalAction.SHORT), price=100.0, time=_T1)

    assert exchange.balance == pytest.approx(10_000.0 - 5_000.0)
    trades = exchange.check_intrabar_stops(high=103.0, low=99.0, time=_T2)
    assert len(trades) == 1
    assert trades[0].pnl == pytest.approx(-100.0)
