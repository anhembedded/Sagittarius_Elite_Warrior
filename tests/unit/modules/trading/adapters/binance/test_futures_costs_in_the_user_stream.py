"""`EPIC-039G` — what a Futures account is charged reaches the app: the commission and the
realized profit on a fill (`ORDER_TRADE_UPDATE` `n`/`N`/`rp`) and the funding fee (an
`ACCOUNT_UPDATE` whose reason `m` is `FUNDING_FEE`).

@details Payloads are Binance's documented shapes (`llms-full.txt`, read 2026-10-13); no live stream
verified them."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_order_updates import (
    FuturesOrderUpdates,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_user_data_stream import (
    FuturesUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.user_data_event_parser import (
    account_update_funding,
    fill_commission,
    fill_realized_profit,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.funding_charged_event import (
    FundingChargedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.emitter_builder import (
    venue_emitter,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus


def _fill(**o: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "s": "BTCUSDT",
        "c": "SEW-a91f4c72e0b8",
        "S": "SELL",
        "o": "LIMIT",
        "q": "0.002",
        "p": "65100",
        "X": "FILLED",
        "x": "TRADE",
        "i": 1,
        "L": "65100",
        "l": "0.002",
        "n": "0.02604",
        "N": "USDT",
        "rp": "0.5",
        "T": 1759320200000,
    }
    body.update(o)
    return {"e": "ORDER_TRADE_UPDATE", "o": body}


def _funding(amount: str, **overrides: Any) -> dict[str, Any]:
    a: dict[str, Any] = {
        "m": "FUNDING_FEE",
        "S": "BTCUSDT",
        "B": [{"a": "USDT", "wb": "999.5", "cw": "999.5", "bc": amount}],
        "P": [],
    }
    a.update(overrides)
    return {"e": "ACCOUNT_UPDATE", "E": 1759320200000, "a": a}


def test_a_futures_fill_carries_its_commission_in_the_quote_asset() -> None:
    assert fill_commission(_fill()) == (Decimal("0.02604"), "USDT")


def test_a_fill_without_a_commission_field_has_no_fee_not_a_zero_fee() -> None:
    """Binance does not push `n` when there is no commission (the page's note)."""
    payload = _fill()
    del payload["o"]["n"], payload["o"]["N"]

    assert fill_commission(payload) is None


def test_the_realized_profit_of_a_fill_is_read_and_absent_is_unknown() -> None:
    assert fill_realized_profit(_fill()) == Decimal("0.5")
    payload = _fill()
    del payload["o"]["rp"]
    assert fill_realized_profit(payload) is None


def test_the_stream_reports_the_commission_and_realized_profit_on_the_fill_event() -> (
    None
):
    bus = MemoryEventBus()
    seen: list[OrderFilledEvent] = []
    bus.on(OrderFilledEvent, seen.append)
    updates = FuturesOrderUpdates(venue_emitter(bus, TradingVenue.FUTURES_TESTNET))

    updates.on_order_trade_update(_fill())

    assert (seen[0].fee_amount, seen[0].fee_asset) == (Decimal("0.02604"), "USDT")
    assert seen[0].realized_profit == Decimal("0.5")


def test_a_funding_fee_is_the_balance_change_of_a_funding_account_update() -> None:
    charge = account_update_funding(_funding("-0.0123"))

    assert charge is not None
    assert (charge.symbol, charge.amount) == ("BTCUSDT", Decimal("-0.0123"))


def test_an_account_update_for_another_reason_is_not_funding() -> None:
    assert account_update_funding(_funding("-1", m="ORDER")) is None


def test_a_funding_update_without_a_symbol_is_unattributed_not_guessed() -> None:
    payload = _funding("-1")
    del payload["a"]["S"]

    assert account_update_funding(payload) is None


def test_a_funding_update_names_its_symbol_by_its_one_position_when_s_is_absent() -> (
    None
):
    payload = _funding("0.5", P=[{"s": "ETHUSDT", "pa": "1", "up": "0"}])
    del payload["a"]["S"]

    charge = account_update_funding(payload)

    assert charge is not None and charge.symbol == "ETHUSDT"


async def test_the_stream_publishes_a_funding_charge_once_per_account_update() -> None:
    bus = MemoryEventBus()
    seen: list[FundingChargedEvent] = []
    bus.on(FundingChargedEvent, seen.append)
    stream = FuturesUserDataStream(
        venue_emitter(bus, TradingVenue.FUTURES_TESTNET),
        Mock(),
        Mock(),
        Mock(),
        TradingSessionState(),
        EquityCurveRecorder(),
    )
    stream._trading_client = Mock(get_positions=Mock(return_value=[]))

    await stream._handle_message(_funding("-0.0123"))

    assert [(e.symbol, e.amount, e.venue) for e in seen] == [
        ("BTCUSDT", Decimal("-0.0123"), TradingVenue.FUTURES_TESTNET)
    ]
