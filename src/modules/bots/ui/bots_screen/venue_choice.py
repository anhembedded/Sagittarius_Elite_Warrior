"""`BOT-171` — the venues a bot may be on, each with its connection state.

@details New bot and the Plan's Venue field offer the same list: every venue a bot kind
runs on, each in its market's words. A kind is offered a venue only when it declares the
venue's market (`IBotKind.supported_profiles`). A venue the owner has not opened (Futures
mainnet until `EPIC-039L`) is listed too, closed and with the reason, never silently left out
(`BUG-208`). The state is what is known without a network call: whether the venue has an
API key (`credentials_provider` is the stored key, ungated — it never reaches the
exchange). Whether the key *works* is the Connect step's read, made once a bot is
on the venue, and its failure is told once, in the message bar (`BUG-181`).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import QComboBox
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    bot_closed_reason,
    plan_market_of,
    runs_bots_on,
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

KEY_SAVED = "API key saved"
NO_KEY = "no API key"
NOT_ENABLED = "not enabled"
CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class VenueChoice:
    """One venue a bot may be on, and what is known of its connection."""

    venue: TradingVenue
    connection: str
    #: Why no bot may be created on this venue yet; `None` when one may.
    closed_reason: str | None = None

    @property
    def option_text(self) -> str:
        return f"{self.venue.display_name} — {self.connection}"


def venue_choices(
    contexts: IVenueContexts, kinds: Iterable[IBotKind]
) -> tuple[VenueChoice, ...]:
    """Every venue some kind runs on, those with an API key first, then in `TradingVenue`
    order, the closed ones last, so the preselected one is a venue a bot can start on whenever
    one has a key (`BUG-155`)."""
    enabled = contexts.enabled()
    markets = frozenset(
        market for kind in kinds for market in kind.supported_profiles()
    )
    choices = [
        _choice_of(contexts, venue, enabled)
        for venue in TradingVenue
        if _runs_bots(venue) and plan_market_of(venue) in markets
    ]
    return tuple(
        sorted(
            choices,
            key=lambda choice: (
                choice.closed_reason is not None,
                choice.connection != KEY_SAVED,
            ),
        )
    )


def _runs_bots(venue: TradingVenue) -> bool:
    profile = venue_profile_of(venue)
    return profile is not None and runs_bots_on(profile)


def _choice_of(
    contexts: IVenueContexts, venue: TradingVenue, enabled: tuple[TradingVenue, ...]
) -> VenueChoice:
    reason = bot_closed_reason(venue)
    if reason is not None:
        return VenueChoice(venue, CLOSED, reason)
    return VenueChoice(venue, _connection_of(contexts, venue, enabled))


def _connection_of(
    contexts: IVenueContexts, venue: TradingVenue, enabled: tuple[TradingVenue, ...]
) -> str:
    if venue not in enabled:
        return NOT_ENABLED
    saved = contexts.get(venue).credentials_provider.resolve().credentials
    return KEY_SAVED if saved is not None else NO_KEY


def add_venue_choice(combo: QComboBox, choice: VenueChoice) -> None:
    """List `choice` in `combo`; a closed venue is shown greyed out, unselectable, with
    its reason as the tooltip (`BUG-208`). Both venue pickers list through here."""
    combo.addItem(choice.option_text, choice.venue)
    model = combo.model()
    if choice.closed_reason is None or not isinstance(model, QStandardItemModel):
        return
    item = model.item(combo.count() - 1)
    if item is not None:
        item.setEnabled(False)
        item.setToolTip(choice.closed_reason)
