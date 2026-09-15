"""`EPIC-021D` — headless `main.py exchange-status`. The first CLI command
that touches the real exchange, read-only."""

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
    IAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.exchange_status_formatter import (
    format_exchange_connection_status,
)
from sagittarius_engine import App


def execute_exchange_status(app: App) -> None:
    """`EPIC-025` PR 1.3b — resolves `trading`'s published port instead of
    building its query. Same handler underneath, same output; what changes is
    that this file no longer imports another context's `application/` package
    to name a type it only wanted to dispatch."""
    status = app.container.resolve(IAccountSnapshot).check_connection()
    print(format_exchange_connection_status(status))
