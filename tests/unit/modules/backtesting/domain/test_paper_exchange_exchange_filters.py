"""EPIC-027C — a simulated fill obeys the exchange's step size, minimum
notional and tick size (ADR `DECISION_2026-09-26_spot_market_axis.md` D5)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.broker_simulation_config import (
    BrokerSimulationConfig,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exchange_filters import (
    ExchangeFilters,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.paper_exchange import (
    PaperExchange,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal import Signal
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal_action import (
    SignalAction,
)

_T0 = datetime(2026, 1, 1, tzinfo=UTC)
_T1 = _T0 + timedelta(hours=1)
_BTC_SPOT = ExchangeFilters(
    step_size=0.00001, min_quantity=0.00001, min_notional=5.0, tick_size=0.01
)


def _signal(action: SignalAction) -> Signal:
    return Signal(symbol="BTCUSDT", action=action, reason="test", price=0.0, time=_T0)


def _exchange(initial_balance: float = 1_000.0, **config: object) -> PaperExchange:
    return PaperExchange(
        symbol="BTCUSDT",
        initial_balance=initial_balance,
        broker_config=BrokerSimulationConfig(**config),
    )


def _is_multiple_of(quantity: float, step: float) -> bool:
    return Decimal(repr(quantity)) % Decimal(repr(step)) == 0


def test_spot_btcusdt_entry_is_floored_to_the_step_and_keeps_the_rest_as_cash():
    """Business acceptance: 1,000 USDT at 33,333 buys 0.030000300… BTC
    unrounded; the exchange accepts 0.03000 and the 0.01 USDT left over stays
    in cash."""
    exchange = _exchange(
        commission_value=0.0, market_type=MarketType.SPOT, exchange_filters=_BTC_SPOT
    )

    exchange.fill(_signal(SignalAction.BUY), price=33_333.0, time=_T0)
    trade = exchange.fill(_signal(SignalAction.SELL), price=33_333.0, time=_T1)

    assert trade is not None
    assert trade.quantity == pytest.approx(0.03)
    assert _is_multiple_of(trade.quantity, _BTC_SPOT.step_size)
    assert exchange.balance == pytest.approx(1_000.0)
    assert exchange.rejected_entries == 0


def test_the_floored_entry_pays_fees_on_what_it_bought_and_conserves_cash():
    exchange = _exchange(commission_value=0.1, exchange_filters=_BTC_SPOT)

    exchange.fill(_signal(SignalAction.BUY), price=33_333.0, time=_T0)
    trade = exchange.fill(_signal(SignalAction.SELL), price=33_333.0, time=_T1)

    assert trade is not None
    assert _is_multiple_of(trade.quantity, _BTC_SPOT.step_size)
    notional = trade.quantity * 33_333.0
    # 0.1% on the way in (of the capital committed) and on the way out.
    expected_fees = notional * 0.001 / 0.999 + notional * 0.001
    assert trade.fees_paid == pytest.approx(expected_fees)
    assert exchange.balance == pytest.approx(1_000.0 - expected_fees)


def test_a_leveraged_futures_entry_is_floored_and_its_margin_scaled_with_it():
    filters = ExchangeFilters(
        step_size=0.001, min_quantity=0.001, min_notional=100.0, tick_size=0.1
    )
    exchange = _exchange(
        commission_value=0.0, long_leverage=5.0, exchange_filters=filters
    )

    exchange.fill(_signal(SignalAction.BUY), price=33_333.0, time=_T0)

    # 5,000 notional buys 0.150001… unrounded; 0.150 is filled and its margin
    # is 0.150 * 33,333 / 5 = 999.99, leaving 0.01 cash.
    assert exchange.balance == pytest.approx(1_000.0 - 0.15 * 33_333.0 / 5.0)
    assert exchange.equity(mark_price=33_333.0) == pytest.approx(1_000.0)


def test_an_entry_below_the_minimum_notional_is_rejected_counted_and_the_run_continues():
    exchange = _exchange(
        initial_balance=4.0,
        commission_value=0.0,
        market_type=MarketType.SPOT,
        exchange_filters=_BTC_SPOT,
    )

    exchange.fill(_signal(SignalAction.BUY), price=100_000.0, time=_T0)
    exchange.fill(_signal(SignalAction.BUY), price=90_000.0, time=_T1)

    assert exchange.is_in_position is False
    assert exchange.balance == pytest.approx(4.0)
    assert exchange.rejected_entries == 2


def test_an_entry_floored_to_zero_is_rejected():
    filters = ExchangeFilters(
        step_size=1.0, min_quantity=0.0, min_notional=0.0, tick_size=0.01
    )
    exchange = _exchange(commission_value=0.0, exchange_filters=filters)

    exchange.fill(_signal(SignalAction.BUY), price=5_000.0, time=_T0)

    assert exchange.is_in_position is False
    assert exchange.rejected_entries == 1


def test_slippage_uses_the_symbols_real_tick_size():
    filters = ExchangeFilters(
        step_size=0.001, min_quantity=0.0, min_notional=0.0, tick_size=0.5
    )
    exchange = _exchange(
        commission_value=0.0, slippage_ticks=2, exchange_filters=filters
    )

    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T0)
    trade = exchange.fill(_signal(SignalAction.SELL), price=100.0, time=_T1)

    assert trade is not None
    assert trade.entry_price == pytest.approx(101.0)
    assert trade.exit_price == pytest.approx(99.0)


def test_without_filters_the_quantity_is_unrounded_exactly_as_before():
    exchange = _exchange(commission_value=0.0)

    exchange.fill(_signal(SignalAction.BUY), price=33_333.0, time=_T0)
    trade = exchange.fill(_signal(SignalAction.SELL), price=33_333.0, time=_T1)

    assert trade is not None
    assert trade.quantity == 1_000.0 / 33_333.0
    assert exchange.rejected_entries == 0
