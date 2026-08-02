from typing import Optional

from sagittarius_engine import App
from sagittarius_engine.interfaces.i_engine_context import IEngineContext
from sagittarius_engine.interfaces.i_task_manager import ITaskHandle
from sagittarius_engine.runtime.hosted.hosted_service import IHostedService
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

from Binace_Bot.src.presentation.cli.handlers.sync_handler import SyncMenuHandler
from Binace_Bot.src.presentation.cli.handlers.stream_handler import (
    StartStreamMenuHandler,
    StopStreamMenuHandler,
)


class TerminalMenuService(IHostedService):
    """
    @brief Interactive Terminal Menu Hosted Service.
    @details Spawns a background thread for a while-loop UI so the main Engine event loop is not blocked.
    """

    def __init__(self, app: App):
        self.app = app
        self.token = CancellationToken()
        self.task: Optional[ITaskHandle] = None

        # Router mapping keys to handlers to avoid God Object
        self.handlers = {
            "1": SyncMenuHandler(),
            "2": StartStreamMenuHandler(),
            "3": StopStreamMenuHandler(),
        }

    def start(self, context: IEngineContext) -> None:
        # Spawn non-blocking background task for CLI user interaction loop
        self.task = context.tasks.spawn(
            self._run_loop, name="TerminalMenuUI", token=self.token
        )

    def stop(self, context: IEngineContext) -> None:
        self.token.cancel()

    def wait_for_exit(self) -> None:
        """
        @brief Blocks main thread until CLI execution finishes or user exits.
        """
        if self.task and self.task.future:
            try:
                self.task.future.result()
            except Exception:
                pass

    def _run_loop(self, token: CancellationToken) -> None:
        while not token.is_cancelled():
            self._print_header()
            print("1. Sync Market Data (Historical)")
            print("2. Start Live Stream (Websocket)")
            print("3. Stop Live Stream")
            print("4. Exit")
            print()

            try:
                choice = input("Select an option: ").strip()
            except (EOFError, KeyboardInterrupt):
                # Safely exit if user Ctrl+C during input block
                print("\nGracefully shutting down...")
                break

            if not choice:
                continue

            if choice == "4":
                print("Goodbye!")
                break

            handler = self.handlers.get(choice)
            if handler:
                handler.handle(self.app)
            else:
                print("❌ Invalid selection. Please choose a valid option.")

            try:
                input("\nPress Enter to continue...")
            except (EOFError, KeyboardInterrupt):
                break

    def _print_header(self) -> None:
        print("\n" + "=" * 40)
        print(" 🤖 BINANCE TRADING BOT - INTERACTIVE ")
        print("=" * 40)
