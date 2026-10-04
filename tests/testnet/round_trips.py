"""The two real round trips this tier proves, written once against the ports.

`EPIC-028N` runs both in one process through `IVenueContexts`. The single-
venue tests (`test_order_lifecycle.py`, `spot/test_spot_order_lifecycle.py`)
run each one with adapters built by hand. All three share these bodies, so a
fix to a wait, a bound or a clean-up lands in one place. Each test module's
docstring explains its choices: the quantities, waiting on a named condition
rather than a sleep, and the residue bound.

Plain functions taking ports (`ITradingClient`, `ITradingAccountReader`,
`IMarketMetadataProvider`), never concrete adapters, so the composed path
and the hand-built path are proven by the same assertions.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    generate_client_order_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    OrderQuantityRoundingPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType

SYMBOL = "BTCUSDT"
#: Futures: comfortably above `MIN_NOTIONAL`, aligned to the `0.001` step.
FUTURES_QUANTITY = Decimal("0.002")
SPOT_ASSET = "BTC"
#: Spot: clears the 5 USDT `NOTIONAL` minimum, well above the `0.00001` step.
SPOT_QUANTITY = Decimal("0.0002")
_POLL_INTERVAL_S = 1.0
_TIMEOUT_S = 30.0

_ROUNDING = OrderQuantityRoundingPolicy()


def _market(side: OrderSide, quantity: Decimal, *, reduce_only: bool = False) -> Order:
    return Order(
        client_order_id=generate_client_order_id(),
        symbol=SYMBOL,
        side=side,
        order_type=OrderType.MARKET,
        quantity=quantity,
        reduce_only=reduce_only,
    )


def wait_until(what: str, condition: Callable[[], bool]) -> None:
    """@brief Polls `condition` until it holds, or raises `TimeoutError`
    naming `what`: a named condition, never a blind sleep."""
    deadline = time.monotonic() + _TIMEOUT_S
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(_POLL_INTERVAL_S)
    raise TimeoutError(f"{what} within {_TIMEOUT_S}s")


def _wait_until_position(
    client: ITradingClient, predicate: Callable[[list[LivePosition]], bool]
) -> list[LivePosition]:
    """@brief Polls `get_positions()` until `predicate` accepts the result,
    or raises `TimeoutError`: a named condition, not a blind sleep."""
    deadline = time.monotonic() + _TIMEOUT_S
    while time.monotonic() < deadline:
        positions = client.get_positions(SYMBOL)
        if predicate(positions):
            return positions
        time.sleep(_POLL_INTERVAL_S)
    raise TimeoutError(
        f"{SYMBOL} position did not reach the expected state within {_TIMEOUT_S}s"
    )


def futures_open_and_close(client: ITradingClient) -> None:
    """A MARKET BUY opens a position of exactly `FUTURES_QUANTITY`; a
    reduce-only MARKET SELL takes it back to flat. A position left open by
    any failure is closed in `finally`."""
    try:
        client.place_order(_market(OrderSide.BUY, FUTURES_QUANTITY))
        positions = _wait_until_position(client, lambda p: len(p) == 1)
        assert positions[0].position_amt == FUTURES_QUANTITY

        client.place_order(_market(OrderSide.SELL, FUTURES_QUANTITY, reduce_only=True))
        _wait_until_position(client, lambda p: len(p) == 0)
    finally:
        remaining = client.get_positions(SYMBOL)
        if remaining:
            amount = remaining[0].position_amt
            client.place_order(
                _market(
                    OrderSide.SELL if amount > 0 else OrderSide.BUY,
                    abs(amount),
                    reduce_only=True,
                )
            )


def _holding_free(status: ExchangeConnectionStatus, asset: str) -> Decimal:
    holding = next((h for h in status.holdings or () if h.asset == asset), None)
    return holding.free if holding is not None else Decimal(0)


def is_back_to_baseline(free: Decimal, baseline: Decimal, step: Decimal) -> bool:
    """@brief The round trip's exact residue bound, derived rather than
    guessed: the SELL quantity is the BUY's *net* fill (after its fee,
    charged in the asset received) floored to the lot step, so what it
    cannot sell is strictly less than one `step`; the SELL's own fee is
    charged in the quote asset and never touches this holding. A fee-sized
    tolerance is smaller than that floor remainder (0.1 % of 0.0002 BTC vs
    a 0.00001 step) and would time out on every run that pays fees in BTC."""
    return abs(free - baseline) < step


def _wait_until_holding_free(
    account_reader: ITradingAccountReader, predicate: Callable[[Decimal], bool]
) -> Decimal:
    """@brief Polls `check_connection()` until `predicate(free)` accepts the
    result, or raises `TimeoutError`: a named condition, not a blind sleep."""
    deadline = time.monotonic() + _TIMEOUT_S
    while time.monotonic() < deadline:
        status = account_reader.check_connection()
        assert status.reachable, status.failure
        free = _holding_free(status, SPOT_ASSET)
        if predicate(free):
            return free
        time.sleep(_POLL_INTERVAL_S)
    raise TimeoutError(
        f"{SPOT_ASSET} holding did not reach the expected state within {_TIMEOUT_S}s"
    )


def _assert_not_resting(client: ITradingClient, order: Order) -> None:
    """A filled MARKET order leaves no open remainder on Spot, so its absence
    is the FILLED proof; `place_order()` returns the `Order` unchanged."""
    assert order.client_order_id not in {
        o.client_order_id for o in client.get_open_orders(SYMBOL)
    }


def spot_buy_and_sell(
    client: ITradingClient,
    account_reader: ITradingAccountReader,
    metadata_provider: IMarketMetadataProvider,
) -> None:
    """A MARKET BUY makes the `SPOT_ASSET` holding grow; a MARKET SELL of what
    was received, floored to the lot step, returns it to within one step of
    its baseline. A surplus left by any failure is sold in `finally`."""
    metadata = metadata_provider.get_or_fetch(SYMBOL)
    assert metadata is not None
    step = metadata.step_size_for(OrderType.MARKET)

    baseline_status = account_reader.check_connection()
    assert baseline_status.reachable, baseline_status.failure
    baseline = _holding_free(baseline_status, SPOT_ASSET)

    try:
        buy = _market(OrderSide.BUY, SPOT_QUANTITY)
        client.place_order(buy)
        _assert_not_resting(client, buy)
        after_buy = _wait_until_holding_free(account_reader, lambda f: f > baseline)

        received = _ROUNDING.round_quantity_down(after_buy - baseline, step)
        assert received > 0, (
            "the BUY fill was too small to round to a sellable quantity"
        )

        sell = _market(OrderSide.SELL, received)
        client.place_order(sell)
        _assert_not_resting(client, sell)
        final = _wait_until_holding_free(
            account_reader, lambda f: is_back_to_baseline(f, baseline, step)
        )
        assert is_back_to_baseline(final, baseline, step)
    finally:
        surplus = (
            _holding_free(account_reader.check_connection(), SPOT_ASSET) - baseline
        )
        rounded_surplus = _ROUNDING.round_quantity_down(surplus, step)
        if rounded_surplus > 0:
            client.place_order(_market(OrderSide.SELL, rounded_surplus))
