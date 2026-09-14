import argparse
import cmd
import logging
import shlex

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_command_handler import (
    ICliCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.cli.stream_cli_handler import (
    StreamCliHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.cli.sync_cli_handler import (
    SyncCliHandler,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.cli_parser import (
    build_handler_parser,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.handlers.exchange_status_cli_handler import (
    ExchangeStatusCliHandler,
)
from sagittarius_engine import App
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_engine_context import IEngineContext
from sagittarius_engine.interfaces.i_task_manager import ITaskHandle
from sagittarius_engine.runtime.hosted.hosted_service import IHostedService

logger = logging.getLogger("App.InteractiveShell")


class InteractiveShell(cmd.Cmd, IHostedService):
    """
    @brief Modular REPL Shell for the Binance Bot.
    @details Implements Python's cmd.Cmd and runs as a Sagittarius IHostedService.
             It routes commands dynamically based on CLI_COMMANDS json config.
    """

    intro = "\n========================================\n 🤖 BINANCE TRADING BOT - INTERACTIVE \n========================================\nType 'help' or '?' to list commands.\n"
    prompt = "🤖 binance-bot> "

    def __init__(self, app: App):
        super().__init__()
        self.app = app
        self.task: ITaskHandle | None = None
        self.config = app.container.resolve(IConfig)

        # Hardcode the routing map to handlers.
        # (A true registry would inject this, but this is a simple implementation)
        self.handlers: dict[str, type[ICliCommandHandler]] = {
            "sync": SyncCliHandler,
            "stream": StreamCliHandler,
            "exchange-status": ExchangeStatusCliHandler,
        }

    def start(self, context: IEngineContext) -> None:
        self.task = context.tasks.spawn(self._run_loop, name="InteractiveShell")

    def stop(self, context: IEngineContext) -> None:
        print("\nShutting down interactive shell...")

    def wait_for_exit(self) -> None:
        if self.task and self.task.future:
            try:
                self.task.future.result()
            except Exception:
                logger.exception("InteractiveShell task raised during shutdown")

    def _run_loop(self) -> None:
        try:
            self.cmdloop()
        except KeyboardInterrupt:
            print("\nExiting...")

    def default(self, line: str) -> None:
        """Route a typed line to its handler, parsed.

        `EPIC-025` PR 0.4a-2: parsing happens **here**, once, and the handler
        receives an `argparse.Namespace`. Before, this method split the line and
        re-joined the tail into a string, and each handler split it again, built
        its own parser from config and repeated the same three `except` blocks —
        which also meant a handler had to import the parser builder, so a
        command owned by a module could not live in that module.

        Everything argparse answers by itself (`-h`, an unknown flag, a missing
        required argument) is answered before the handler is reached.
        """
        if not line:
            return

        words = shlex.split(line)
        cmd_name = words[0]

        cli_commands = self.config.get(ConfigKeys.CLI_COMMANDS.value, {})
        if cmd_name not in cli_commands or cmd_name not in self.handlers:
            print(f"*** Unknown syntax: {line}")
            return

        parsed = self._parse(cmd_name, words[1:])
        if parsed is None:
            return
        self.handlers[cmd_name].handle(parsed, self.app)

    def _parse(self, cmd_name: str, words: list[str]) -> argparse.Namespace | None:
        """The parsed arguments, or `None` when there is nothing to run.

        `None` covers both "already handled" and "rejected": argparse raises
        `SystemExit` after printing help for `-h`, and would raise it again to
        kill the process on a bad argument — in a REPL that must return to the
        prompt instead, which is what `exit_on_error=False` and this catch are
        for.
        """
        parser = build_handler_parser(self.config, cmd_name)
        try:
            return parser.parse_args(words)
        except SystemExit:
            return None
        except argparse.ArgumentError as exc:
            print(f"❌ Argument Error: {exc}")
            return None

    def do_help(self, arg: str) -> None:
        """Dynamically builds help texts from configuration."""
        cli_commands = self.config.get(ConfigKeys.CLI_COMMANDS.value, {})

        if not arg:
            print("\nDocumented commands (type help <topic>):")
            print("========================================")
            for cmd_name, cmd_config in cli_commands.items():
                help_text = cmd_config.get("help", "No description available")
                print(f"  {cmd_name:<15} {help_text}")
            print(f"  {'exit':<15} Exit the interactive shell")
            print(f"  {'quit':<15} Alias for exit")
            print()
            return

        if arg in cli_commands:
            parser = build_handler_parser(self.config, arg)
            parser.print_help()
        elif arg in ("exit", "quit"):
            print("Exit the interactive shell")
        else:
            print(f"*** No help on {arg}")

    def do_exit(self, arg: str) -> bool:
        """Exit the interactive shell."""
        print("Goodbye!")
        return True

    def do_quit(self, arg: str) -> bool:
        """Alias for exit."""
        return self.do_exit(arg)

    def emptyline(self):
        """Do nothing on empty input line instead of repeating last command."""
