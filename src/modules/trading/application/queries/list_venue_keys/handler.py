from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.list_venue_keys.query import (
    ListVenueKeysQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_key import (
    VenueKey,
    key_fingerprint,
)


class ListVenueKeysQueryHandler(
    IQueryHandler[ListVenueKeysQuery, tuple[VenueKey, ...]]
):
    """@brief One row per venue, in `TradingVenue` order. The full key is read
    here and goes no further: the row holds its fingerprint."""

    def __init__(self, contexts: IVenueContexts) -> None:
        self._contexts = contexts

    def execute(self, query: ListVenueKeysQuery) -> tuple[VenueKey, ...]:
        rows: list[VenueKey] = []
        for venue in self._contexts.enabled():
            resolution = self._contexts.get(venue).credentials_provider.resolve()
            credentials = resolution.credentials
            rows.append(
                VenueKey(
                    venue,
                    key_fingerprint(credentials.api_key) if credentials else None,
                    resolution.source,
                )
            )
        return tuple(rows)
