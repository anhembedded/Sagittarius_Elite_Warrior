from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_exchange_connection_status import (
    GetExchangeConnectionStatusQuery,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.exchange_status_formatter import (
    format_exchange_connection_status,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.handlers.i_cli_command_handler import (
    ICliCommandHandler,
)
from sagittarius_engine import App


class ExchangeStatusCliHandler(ICliCommandHandler):
    """`EPIC-021D` — interactive-shell counterpart to
    `exchange_status_cmd.execute_exchange_status`; both share
    `format_exchange_connection_status` so their output never drifts."""

    @staticmethod
    def handle(arg_str: str, app: App) -> None:
        status = app.dispatch(
            GetExchangeConnectionStatusQuery, GetExchangeConnectionStatusQuery()
        )
        print(format_exchange_connection_status(status))
