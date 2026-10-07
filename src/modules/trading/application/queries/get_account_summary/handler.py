"""`EPIC-028D` — `GetAccountSummaryQueryHandler`.

@details Reads the summary off the venue's own
`ITradingAccountReader.check_connection()`, the same seam
`GetHoldingsQueryHandler` uses: both readers fill
`ExchangeConnectionStatus.summary` from the account payload they already
fetch, so the answer costs no second request and needs no market branch
here.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_account_summary.query import (
    GetAccountSummaryQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary_unavailable_error import (
    AccountSummaryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)

logger = logging.getLogger("App.QueryHandler")


class GetAccountSummaryQueryHandler(
    IQueryHandler[GetAccountSummaryQuery, AccountSummary | None]
):
    """@return The venue's summary, or `None` when the check named no failure
    and still built no summary.
    @throws AccountSummaryUnavailableError The check failed; the exception
    carries its `ConnectionFailureKind` (`BUG-174`)."""

    def __init__(self, contexts: IVenueContexts) -> None:
        self._contexts = contexts

    def execute(self, query: GetAccountSummaryQuery) -> AccountSummary | None:
        logger.debug("Handling GetAccountSummaryQuery on %s", query.venue.value)
        status = self._contexts.get(query.venue).account_reader.check_connection()
        if status.summary is None and status.failure is not None:
            raise AccountSummaryUnavailableError(status.failure)
        return status.summary
