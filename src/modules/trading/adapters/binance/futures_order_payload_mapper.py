"""`EPIC-021F` — domain `Order`/`LivePosition` ↔ Binance Futures REST
payload. Pure logic, no network — this is what makes it the cheapest place
to catch a mapping mistake, before a live call ever confirms it the
expensive way (a rejected/misrouted order).

@details `side` (BUY/SELL) and `positionSide` are two different fields on
Binance's own API; this app always sends `positionSide=BOTH` (One-way,
already enforced at the connection-check door by `EPIC-021D`'s
`ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED`). `timeInForce` is only
valid for `LIMIT`. `quantity`/`price`/`stop_price` are trusted to already
be rounded to the symbol's `stepSize`/`tickSize`
(`OrderQuantityRoundingPolicy`, `EPIC-021C`) — this module never rounds
anything itself; it rejects an unrounded `Order` with a named error
instead, so domain and exchange can never silently disagree about the
quantity that was actually sent.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.order_enum_parsing import (
    order_status_or_unknown,
    order_type_or_unknown,
    time_in_force_or_none,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.invalid_order_for_submission import (
    InvalidOrderForSubmissionError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LiquidationPrice,
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)

#: `positionSide` Binance's API expects when the account is One-way mode —
#: never anything else in this epic (ADR §6, `EPIC-021D`).
_ONE_WAY_POSITION_SIDE = "BOTH"

#: `EPIC-028O` — the conditional types this app's enum names. Binance serves
#: every one of them through the Algo Order API (`POST /fapi/v1/algoOrder`,
#: its change of 2025-12-09), never through `POST /fapi/v1/order`, so this
#: mapper refuses them all. `EPIC-028R` sends the stop-limit through
#: `futures_algo_order_mapper.py`, with the app's client id as `clientAlgoId`;
#: `STOP_MARKET` and `TAKE_PROFIT_MARKET` stay unsent until a desk needs them.
_CONDITIONAL_ORDER_TYPES = frozenset(
    {OrderType.STOP_MARKET, OrderType.TAKE_PROFIT_MARKET, OrderType.STOP_LIMIT}
)
#: What the Futures client can send: `MARKET` and `LIMIT` here, `STOP_LIMIT`
#: through the Algo Order API (`EPIC-028R`); everything else is refused
#: (`FuturesTradingClientFactory.accepted_order_types` answers with this).
FUTURES_SENDABLE_ORDER_TYPES = frozenset(
    {OrderType.MARKET, OrderType.LIMIT, OrderType.STOP_LIMIT}
)
#: Futures' spelling of a member whose name is not Binance's, for the read
#: direction: a stop-limit is `STOP` on USD-M.
FUTURES_ORDER_TYPE_NAMES: dict[str, OrderType] = {"STOP": OrderType.STOP_LIMIT}


def _require_step_aligned(quantity: Decimal, step_size: Decimal, label: str) -> None:
    if step_size > 0 and quantity % step_size != 0:
        raise InvalidOrderForSubmissionError(
            f"{label} {quantity} is not a multiple of step size {step_size} — "
            "round it with OrderQuantityRoundingPolicy before submitting."
        )


def map_order_to_futures_params(
    order: Order, metadata: SymbolOrderMetadata
) -> dict[str, Any]:
    """@brief Builds the `**params` dict `python-binance`'s
    `futures_create_order`/`futures_create_test_order` expects from `order`.
    @raise InvalidOrderForSubmissionError If `order` is a conditional type
    (`_CONDITIONAL_ORDER_TYPES`), is sized by quote amount, its quantity/
    price is not already rounded to `metadata`'s filters, or a `LIMIT`
    lacks its `price`/`time_in_force`.
    """
    if order.order_type in _CONDITIONAL_ORDER_TYPES:
        raise InvalidOrderForSubmissionError(
            f"{order.order_type.name} on Futures goes through Binance's Algo Order "
            "API, not POST /fapi/v1/order (futures_algo_order_mapper.py)."
        )
    if order.order_type not in FUTURES_SENDABLE_ORDER_TYPES:
        raise InvalidOrderForSubmissionError(
            f"{order.order_type.name} is not an order type the Futures client sends."
        )
    if order.quote_quantity is not None:
        raise InvalidOrderForSubmissionError(
            "USD-M Futures has no quote-sized order; size it by quantity."
        )
    _require_step_aligned(order.quantity, metadata.step_size, "quantity")

    params: dict[str, Any] = {
        "symbol": order.symbol,
        "side": order.side.value,
        "type": order.order_type.name,
        "quantity": str(order.quantity),
        "newClientOrderId": str(order.client_order_id),
        "positionSide": _ONE_WAY_POSITION_SIDE,
        "reduceOnly": order.reduce_only,
    }

    if order.order_type is OrderType.LIMIT:
        if order.price is None:
            raise InvalidOrderForSubmissionError("LIMIT order is missing price.")
        if order.time_in_force is None:
            raise InvalidOrderForSubmissionError(
                "LIMIT order is missing time_in_force."
            )
        _require_step_aligned(order.price, metadata.tick_size, "price")
        params["price"] = str(order.price)
        params["timeInForce"] = order.time_in_force.value

    return params


def _decimal_or_none(raw: Any) -> Decimal | None:
    if raw is None:
        return None
    value = Decimal(str(raw))
    return value if value != 0 else None


def _order_time_or_none(payload: dict[str, Any]) -> datetime | None:
    """`updateTime` (last change) over `time` (creation) — `EPIC-021I` §3.1
    wants "when did this order last change", the same fact `LivePosition.
    updated_at` already reports for a position. Falls back to `time` only
    when `updateTime` is absent (some REST responses omit it); `None` when
    neither is present rather than fabricating "now"."""
    raw = payload.get("updateTime") or payload.get("time")
    return datetime.fromtimestamp(raw / 1000, tz=UTC) if raw else None


def map_futures_order_payload_to_order(payload: dict[str, Any]) -> Order:
    """@brief The reverse direction: one order object from a Binance
    Futures REST response (`place`/`cancel`/`get_open_orders`) back into a
    domain `Order`.
    @details `price`/`stop_price` come back as `"0"`/`"0.0"` from Binance
    for order types that don't use them, not as an absent field — treated
    as `None` here, matching how `Order` itself represents "not
    applicable" rather than "zero".
    @raise KeyError A required field is missing — a genuinely malformed
    payload, not merely an unrecognized `type`/`status` value
    (`order_enum_parsing.py` handles that case without raising, `BUG-091`
    — the whole-account reconciliation this feeds, `EnableTradingCommand`'s
    `get_open_orders()`, must not lose an order just because it wasn't
    placed by this app).
    """
    order_type = order_type_or_unknown(payload["type"], FUTURES_ORDER_TYPE_NAMES)
    return Order(
        client_order_id=ClientOrderId(payload["clientOrderId"]),
        symbol=payload["symbol"],
        side=OrderSide[payload["side"]],
        order_type=order_type,
        quantity=Decimal(str(payload["origQty"])),
        status=order_status_or_unknown(payload["status"]),
        price=_decimal_or_none(payload.get("price")),
        stop_price=_decimal_or_none(payload.get("stopPrice")),
        time_in_force=time_in_force_or_none(payload.get("timeInForce")),
        reduce_only=bool(payload.get("reduceOnly", False)),
        order_time=_order_time_or_none(payload),
    )


def _leverage_from_margin(payload: dict[str, Any]) -> int:
    """`BUG-114` — `/fapi/v1(v2)/positionRisk`'s documented `leverage`
    field does not exist on the real `/fapi/v3/positionRisk` response
    `futures_position_information()` actually calls: a real Testnet
    account hit `KeyError: 'leverage'` on every position, every time.
    Binance's own margin formula (`initialMargin = notional / leverage`)
    is reported to hold in cross margin's base tier; recovers `20` here
    against a real payload independently confirmed as 20x on Binance's
    own Testnet UI. Deliberately deviates from this module's own
    "never computes, only parses" rule (see module docstring) — the field
    this app depended on for years turned out to not exist on the wire at
    all, and no other already-verified field reports it directly.
    """
    # `notional` is signed (negative for a short); leverage is not. A 20x
    # short read as -20x before `EPIC-028O`'s fake filled one.
    notional = abs(Decimal(str(payload["notional"])))
    initial_margin = Decimal(str(payload["initialMargin"]))
    if initial_margin == 0:
        # A real open position (`positionAmt != 0`, already filtered by
        # the caller) always carries a non-zero initial margin requirement
        # — reaching here means the exchange sent a shape this formula
        # cannot make sense of. Refusing loudly beats reporting a
        # fabricated leverage number (`domain-truth-rule.md`).
        raise KeyError("leverage")
    return int((notional / initial_margin).to_integral_value())


def _margin_type_from_isolation(payload: dict[str, Any]) -> MarginType:
    """`BUG-114` — same defunct-field problem as `_leverage_from_margin`:
    real `/fapi/v3/positionRisk` carries no `marginType` string either.
    `isolatedMargin` (and `isolatedWallet`) are non-zero only for an
    isolated position — real Cross-margin payloads observed report both
    as `"0"`."""
    isolated_margin = _decimal_or_none(payload.get("isolatedMargin"))
    return (
        MarginType.ISOLATED
        if isolated_margin is not None and isolated_margin != 0
        else MarginType.CROSSED
    )


def map_futures_position_payload_to_live_position(
    payload: dict[str, Any],
) -> LivePosition:
    """@brief One entry of `futures_position_information()`'s response into
    a domain `LivePosition`.
    @details `updateTime` is not present on every version of this endpoint
    this app has seen documented; falls back to "now" rather than
    fabricating a stale timestamp when it's missing.
    """
    liquidation_price_raw = _decimal_or_none(payload.get("liquidationPrice"))
    update_time_ms = payload.get("updateTime")
    updated_at = (
        datetime.fromtimestamp(update_time_ms / 1000, tz=UTC)
        if update_time_ms
        else datetime.now(UTC)
    )
    return LivePosition(
        symbol=payload["symbol"],
        position_amt=Decimal(str(payload["positionAmt"])),
        entry_price=Decimal(str(payload["entryPrice"])),
        mark_price=Decimal(str(payload["markPrice"])),
        unrealized_pnl=Decimal(str(payload["unRealizedProfit"])),
        leverage=_leverage_from_margin(payload),
        margin_type=_margin_type_from_isolation(payload),
        liquidation_price=(
            LiquidationPrice(liquidation_price_raw)
            if liquidation_price_raw is not None
            else None
        ),
        updated_at=updated_at,
    )
