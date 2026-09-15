import argparse

from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_command_handler import (
    ICliCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_exchange_connection_status import (
    GetExchangeConnectionStatusQuery,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.exchange_status_formatter import (
    format_exchange_connection_status,
)
from sagittarius_engine import App


class ExchangeStatusCliHandler(ICliCommandHandler):
    """`EPIC-021D` — interactive-shell counterpart to
    `exchange_status_cmd.execute_exchange_status`; both share
    `format_exchange_connection_status` so their output never drifts."""

    @staticmethod
    def handle(args: argparse.Namespace, app: App) -> None:
        # `exchange-status` declares no arguments in `cli_commands.json`, so
        # `args` is an empty namespace. It stays in the signature because the
        # port is one shape for every command, not one per command.
        del args
        status = app.dispatch(
            GetExchangeConnectionStatusQuery, GetExchangeConnectionStatusQuery()
        )
        print(format_exchange_connection_status(status))
