"""`stream start` / `stream stop` at the interactive prompt."""

from __future__ import annotations

import argparse
from typing import cast

from pydantic import ValidationError
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_command_handler import (
    ICliCommandHandler,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.start_live_stream import (
    StartLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.start_live_stream.command import (
    StartLiveStreamResponse,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.stop_live_stream import (
    StopLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.stop_live_stream.command import (
    StopLiveStreamResponse,
)
from sagittarius_engine import App

#: The stream owner the CLI claims. A *namespace*, not an exclusive lease
#: (`Docs/VOCABULARY`): a stream started here replaces an earlier CLI stream and
#: leaves a screen's own stream alone.
_CLI_OWNER = "cli"


class StreamCliHandler(ICliCommandHandler):
    """Turns a parsed `stream` line into a start or stop command."""

    @staticmethod
    def handle(args: argparse.Namespace, app: App) -> None:
        # `action` is a required subcommand in `cli_commands.json`, but a
        # `required=False` subparser yields `None` rather than failing, so a
        # bare `stream` still reaches here — answer it with help, not a
        # traceback.
        action = getattr(args, "action", None)
        if not action:
            print("Usage: stream start --symbols <list> --interval <tf> | stream stop")
            return

        if action == "start":
            StreamCliHandler._start(args, app)
        elif action == "stop":
            StreamCliHandler._stop(app)

    @staticmethod
    def _start(args: argparse.Namespace, app: App) -> None:
        symbols = [s.strip().upper() for s in args.symbols.split(",")]
        try:
            cmd = StartLiveStreamCommand(
                owner=_CLI_OWNER, symbols=symbols, interval=TimeFrame(args.interval)
            )
            # Through this app's port, not `App.dispatch` — see
            # `sync_cli_handler.py` for why. The cast is sound because this
            # caller chose the command and the handler declares
            # `ICommandHandler[StartLiveStreamCommand, StartLiveStreamResponse]`;
            # it goes away when the port becomes generic over that response.
            response = cast(
                StartLiveStreamResponse,
                app.container.resolve(ICommandDispatcher).dispatch(
                    StartLiveStreamCommand, cmd
                ),
            )
            if response.success:
                print(
                    f"✅ Live stream started for {symbols} at {args.interval} "
                    "in the background."
                )
            else:
                print(f"❌ Failed to start stream: {response.message}")
        except ValueError as e:
            print(f"❌ Validation Error: {e}")
        except ValidationError as e:
            print(f"❌ Validation Error: {e}")
        except Exception as e:  # noqa: BLE001 - CLI boundary: report the real failure instead of an uncaught traceback
            print(f"❌ Failed to start stream: {e}")

    @staticmethod
    def _stop(app: App) -> None:
        try:
            response = cast(
                StopLiveStreamResponse,
                app.container.resolve(ICommandDispatcher).dispatch(
                    StopLiveStreamCommand, StopLiveStreamCommand(owner=_CLI_OWNER)
                ),
            )
            if response.success:
                print("✅ Live stream stopped.")
            else:
                print(f"❌ Failed to stop stream: {response.message}")
        except Exception as e:  # noqa: BLE001 - CLI boundary: report the real failure instead of an uncaught traceback
            print(f"❌ Failed to stop stream: {e}")
