from dataclasses import dataclass

from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class LiveOrderBlockedEvent(BaseEvent):
    """
    @brief Domain event fired whenever `LiveTradingCoordinator` decides not
    to submit a signal-driven live order (`BUG-084`).

    @details Before this event existed, a blocked signal was invisible
    anywhere an operator would actually be looking: `logger.debug()` for a
    zero-quantity computation, `logger.info()` for a safety-gate/trading-
    limit block — neither reaches the Trading screen, so "the strategy
    didn't signal" and "it signalled but got blocked" looked identical: the
    screen just sat still. `reason` is a plain human-readable string, not
    the `ExecuteOrderResult.blocked_by` union type, on purpose — that type
    lives in `application/use_cases/`, and `domain/events/` must not import
    from a use case module (Shared Kernel direction, `architecture-rule.md`
    §3); `LiveTradingCoordinator` already has the string it would log
    anyway, so it hands that over instead of a second representation to
    keep in sync.

    @par Not `frozen` — same `BaseEvent` inheritance cost every other event
    in this module documents; treat as read-only by convention.
    """

    symbol: str
    reason: str
