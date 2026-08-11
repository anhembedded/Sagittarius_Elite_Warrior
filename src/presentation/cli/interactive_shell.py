import cmd
import logging
import shlex

from Sagittarius_Elite_Warrior.src.presentation.cli.handlers.stream_cli_handler import StreamCliHandler
from Sagittarius_Elite_Warrior.src.presentation.cli.handlers.sync_cli_handler import SyncCliHandler
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
        self.handlers = {"sync": SyncCliHandler, "stream": StreamCliHandler}

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
        """Dynamic routing based on JSON configuration."""
        if not line:
            return

        args = shlex.split(line)
        cmd_name = args[0]

        cli_commands = self.config.get("CLI_COMMANDS", {})

        if cmd_name in cli_commands and cmd_name in self.handlers:
            handler = self.handlers[cmd_name]
            handler.handle(" ".join(args[1:]), self.app)
        else:
            print(f"*** Unknown syntax: {line}")

    def do_help(self, arg: str) -> None:
        """Dynamically builds help texts from configuration."""
        cli_commands = self.config.get("CLI_COMMANDS", {})

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
            from Sagittarius_Elite_Warrior.src.presentation.cli.cli_parser import build_handler_parser

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
