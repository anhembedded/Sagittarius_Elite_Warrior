from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.sync.sync_market_data import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.cli.failure_exit_code import (
    failure_exit_code,
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


def execute_sync(app: App, args) -> CliOutcome | None:
    """Sync history; `None` on success.

    `EPIC-038B` — a failure is a returned outcome, not a `sys.exit(1)` in the
    middle of the command: a request the command rejects is `USAGE`, an
    exchange or network failure is `EXCHANGE`, anything else `ERROR`.
    """
    symbols_list = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    try:
        timeframe = TimeFrame(args.interval)
    except ValueError:
        print(
            f"Invalid interval: {args.interval}. Must be one of {[t.value for t in TimeFrame]}"
        )
        return CliOutcome(ExitCode.USAGE)

    # `EPIC-027A` — see `sync_cli_handler.py`'s identical comment: no
    # `--market` flag yet, pinned to Spot.
    command = SyncMarketDataCommand(
        symbols=symbols_list,
        interval=timeframe,
        market=MarketType.SPOT,
        days_back_if_empty=args.days,
    )

    # Dispatch to Application Layer
    try:
        app.container.resolve(ICommandDispatcher).dispatch(
            SyncMarketDataCommand, command
        )
    except Exception as e:  # noqa: BLE001 - CLI boundary: report the real failure instead of an uncaught traceback
        print(f"❌ Sync failed: {e}")
        return CliOutcome(failure_exit_code(e))
    return None
