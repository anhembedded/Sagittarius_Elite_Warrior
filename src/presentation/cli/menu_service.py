from typing import Optional

from sagittarius_engine import App
from sagittarius_engine.interfaces.i_engine_context import IEngineContext
from sagittarius_engine.interfaces.i_task_manager import ITaskHandle
from sagittarius_engine.runtime.hosted.hosted_service import IHostedService
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken



import shlex
import argparse
from pydantic import ValidationError

from Binace_Bot.src.presentation.cli.cli_parser import build_parser
from Binace_Bot.src.application.use_cases.sync_market_data import SyncMarketDataCommand
from Binace_Bot.src.application.use_cases.start_live_stream import StartLiveStreamCommand
from Binace_Bot.src.application.use_cases.stop_live_stream import StopLiveStreamCommand
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

class TerminalMenuService(IHostedService):
    """
    @brief Interactive Terminal Menu Hosted Service.
    @details Spawns a background thread for a while-loop UI so the main Engine event loop is not blocked.
    """

    def __init__(self, app: App):
        self.app = app
        self.token = CancellationToken()
        self.task: Optional[ITaskHandle] = None
        self.parser = build_parser()

    def start(self, context: IEngineContext) -> None:
        self.task = context.tasks.spawn(
            self._run_loop, name="TerminalMenuUI", token=self.token
        )

    def stop(self, context: IEngineContext) -> None:
        self.token.cancel()

    def wait_for_exit(self) -> None:
        if self.task and self.task.future:
            try:
                self.task.future.result()
            except Exception:
                pass

    def _run_loop(self, token: CancellationToken) -> None:
        self._print_header()
        
        while not token.is_cancelled():
            try:
                cmd_line = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGracefully shutting down...")
                break

            if not cmd_line:
                continue

            if cmd_line.lower() in ("exit", "quit"):
                print("Goodbye!")
                break
                
            if cmd_line.lower() in ("help", "?"):
                self.parser.print_help()
                continue
                
            try:
                args_list = shlex.split(cmd_line)
                args = self.parser.parse_args(args_list)
                self._execute_command(args)
            except SystemExit:
                # argparse raises SystemExit on -h or invalid args. Catch to keep REPL alive.
                pass
            except argparse.ArgumentError as e:
                print(f"❌ Argument Error: {e}")
            except Exception as e:
                print(f"❌ Error: {e}")

    def _execute_command(self, args) -> None:
        if args.command == "sync":
            symbols = [s.strip().upper() for s in args.symbols.split(",")]
            try:
                cmd = SyncMarketDataCommand(
                    symbols=symbols,
                    interval=TimeFrame(args.interval),
                    days_back_if_empty=args.days
                )
                print(f"🔄 Syncing historical data for {symbols}...")
                response = self.app.dispatch(SyncMarketDataCommand, cmd)
                if response.success:
                    print(f"✅ Sync complete.")
                else:
                    print(f"❌ Sync failed: {response.message}")
            except ValueError as e:
                print(f"❌ Validation Error: {e}")
            except ValidationError as e:
                print(f"❌ Validation Error: {e}")

        elif args.command == "stream":
            symbols = [s.strip().upper() for s in args.symbols.split(",")]
            try:
                cmd = StartLiveStreamCommand(
                    symbols=symbols, interval=TimeFrame(args.interval)
                )
                response = self.app.dispatch(StartLiveStreamCommand, cmd)
                if response.success:
                    print(f"✅ Live stream started for {symbols} at {args.interval} in the background.")
                else:
                    print(f"❌ Failed to start stream: {response.message}")
            except ValueError as e:
                print(f"❌ Validation Error: {e}")
            except ValidationError as e:
                print(f"❌ Validation Error: {e}")
                
        elif args.command == "stop-stream":
            cmd = StopLiveStreamCommand()
            response = self.app.dispatch(StopLiveStreamCommand, cmd)
            if response.success:
                print(f"✅ Live stream stopped.")
            else:
                print(f"❌ Failed to stop stream: {response.message}")
        else:
            self.parser.print_help()

    def _print_header(self) -> None:
        print("\n" + "=" * 40)
        print(" 🤖 BINANCE TRADING BOT - INTERACTIVE ")
        print("=" * 40)
        print("\nType 'help' for available commands, or 'exit' to quit.")
