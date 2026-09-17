"""`backtesting` as one Engine extension (ADR D1, HLD §3.2, §3.4).

This is the only file under `modules/backtesting/` that `shell/` may import
(`is_module_entry_point` in the boundary guard). `shell/modules.py` lists the
class; `shell/module_registration.py` instantiates it and hands it to
`app.use()`.

**The context's one question:** *if this strategy had been running over this
history, what would have happened?* The paper broker that fills orders against
candles, the fee, margin and matching policies that decide how, the two runners
(static and historical-tick), and the answer they produce — a `BacktestResult`
with its trades and metrics.

@par Why it is a context of its own, and the least entangled one
ADR D1. It consumes `market_data.contracts` for the candles and
`strategy.contracts` for the engine that decides, and **nothing consumes it**
except the screen that shows its answers. `EPIC-025D` §4 measured that: of the
185 imports the moving code made, 105 were already-permitted reads of `core/`,
`support/` and other modules' `contracts/`, and the only hard refusals were six
reads of `strategy`'s internals — which PR 3.1b retired by publishing
`IStrategyEngine` and binding `ISizingPolicy`.

@par `register()` binds nothing yet, and that is a measurement
Its two command handlers are still bound in `binance_bot_module.py`, the
strangler root the boundary scan skips by name, because they are dispatched
through `ICommandDispatcher` by the Backtest screen — and moving a
*registration* while the dispatcher and the screen both stay put buys nothing
but a second place to look. HLD §3.4 records what closes this properly: *"if a
CLI `backtest` command appears, `IBacktestRunner` is added then"*, which is the
`IMarketDataSync` arc (PR 0.4a moved the code, PR 0.5 published the port and
four consumers stopped building the command).

`ISizingPolicy` is **resolved** here rather than bound — `strategy` owns that
binding (ADR D17), and this module is the consumer PR 3.1b's binding was waiting
for.

@par No `ui/` yet, and the reason is ADR D21 rather than scope
The Backtest screen is 74 files and 12,400 lines, and `EPIC-025D` §4.1 measured
why it could not come with the rest: **29** of its imports name QML packages ADR
D21 **deletes** in Phase 4 rather than moves. Writing those as new lines in a
shrink-only allowlist to hit a number four pull requests early is exactly what
the user refused on 2026-09-16 for Phase 1's two screens
(`DECISION_2026-09-16_the_duplication_criterion_waits.md`), so this screen
travels the same way: it becomes `modules/backtesting/ui/` in Phase 4, as its
eleven QML modals become `QDialog`s and its panels docks.

@par `contribute()`, `declare_cli()`, `subscribe()`: none, and each is measured
  · **no contribution** — nothing to contribute until the screen moves (above).
  · **no `declare_cli()`** — `ICliRegistry` is the *interactive shell*'s, and
    this context has no shell command. A `backtest` argparse subcommand is the
    thing HLD §3.4 says would bring `IBacktestRunner`; it does not exist.
  · **no `subscribe()`** — this module *publishes* `BacktestCompletedEvent` and
    `BacktestFailedEvent` and subscribes to nothing. The hook is also
    uncalled by any code path (PR 2.1c-2 measured that), so implementing it
    would subscribe nothing anyway.
"""

from __future__ import annotations

from typing import Any

from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)


class BacktestingModule(BoundedContextModule):
    """The paper broker, the two runners, and the answer they produce."""

    module_id = "backtesting"

    #: Checked, not declared by hand: `test_module_declarations.py` reads the
    #: imports actually present under `modules/backtesting/` and fails on both
    #: surplus and shortfall.
    #:
    #: `market_data` for the candles (`IMarketDataRepository`); `strategy` for
    #: the engine that decides and the rule that sizes — `IStrategyEngine`,
    #: `IStrategyEngineFactory`, `ISizingPolicy`, `Signal`, `SignalAction`, all
    #: published in Phase 2 and PR 3.1b; `trading` for `PositionSide`, the one
    #: word a paper position and a live one must agree on. HLD §02 has all three
    #: as this context's suppliers, and nothing as its customer — which is why
    #: it is the least entangled phase.
    dependencies: list[str] = ["market_data", "strategy", "trading"]  # noqa: RUF012 — the Engine reads a plain attribute

    def register(self, context: Any) -> None:
        """Nothing yet, deliberately — see this module's docstring.

        The two command handlers stay registered in `binance_bot_module.py`
        until something asks this context a question through a port rather than
        by building its command. A registration moved here while the dispatcher
        and the screen both stay put would be a second place to look for one
        fact, which is the accidental complexity ADR D2 exists to avoid — and a
        binding nothing resolves differently is the dead wiring `BUG-120` was.
        """
