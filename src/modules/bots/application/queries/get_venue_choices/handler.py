"""`EPIC-048B` — handler for `GetVenueChoicesQuery`: each venue a bot may be on, with its connection state.

A venue a build closes is listed too, greyed out with its reason (`VenueChoice.closed_reason`),
never silently left out (`BUG-208`); no venue is closed today. The state is what is known without a
network call: whether the venue has a saved API key (`credentials_provider` is the stored key,
ungated; it never reaches the exchange). The answer holds a venue and a few words, never a key.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_venue_choices.query import (
    GetVenueChoicesQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_choice import (
    KEY_SAVED,
    NO_KEY,
    NOT_ENABLED,
    VenueChoice,
    VenueChoices,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
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


class GetVenueChoicesQueryHandler(IQueryHandler[GetVenueChoicesQuery, VenueChoices]):
    """Every venue some kind runs on, those with an API key first, then in `TradingVenue`
    order, the closed ones last, so the preselected one is a venue a bot can start on whenever
    one has a key (`BUG-155`)."""

    def __init__(self, contexts: IVenueContexts, kinds: IBotKindCatalog) -> None:
        self._contexts = contexts
        self._kinds = kinds

    def execute(self, query: GetVenueChoicesQuery) -> VenueChoices:
        enabled = self._contexts.enabled()
        return venue_choices_of(
            self._kinds,
            lambda venue: self._connection_of(venue, enabled),
        )

    def _connection_of(
        self, venue: TradingVenue, enabled: tuple[TradingVenue, ...]
    ) -> str:
        if venue not in enabled:
            return NOT_ENABLED
        saved = self._contexts.get(venue).credentials_provider.resolve().credentials
        return KEY_SAVED if saved is not None else NO_KEY


def venue_choices_of(
    kinds: IBotKindCatalog, connection_of: Callable[[TradingVenue], str]
) -> VenueChoices:
    """The venue pickers' list, from how each venue's connection reads. Pure, so the desktop
    that was told which venues the host enables and which have a key lists them in the same
    order with the same words (`EPIC-047E`)."""
    markets = frozenset(
        market for kind in kinds.kinds() for market in kind.supported_profiles()
    )
    choices = [
        VenueChoice(venue, connection_of(venue))
        for venue in TradingVenue
        if _runs_bots(venue) and plan_market_of(venue) in markets
    ]
    return VenueChoices(
        tuple(
            sorted(
                choices,
                key=lambda choice: (
                    choice.closed_reason is not None,
                    choice.connection != KEY_SAVED,
                ),
            )
        )
    )


def _runs_bots(venue: TradingVenue) -> bool:
    profile = venue_profile_of(venue)
    return profile is not None and runs_bots_on(profile)
