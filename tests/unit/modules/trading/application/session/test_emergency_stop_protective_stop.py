"""`EPIC-039L` (decision D11, the owner's O1) - the Emergency Stop and a Futures protective stop.

@details The order is the safety: the regular orders go first (so a ladder cannot refill while a
position is closed), then the positions close, and only then are the conditional orders of each
symbol confirmed flat cancelled. A close that did not take a position down leaves its stop
standing and says so. The raw Binance client is a `Mock`; `FuturesTradingClient` runs for real,
so the endpoint each step reaches is what the tests read.
"""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop.command import (
    EmergencyStopCommand,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.session.emergency_stop_builders import (
    make_handler,
    open_order_payload,
    position_payload,
)

_VENUE = TradingVenue.FUTURES_TESTNET


def _stop_payload(symbol: str = "BTCUSDT") -> dict:
    return {
        "clientAlgoId": "SEW-bot-stop1",
        "algoId": 2_000_001,
        "symbol": symbol,
        "side": "SELL",
        "orderType": "STOP_MARKET",
        "algoType": "CONDITIONAL",
        "algoStatus": "NEW",
        "triggerPrice": "50000",
        "closePosition": True,
        "workingType": "MARK_PRICE",
        "createTime": 1,
    }


def _raw(*, regular: list, stops: list, positions: list) -> tuple[Mock, list[str]]:
    """A raw client whose reads answer from `positions` as they are *now* (a close empties them
    unless `close_leaves` says otherwise) and that records which endpoint each step reached."""
    calls: list[str] = []
    raw = Mock()
    resting = list(regular)
    raw.futures_get_open_orders.side_effect = lambda **_: list(resting)
    raw.futures_get_open_algo_orders.side_effect = lambda **_: list(stops)
    raw.futures_position_information.side_effect = lambda **_: list(positions)
    raw.futures_cancel_all_open_orders.side_effect = lambda **_: (
        calls.append("cancel_regular") or resting.clear()
    )
    raw.futures_cancel_all_algo_open_orders.side_effect = lambda **_: calls.append(
        "cancel_stops"
    )
    raw.futures_create_order.side_effect = lambda **_: (
        calls.append("close")
        or {
            "clientOrderId": "x",
            "symbol": "BTCUSDT",
            "side": "SELL",
            "type": "MARKET",
            "origQty": "0.002",
            "status": "FILLED",
            "price": "0",
            "stopPrice": "0",
            "reduceOnly": True,
        }
    )
    return raw, calls


def test_the_ladder_goes_first_then_the_close_then_the_stop_over_a_flat_symbol() -> (
    None
):
    positions = [position_payload()]
    raw, calls = _raw(
        regular=[open_order_payload()], stops=[_stop_payload()], positions=positions
    )
    # The close empties the account: the position read after it is flat.
    raw.futures_create_order.side_effect = lambda **_: (
        calls.append("close")
        or (
            positions.clear()
            or {
                "clientOrderId": "x",
                "symbol": "BTCUSDT",
                "side": "SELL",
                "type": "MARKET",
                "origQty": "0.002",
                "status": "FILLED",
                "price": "0",
                "stopPrice": "0",
                "reduceOnly": True,
            }
        )
    )

    result = make_handler(raw_client=raw).execute(EmergencyStopCommand(venue=_VENUE))

    assert calls == ["cancel_regular", "close", "cancel_stops"]
    assert result.conditional_orders_cancelled.succeeded
    assert result.fully_succeeded


def test_a_close_that_left_the_position_leaves_its_stop_standing_and_says_so() -> None:
    raw, calls = _raw(
        regular=[], stops=[_stop_payload()], positions=[position_payload()]
    )

    result = make_handler(raw_client=raw).execute(EmergencyStopCommand(venue=_VENUE))

    assert "cancel_stops" not in calls, "the stop must not go while the position stands"
    assert not result.conditional_orders_cancelled.succeeded
    assert "BTCUSDT" in result.conditional_orders_cancelled.detail
    assert not result.fully_succeeded


def test_stops_are_kept_when_the_account_cannot_be_read_after_the_close() -> None:
    raw, calls = _raw(regular=[], stops=[_stop_payload()], positions=[])
    raw.futures_position_information.side_effect = [[], RuntimeError("timed out")]

    result = make_handler(raw_client=raw).execute(EmergencyStopCommand(venue=_VENUE))

    assert "cancel_stops" not in calls, "unread is not flat"
    assert not result.conditional_orders_cancelled.succeeded


def test_a_stop_over_a_flat_symbol_with_no_position_at_all_is_cancelled() -> None:
    raw, calls = _raw(regular=[], stops=[_stop_payload()], positions=[])

    result = make_handler(raw_client=raw).execute(EmergencyStopCommand(venue=_VENUE))

    assert calls == ["cancel_stops"]
    assert result.conditional_orders_cancelled.succeeded


def test_the_regular_cancel_never_reaches_the_conditional_endpoint() -> None:
    raw, calls = _raw(
        regular=[open_order_payload()],
        stops=[_stop_payload()],
        positions=[position_payload()],
    )

    make_handler(raw_client=raw).execute(EmergencyStopCommand(venue=_VENUE))

    assert calls[0] == "cancel_regular"
    raw.futures_cancel_all_algo_open_orders.assert_not_called()


def test_a_stop_stays_over_a_flat_symbol_whose_ladder_could_not_be_cancelled() -> None:
    """Review of #550: flat is not safe while a regular order rests, because a fill reopens a
    position with no stop and no bot."""
    raw, calls = _raw(
        regular=[open_order_payload()], stops=[_stop_payload()], positions=[]
    )
    raw.futures_cancel_all_open_orders.side_effect = RuntimeError("refused")

    result = make_handler(raw_client=raw).execute(EmergencyStopCommand(venue=_VENUE))

    assert "cancel_stops" not in calls
    assert not result.orders_cancelled.succeeded
    assert not result.conditional_orders_cancelled.succeeded
    assert "BTCUSDT" in result.conditional_orders_cancelled.detail
