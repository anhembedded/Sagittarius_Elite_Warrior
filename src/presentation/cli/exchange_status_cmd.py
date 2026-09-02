"""`EPIC-021D` — headless `main.py exchange-status`. The first CLI command
that touches the real exchange, read-only."""

from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_exchange_connection_status import (
    GetExchangeConnectionStatusQuery,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.exchange_status_formatter import (
    format_exchange_connection_status,
)
from sagittarius_engine import App


def execute_exchange_status(app: App) -> None:
    status = app.dispatch(
        GetExchangeConnectionStatusQuery, GetExchangeConnectionStatusQuery()
    )
    print(format_exchange_connection_status(status))
