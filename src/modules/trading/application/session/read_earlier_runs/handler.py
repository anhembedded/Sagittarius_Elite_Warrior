"""`BUG-196` — what an owner's earlier runs left, capped by the account.

@details Two reads of exchange evidence, in the order of their cost: the
venue's history of the owner's tagged orders and trades (the quantity, and the
cost of it), then the account's free base (the cap). A coin the user sold or
moved by hand since the run ended is not in the account, so it is not claimed:
the answer is the smaller of the two, its cost scaled with it. A venue that
does not answer is a named `unavailable`, never a zero: nobody is told "nothing
left" on the strength of a read that failed. Nothing is installed and nothing
is saved; the current run's book and checkpoint are untouched.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.earlier_runs_deriver import (
    derive_earlier_runs,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.read_earlier_runs.command import (
    ReadEarlierRunsCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScopes,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.earlier_runs_inventory import (
    EarlierRunsInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)

logger = logging.getLogger("App.CommandHandler")


class ReadEarlierRunsCommandHandler(
    ICommandHandler[ReadEarlierRunsCommand, EarlierRunsInventory]
):
    """Replays the owner's history before the current run, then caps it."""

    def __init__(self, scopes: VenueTradingScopes) -> None:
        self._scopes = scopes

    def execute(self, command: ReadEarlierRunsCommand) -> EarlierRunsInventory:
        request = command.request
        ports = self._scopes.get(command.venue).ports
        ports.history_reader.discard_remembered(request.symbol)
        try:
            earlier = derive_earlier_runs(
                request, ports.history_reader, datetime.now(UTC)
            )
        except AccountHistoryUnavailableError as exc:
            logger.warning(
                "[earlier-runs] %s: history unavailable: %s", request.tag, exc
            )
            return EarlierRunsInventory(unavailable=str(exc))
        if not earlier.is_left:
            return earlier
        free = _free_base(ports.account_reader.check_connection(), request.base_asset)
        if free is None:
            return EarlierRunsInventory(
                unavailable="the account's holdings were not read"
            )
        if free >= earlier.quantity:
            return earlier
        logger.info(
            "[earlier-runs] %s: history says %s %s, the account has %s free.",
            request.tag,
            earlier.quantity,
            request.base_asset,
            free,
        )
        return EarlierRunsInventory(
            free, earlier.cost * free / earlier.quantity, earlier.counted_from
        )


def _free_base(status: ExchangeConnectionStatus, asset: str) -> Decimal | None:
    """The account's free `asset`, `None` when the holdings were not read."""
    if status.holdings is None:
        return None
    return next((h.free for h in status.holdings if h.asset == asset), Decimal(0))
