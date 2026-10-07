"""`EPIC-034E` — handler for `GetMainnetAccountQuery`: the read-only mainnet
account's reader answers. It holds `IVenueAccounts` only, so reaching it can
read and nothing else."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_mainnet_account.query import (
    GetMainnetAccountQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_accounts import (
    IVenueAccounts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)

logger = logging.getLogger("App.QueryHandler")


class GetMainnetAccountQueryHandler(
    IQueryHandler[GetMainnetAccountQuery, VenueAccountSnapshot | ConnectFailure]
):
    def __init__(self, accounts: IVenueAccounts) -> None:
        self._accounts = accounts

    def execute(
        self, query: GetMainnetAccountQuery
    ) -> VenueAccountSnapshot | ConnectFailure:
        logger.debug("Handling GetMainnetAccountQuery for %s", query.symbol)
        return self._accounts.reader(AccountSource.SPOT_MAINNET_READONLY).read(
            query.symbol
        )
