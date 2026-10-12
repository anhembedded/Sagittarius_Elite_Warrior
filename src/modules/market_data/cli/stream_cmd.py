import time
from typing import cast

from binance.exceptions import BinanceAPIException, BinanceRequestException
from pydantic import ValidationError
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.start_live_stream import (
    StartLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.start_live_stream.command import (
    StartLiveStreamResponse,
)
from sagittarius_engine import App

#: `EPIC-025` PR 0.4a-2: module code dispatches through **this application's own**
#: `ICommandDispatcher` port, not the Engine's `App.dispatch`.
#:
#: Not a style preference, and not mypy appeasement. Two reasons, in order:
#:
#: 1. `architecture-rule.md` (`EPIC-008F`): code inside a bounded context talks
#:    to the Engine only through this app's ports. That rule applied to these
#:    files the moment they became module code instead of `presentation/` code.
#: 2. The Engine annotates `App.dispatch(handler_class: type[IDispatchable])`,
#:    meaning the *handler* type — but this app registers `bind(CommandType,
#:    HandlerType)` and passes the **command** type as the container key. Both
#:    are self-consistent; the annotations are not. `ICommandDispatcher.dispatch`
#:    takes a plain `type` and its docstring says so explicitly, so the app's own
#:    port is the one that describes what the app actually does.
#:
#: mypy never saw the mismatch before because every caller lived under
#: `src/presentation/`, which the gate excludes wholesale for an unrelated
#: PySide6 reason. Moving two files out of that directory is what surfaced it.


def execute_stream(app: App, args) -> CliOutcome | None:
    """
    Executes the stream command.
    The actual WebSocket streaming is managed by the LiveStreamExtension's HostedService.
    This function simply blocks the main thread to keep the application alive.

    `EPIC-038B` — returns the outcome of *starting*: `None` once the stream was
    started and the operator interrupted it, otherwise the code the failure
    deserves (an unusable request is `USAGE`, the exchange `EXCHANGE`, a refusal
    or anything else `ERROR`).
    """
    symbols_list = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    try:
        timeframe = TimeFrame(args.interval)
    except ValueError:
        print(
            f"Invalid interval: {args.interval}. Must be one of {[t.value for t in TimeFrame]}"
        )
        return CliOutcome(ExitCode.USAGE)

    # `EPIC-027A` — the CLI has no market option; it streams Spot, as it always has.
    cmd = StartLiveStreamCommand(
        owner="cli",
        market_type=MarketType.SPOT,
        symbols=symbols_list,
        interval=timeframe,
    )
    # `dispatch` returns `object`, deliberately: one port serves every command,
    # so it cannot know this one's response type. The cast is sound because the
    # caller chose the command, and `StartLiveStreamCommandHandler` declares
    # `ICommandHandler[StartLiveStreamCommand, StartLiveStreamResponse]`. The
    # cast disappears when the port becomes generic over that declared response
    # — a `core/` change with its own pull request, not this one's.
    try:
        response = cast(
            StartLiveStreamResponse,
            app.container.resolve(ICommandDispatcher).dispatch(
                StartLiveStreamCommand, cmd
            ),
        )
    except Exception as e:  # noqa: BLE001 - CLI boundary: report the real failure instead of an uncaught traceback
        print(f"❌ Failed to start stream: {e}")
        return CliOutcome(_failure_code(e))

    if not response.success:
        print(f"Failed to start stream: {response.message}")
        return CliOutcome(ExitCode.ERROR)

    print(
        f"Live stream started for {symbols_list} at {timeframe.value} in the background. Press Ctrl+C to stop."
    )
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nReceived KeyboardInterrupt. Shutting down gracefully...")
    return None


def _failure_code(error: Exception) -> ExitCode:
    """A request the command rejects is `USAGE`, an exchange or network failure
    is `EXCHANGE`, anything else `ERROR`."""
    if isinstance(error, ValueError | ValidationError):
        return ExitCode.USAGE
    if isinstance(
        error, BinanceAPIException | BinanceRequestException | RequestException
    ):
        return ExitCode.EXCHANGE
    return ExitCode.ERROR
