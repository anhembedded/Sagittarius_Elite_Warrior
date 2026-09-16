"""`strategy` as one Engine extension — the Core domain (ADR D1, HLD §3.2, §3.4).

This is the only file under `modules/strategy/` that `shell/` may import
(`is_module_entry_point` in the boundary guard). `shell/modules.py` lists the
class; `shell/module_registration.py` instantiates it and hands it to
`app.use()`.

**The context's one question:** *given what the market just did, should this
account be long, short, or out — and by how much?* The strategies themselves,
the registry that names them, the engine that runs one over a candle, the live
session that holds an armed strategy per symbol, and arming and disarming. How
an order actually reaches the venue is `trading`'s, and this context asks for it
through `trading/contracts/IOrderSubmission`.

@par Why it is the Core domain and separate from `trading`
ADR D1, and `BUG-112` is what it cost to keep them merged: a defect in how a
position was read broke how a signal was acted on, because one module owned
both. The two have a direction — HLD §02's Customer/Supplier — and it runs one
way only: `strategy` consumes `trading`, never the reverse. `EPIC-025C` §2's
first done-when is that `modules/trading` imports **nothing** from here, not
even `contracts/`, and PR 2.1a is what made that true: the `SignalAction →
OrderIntent` table had been sitting in `trading/domain/policies/` although
nothing in that module called it, so it came here with its two callers and
`trading` stopped naming `SignalAction` at all.

@par `register()` binds nothing yet, and that is a statement
Like `trading` at PR 1.3a, this module arrives as a **move**: the code is here,
the container bindings are not. `binance_bot_module.py` still registers the
strategy registry, the live session, the config store and the two handlers,
which costs no boundary violation because the boundary scan skips that file by
name (`tests/unit/architecture/boundaries/scan.py`) — it *is* the composition
root the strangler is replacing, and it shrinks by one phase at a time.

They move in when there is a port to bind them behind, which is PR 2.1c's
`IStrategyCatalog`. Binding them here first would mean this module resolving
types its consumers still reach for directly, and `register()` may not resolve
(SDD §4) — so the order is the same one `market_data` and `trading` both
followed: move, publish, then move the consumers.

@par `contribute()`, `declare_cli()` and `subscribe()` are not implemented
Each absence is a measurement, not an omission:

  · **no contribution** — the strategy card, the last-signal card and the
    parameters dialog are `EPIC-025C` §1 item 4, and they are still
    `presentation/ui/components/strategy_params` and `strategy_overlay`, which
    need `BaseStrategy` from *this* module and therefore could not move before
    it existed. PR 2.1e brings them.
  · **no CLI command** — `trade-once` is a strategy run and reads as this
    context's, but it is declared by nobody today: `presentation/cli/` still
    parses it and `shell/cli_registry.py` collects what modules declare
    (PR 1.3c-5). Moving it is a behaviour question about one command's
    ownership rather than a rider on a move.
  · **no Qt subscription** — `signal_feed` and `StrategyArmingCoordinator` are
    Qt objects still under `presentation/ui/common/`, and they travel with the
    widgets in PR 2.1e.
"""

from __future__ import annotations

import logging
from typing import Any

from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)

logger = logging.getLogger("App.StrategyModule")


class StrategyModule(BoundedContextModule):
    """The strategies, the engine that runs them, and the live armed session."""

    module_id = "strategy"

    #: `trading`, and checked: `test_module_declarations.py` reads the imports
    #: actually present under `modules/strategy/` and fails on both surplus and
    #: shortfall. This context is the **customer** in its one relationship —
    #: it reads `trading/contracts/` for `IOrderSubmission`, `ITradingSession`,
    #: `IMarketMetadataProvider`, `ITradingAccountReader` and `PositionSide` —
    #: and `market_data` reaches it the other way round, through the bus, so no
    #: dependency on that module appears here.
    dependencies: list[str] = ["trading"]  # noqa: RUF012 — the Engine reads a plain attribute

    def register(self, context: Any) -> None:
        """Nothing, yet — see this module's docstring for why the bindings are
        still `binance_bot_module.py`'s and which pull request moves them.

        Deliberately not `pass` with no words: an empty `register()` is the one
        shape a reader cannot tell apart from a forgotten one.
        """
        logger.debug(
            "[STRATEGY] register(): no bindings yet — binance_bot_module.py still "
            "holds them until IStrategyCatalog is published (EPIC-025C, PR 2.1c)."
        )
