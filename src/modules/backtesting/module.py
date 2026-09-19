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

@par `register()` binds its own two commands — PR 4.4f-1
The two command handlers moved out of `binance_bot_module.py`,
`composition/command_bindings.py` now the one place that answers "what handles
`RunStaticBacktestCommand`/`RunHistoricalTickBacktestCommand`". Earlier
phases deliberately left them there — moving a *registration* while the
dispatcher and the screen both stayed put would have bought nothing but a
second place to look, the accidental complexity ADR D2 exists to avoid. What
changed by Phase 4's 4.4f: the destination is deleting that composition root
entirely, so the binding needs a home regardless, and this module is that
home. HLD §3.4's own note on what closes this *properly* — a CLI `backtest`
subcommand bringing `IBacktestRunner`, the `IMarketDataSync` arc's shape (PR
0.4a moved the code, PR 0.5 published the port) — is unrelated and still
open; nothing about that arc changed here. This is a registration moving to
where it is used, not the port HLD §3.4 describes.

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

@par `contribute()` since `EPIC-025F` PR 5.2 — the Backtest screen itself
The screen moved into `modules/backtesting/ui/` in Phase 4 (`EPIC-025E` PR
4.4d, above) but kept registering through the legacy `AbstractScreenModule`
mechanism (`shell/legacy_screen_adapter.py`) until this pull request:
`backtest_screen()` describes it the way `settings_screen()` describes the
shell's own screen, and needs `container` at view-construction time (which
concrete View this install uses is a named choice read from `IConfig`,
`EPIC-013F`) — `boot()` (added in this pull request, previously this
module's inherited no-op default) stashes it for exactly this call, the
same pattern `trading`'s Dev Board screen uses in the same pull request.
Not `register()`: the `context.container` `register()` receives is
`RegisteringContainer`, a spy that refuses every `resolve()` call forever,
not only during registration (`shell/registering_container.py`'s own
docstring) — a reference captured there and used later, inside a screen's
lazily-run view factory, would raise on a call that has nothing to do with
registration any more.

@par `declare_cli()`, `subscribe()`: still none, and each is still measured
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
from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_registry import (
    IContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.composition.command_bindings import (
    bind_commands,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_screen import (
    backtest_screen,
)
from sagittarius_engine.interfaces.i_container import IContainer


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

    def __init__(self) -> None:
        super().__init__()
        #: Stashed by `boot()`, read by `contribute()`'s `backtest_
        #: screen(self._container)` call (`EPIC-025F` PR 5.2) — see
        #: `boot()`'s own docstring for why it must come from there and not
        #: from `register()`.
        self._container: IContainer | None = None

    def register(self, context: Any) -> None:
        """Binds this module's own two commands — see this module's docstring
        for why this moved now (4.4f-1) rather than earlier."""
        bind_commands(context.container)

    def boot(self, context: Any) -> None:
        """Stashes `container` for `contribute()` — see this module's own
        docstring's `contribute()` section for the full reasoning. Nothing
        else needed starting; this hook was this module's inherited no-op
        default until `EPIC-025F` PR 5.2."""
        self._container = context.container

    def contribute(self, registry: IContributionRegistry) -> None:
        """The Backtest screen — see this module's own docstring."""
        if self._container is None:
            raise RuntimeError("BacktestingModule.contribute() called before boot()")
        registry.contribute_screen(backtest_screen(self._container))
