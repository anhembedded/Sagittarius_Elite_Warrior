"""trading's read side: the three queries the Trading screen and Dev Board
dispatch.

`EPIC-025E` PR 4.4f-4 — moved out of `binance_bot_module.py`, same shape
`command_bindings.py` in this package already uses.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order import (
    PreviewOrderQuery,
    PreviewOrderQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_exchange_connection_status import (
    GetExchangeConnectionStatusQuery,
    GetExchangeConnectionStatusQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_positions import (
    GetOpenPositionsQuery,
    GetOpenPositionsQueryHandler,
)
from sagittarius_engine.interfaces.i_container import IContainer


def bind_queries(container: IContainer) -> None:
    """Route each trading query type to the handler that answers it."""
    container.bind(GetOpenPositionsQuery, GetOpenPositionsQueryHandler)
    container.bind(
        GetExchangeConnectionStatusQuery, GetExchangeConnectionStatusQueryHandler
    )
    container.bind(PreviewOrderQuery, PreviewOrderQueryHandler)
