"""`main.py run [flags]` (`EPIC-038D`): validate the flags, then hand over to `RunCommand`."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import CliOutcome
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_command_handler import (
    ICliCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.signal_sources import (
    default_shutdown_signal_source,
)
from Sagittarius_Elite_Warrior.src.modules.operations.cli.run_command import (
    RunCommand,
)
from Sagittarius_Elite_Warrior.src.modules.operations.cli.run_options import (
    run_options_of,
)

if TYPE_CHECKING:
    from sagittarius_engine import App


class RunCliHandler(ICliCommandHandler):
    """The app is built and not booted (`"owns_lifecycle": true`): `run` boots and stops it."""

    @staticmethod
    def handle(args: argparse.Namespace, app: App) -> CliOutcome | None:
        options = run_options_of(args)
        if isinstance(options, CliOutcome):
            return options
        return RunCommand(app, options, default_shutdown_signal_source()).execute()
