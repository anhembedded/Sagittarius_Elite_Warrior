import argparse

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import CliOutcome
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_command_handler import (
    ICliCommandHandler,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.exchange_status_cmd import (
    execute_exchange_status,
)
from sagittarius_engine import App


class ExchangeStatusCliHandler(ICliCommandHandler):
    """`EPIC-021D` — interactive-shell counterpart to
    `exchange_status_cmd.execute_exchange_status`; both are the same function,
    so their output never drifts (`EPIC-038B`: it also means `--json` and
    `--format` work at the prompt, instead of being accepted and ignored)."""

    @staticmethod
    def handle(args: argparse.Namespace, app: App) -> CliOutcome | None:
        return execute_exchange_status(app, args)
