"""`EPIC-034D` — handler for `GetVenueConnectionQuery`: the Connect step's one read.

The venue's account, its terms, the key's permission to trade and the symbol's
filters and price come back as one `VenueAccountSnapshot`, or as the
`ConnectFailure` that stopped the read. The read goes through
`IVenueAccountReader`, which holds read ports only, so reaching it can never
place an order.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_venue_connection.query import (
    GetVenueConnectionQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_accounts import (
    IVenueAccounts,
    UnknownAccountSourceError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)

logger = logging.getLogger("App.QueryHandler")


class GetVenueConnectionQueryHandler(
    IQueryHandler[GetVenueConnectionQuery, VenueAccountSnapshot | ConnectFailure]
):
    def __init__(self, accounts: IVenueAccounts) -> None:
        self._accounts = accounts

    def execute(
        self, query: GetVenueConnectionQuery
    ) -> VenueAccountSnapshot | ConnectFailure:
        source = AccountSource.for_venue(query.venue)
        logger.debug(
            "Handling GetVenueConnectionQuery for %s on %s",
            query.symbol,
            source.value,
        )
        try:
            reader = self._accounts.reader(source)
        except UnknownAccountSourceError:
            return ConnectFailure(
                source, ConnectionFailureKind.NOT_CONFIGURED, "the venue is not enabled"
            )
        return reader.read(query.symbol)
