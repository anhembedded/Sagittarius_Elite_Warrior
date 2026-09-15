"""`IAccountSnapshot`, implemented over the two read-only queries.

Both queries are parameterless and both already answer with the published
type, so this class is the thinnest of the three: it exists to give the two
reads one name and one type, not to add anything to them.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_exchange_connection_status.query import (
    GetExchangeConnectionStatusQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_positions.query import (
    GetOpenPositionsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
    IAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)


class AccountSnapshotService(IAccountSnapshot):
    """The module's answer to "can we reach the venue, and what is open"."""

    def __init__(self, dispatcher: ICommandDispatcher) -> None:
        self._dispatcher = dispatcher

    def check_connection(self) -> ExchangeConnectionStatus:
        response = self._dispatcher.dispatch(
            GetExchangeConnectionStatusQuery, GetExchangeConnectionStatusQuery()
        )
        if not isinstance(response, ExchangeConnectionStatus):
            raise TypeError(
                "the connection check was not answered with "
                f"ExchangeConnectionStatus but with {type(response).__name__} "
                "— no handler is bound for it"
            )
        return response

    def open_positions(self) -> tuple[LivePosition, ...]:
        """A tuple, always. The handler answers with one; anything else means
        no handler is bound, and an empty tuple would report "nothing open"
        for a broken container — the one answer a caller must not be given
        (`IAccountSnapshot`'s own docstring)."""
        response = self._dispatcher.dispatch(
            GetOpenPositionsQuery, GetOpenPositionsQuery()
        )
        if not isinstance(response, tuple):
            raise TypeError(
                "the open-positions read was not answered with a tuple but "
                f"with {type(response).__name__} — no handler is bound for it"
            )
        return response
