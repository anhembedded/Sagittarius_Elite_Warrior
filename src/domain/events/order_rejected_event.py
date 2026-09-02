from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class OrderRejectedEvent(BaseEvent):
    """
    @brief Domain event fired when the exchange refuses `order` outright
    (`EPIC-021E`/`EPIC-021F`).

    @details `reason` is a short, named, human-readable explanation — the
    same "an exchange error code is not a stable contract"
    (`exchange_connection_status.py`'s `ConnectionFailureKind`) shape
    applies here: whatever maps Binance's numeric code onto this field
    (`EPIC-021F`) is the one place a code lookup belongs, not every
    subscriber of this event.

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
    reason: str
