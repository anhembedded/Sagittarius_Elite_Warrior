from dataclasses import dataclass, field
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class OrderFilledEvent(BaseEvent):
    """
    @brief Domain event fired when `order` fills, fully or partially
    (`EPIC-021E`/`EPIC-021F`) — the event `BOT-009`'s Trade Markers Manager
    has been waiting for; the name is load-bearing, keep it exact.

    @details `fill_price`/`fill_quantity` describe this one fill, not the
    order's running total — `order.status` (`OrderStatus.PARTIALLY_FILLED`
    vs `OrderStatus.FILLED`) already says whether more is expected.

    @par Not `frozen` — a cost of inheriting `BaseEvent` (`EPIC-008F`)
    This was `@dataclass(frozen=True)`. Python forbids a frozen dataclass from
    inheriting a non-frozen one, and `BaseEvent` cannot become frozen: it
    supports subclasses with hand-written `__init__` that assign attributes
    (the engine's own `HealthUpdatedEvent` is one), which freezing would break.
    So adopting the Shared Kernel base costs immutability here.

    Not free: `test_signal_generated_event_is_no_longer_frozen` used to assert
    `FrozenInstanceError` here, so this trades away a guarantee somebody had
    deliberately locked down. User chose to accept that (2026-08-25) rather
    than give up registry membership. Treat these as read-only **by
    convention** now — a handler that mutates an event mutates it for every
    later subscriber in the same fan-out, and nothing stops it any more.

    Equality still works on payload: `BaseEvent` marks its `_event_id` /
    `_occurred_on` `compare=False`, without which a per-instance UUID would
    make two identical events compare unequal.
    """

    order: Order
    fill_price: Decimal
    fill_quantity: Decimal
    #: `EPIC-027L` — Spot's per-fill commission (`"n"`/`"N"` on
    #: `executionReport`), absent for Futures (`ORDER_TRADE_UPDATE` carries
    #: no per-fill commission field at all — funding/commission there is a
    #: separate wallet-balance concern `account_update_wallet_balance`
    #: already covers). `None` rather than `Decimal(0)` when unknown: a real
    #: zero-fee fill and "this venue's parser never populated it" are
    #: different facts (`code/errors.md` §6, no fabricated fallback).
    fee_amount: Decimal | None = None
    fee_asset: str | None = None
    #: `EPIC-028C` — the venue this happened on, so a screen showing one
    #: venue never shows another's. No default: a missing venue is exactly
    #: the fill landing in the wrong desk's table.
    venue: TradingVenue = field(kw_only=True)
