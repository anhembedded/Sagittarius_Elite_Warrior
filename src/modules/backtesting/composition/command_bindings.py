"""backtesting's write side: the two commands the Backtest screen dispatches.

`EPIC-025E` PR 4.4f-1 — the first of `binance_bot_module.py`'s remaining
bindings to move into its own module, following the same one-port-at-a-time
pattern PRs 2.1c/2.1d/3.1b already used to dissolve the rest of that strangler
root. `module.py`'s own docstring argued against moving this binding *for its
own sake* while the dispatcher and the screen both stayed put — that objection
no longer holds once the destination is deleting the composition root itself,
which is what `binance_bot_module.py` deleted last (4.4f-4) actually needs.

`bind` (transient), matching every other command handler in this codebase: a
handler holds the state of the one run it is executing, and two concurrent
backtests must not share it.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.backtesting.application.run_historical_tick_backtest import (
    RunHistoricalTickBacktestCommand,
    RunHistoricalTickBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.application.run_static_backtest import (
    RunStaticBacktestCommand,
    RunStaticBacktestCommandHandler,
)
from sagittarius_engine.interfaces.i_container import IContainer


def bind_commands(container: IContainer) -> None:
    """Route each backtesting command type to the handler that executes it."""
    container.bind(RunStaticBacktestCommand, RunStaticBacktestCommandHandler)
    container.bind(
        RunHistoricalTickBacktestCommand, RunHistoricalTickBacktestCommandHandler
    )
