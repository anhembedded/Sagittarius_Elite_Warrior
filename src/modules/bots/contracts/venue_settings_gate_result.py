"""`EPIC-039E` — what a venue's settings gate is asked, and what it answers.

@details A Futures bot names a leverage and a margin mode; the venue's symbol must hold
exactly those before the first order, and must be *proved* to still hold them later. The gate
(`IVenueSettingsGate`) answers with a `GateResult`: `ENSURED`, or a named refusal whose
`detail` is the words a Start refusal or a halt shows, with both values in it.

@par Extension cases
  · Cross margin - a `MarginMode.CROSS` request is already expressible; the venue profile
    decides whether a bot may ask for it (`VenueProfile.margin_modes`);
  · a setting the exchange later adds (a position-mode check, Multi-Assets) - one more
    `GateOutcome` and one more comparison in the adapter, no change to a caller that reads
    `ensured` and `detail`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.margin_mode import MarginMode
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class GateOutcome(str, Enum):
    ENSURED = "ensured"
    #: The account's position mode is Hedge; this app trades One-way only (decision D3).
    HEDGE_MODE_UNSUPPORTED = "hedge_mode_unsupported"
    #: A change was needed and the symbol has an open order or a position, so the exchange
    #: would refuse it; nothing was sent.
    SYMBOL_NOT_FLAT = "symbol_not_flat"
    #: The exchange holds a different leverage or margin type than the bot asked for.
    SETTINGS_MISMATCH = "settings_mismatch"
    #: A setting or the account's mode could not be read; a missing fact is never a match.
    SETTINGS_UNREADABLE = "settings_unreadable"
    #: The exchange answered a change with a refusal of its own.
    EXCHANGE_REFUSED = "exchange_refused"
    #: The order path's own safety gate stopped the change before any request: a change is
    #: signed account activity, gated like a cancel (the venue's order session is not open,
    #: the connection is not ready). Start opens the session first.
    CHANGE_NOT_PERMITTED = "change_not_permitted"


@dataclass(frozen=True, slots=True)
class GateRequest:
    """What the bot's parameters ask of one symbol on one venue."""

    venue: TradingVenue
    symbol: str
    leverage: int
    margin_mode: MarginMode

    def __post_init__(self) -> None:
        if self.leverage < 1:
            raise ValueError(f"leverage must be 1 or more, got {self.leverage}")


@dataclass(frozen=True, slots=True)
class GateResult:
    outcome: GateOutcome
    #: The words for the user; empty exactly when the outcome is `ENSURED`.
    detail: str = ""

    def __post_init__(self) -> None:
        if (self.outcome is GateOutcome.ENSURED) != (self.detail == ""):
            raise ValueError(
                "a refusal names why; an ensured result has nothing to add"
            )

    @property
    def ensured(self) -> bool:
        return self.outcome is GateOutcome.ENSURED


ENSURED = GateResult(GateOutcome.ENSURED)
