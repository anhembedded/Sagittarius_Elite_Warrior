"""`EPIC-021G`, `EPIC-034C` — the outcome of one `EnsureSessionReadyCommand`: the
venue's order session is open, or the named reason it is not."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order


class SessionBlockReason(str, Enum):
    """@brief Why the order session did not open — named, never a bare `False`."""

    #: `TradingVenue.DISABLED` — a venue that places no orders at all (ADR §3),
    #: the same gate `ExecuteOrderCommand` also checks.
    TRADING_VENUE_DISABLED = "trading_venue_disabled"
    #: `EPIC-021D`'s connection check did not come back reachable and
    #: fully ready (includes Hedge Mode — `ConnectionFailureKind.
    #: HEDGE_MODE_UNSUPPORTED` already covers "reachable but not usable").
    CONNECTION_NOT_READY = "connection_not_ready"
    #: The exchange already has an open position this app has no record
    #: of — refused outright rather than silently adopted or auto-closed
    #: (`EPIC-021G` §2.4, ADR §4). The user decides what to do next.
    UNEXPECTED_POSITIONS = "unexpected_positions"
    #: `BUG-088` — something else (an Emergency Stop, an order, a
    #: reconciliation) mutated `TradingSessionState` while this command's own
    #: reconciliation network calls were in flight, most often an Emergency Stop
    #: that ran mid-reconciliation. Refused rather than applied — silently
    #: reopening the session right after an Emergency Stop would defeat the
    #: whole point of that button.
    SUPERSEDED_BY_CONCURRENT_STATE_CHANGE = "superseded_by_concurrent_state_change"


#: `EPIC-028M`/`028S` (the PR 309 reviews) — the outcomes whose
#: `reconciled_*` tuples are the venue's answer: a success (`None`) and the
#: refusals decided after the read. An allow-list, so a block reason added
#: later counts as "not read" until someone says otherwise: an empty tuple
#: from a skipped read would read as "flat" and wipe a screen's tables.
_DECIDED_AFTER_READING: frozenset[SessionBlockReason | None] = frozenset(
    {
        None,
        SessionBlockReason.UNEXPECTED_POSITIONS,
        SessionBlockReason.SUPERSEDED_BY_CONCURRENT_STATE_CHANGE,
    }
)


@dataclass(frozen=True)
class SessionReadyResult:
    #: The order session is open on the venue: reconciled just now, or by an
    #: earlier action that left it open (`already_open`).
    ready: bool
    block_reason: SessionBlockReason | None
    reconciled_positions: tuple[LivePosition, ...]
    reconciled_open_orders: tuple[Order, ...]
    #: The session was already open, so nothing was read this time: the
    #: `reconciled_*` tuples are empty because nothing was asked, not because
    #: the account is flat.
    already_open: bool = False

    @property
    def account_was_read(self) -> bool:
        """Whether `reconciled_positions`/`reconciled_open_orders` are the
        venue's answer. A refusal decided before any read (the venue off, the
        connection not ready) and a session that was already open carry empty
        tuples, and "nothing came back" is not "flat" (`BUG-093`'s principle)."""
        return not self.already_open and self.block_reason in _DECIDED_AFTER_READING
