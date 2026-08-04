import cmd
from typing import Optional

from sagittarius_engine import App
from sagittarius_engine.interfaces.i_engine_context import IEngineContext
from sagittarius_engine.runtime.hosted.hosted_service import IHostedService
from sagittarius_engine.interfaces.i_task_manager import ITaskHandle

from Binace_Bot.src.presentation.cli.handlers.sync_cli_handler import SyncCliHandler
from Binace_Bot.src.presentation.cli.handlers.stream_cli_handler import StreamCliHandler

class InteractiveShell(cmd.Cmd, IHostedService):
    """
    @brief Modular REPL Shell for the Binance Bot.
    @details Implements Python's cmd.Cmd and runs as a Sagittarius IHostedService.
             It routes commands to modular CLI Handlers.
    """
    intro = "\n========================================\n 🤖 BINANCE TRADING BOT - INTERACTIVE \n========================================\nType 'help' or '?' to list commands.\n"
    prompt = "🤖 binance-bot> "

    def __init__(self, app: App):
        # cmd.Cmd is an old-style class in some python versions, but in 3.x it is new-style.
        # Call super().__init__() to initialize it safely.
        super().__init__()
        self.app = app
        self.task: Optional[ITaskHandle] = None

    def start(self, context: IEngineContext) -> None:
        # Run the blocking cmdloop in a background task
        self.task = context.tasks.spawn(self._run_loop, name="InteractiveShell")

    def stop(self, context: IEngineContext) -> None:
        print("\nShutting down interactive shell...")

    def wait_for_exit(self) -> None:
        if self.task and self.task.future:
            try:
                self.task.future.result()
            except Exception:
                pass

    def _run_loop(self) -> None:
        try:
            self.cmdloop()
        except KeyboardInterrupt:
            print("\nExiting...")

    # --- Routing Commands ---
    
    def do_sync(self, arg: str):
        """Synchronize market data from Binance."""
        SyncCliHandler.handle(arg, self.app)

    def do_stream(self, arg: str):
        """Manage live websocket market stream. Use 'start' or 'stop'."""
        StreamCliHandler.handle(arg, self.app)

    def do_exit(self, arg: str) -> bool:
        """Exit the interactive shell."""
        print("Goodbye!")
        return True
        
    def do_quit(self, arg: str) -> bool:
        """Alias for exit."""
        return self.do_exit(arg)
        
    def emptyline(self):
        """Do nothing on empty input line instead of repeating last command."""
        pass
