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

@par `register()` binds the published ports, and only those
PR 2.1b brought the code with no bindings at all; **PR 2.1c binds the one port
it publishes** — `IArmedStrategy`, what is armed right now — onto the single
`LiveStrategySession` that `binance_bot_module.py` already registers.
`composition/port_bindings.py` explains why that is a lambda rather than
construction: a second session built here would give the screens an armed state
the tick path never drives, which is the class of bug the
`ExchangeSessionFactory` split took four pull requests to leave behind.

`IStrategyCatalog` is **not** here, and that is a measurement rather than an
omission — see `EPIC-025C` §5. Every caller that would read it also needs the
strategy *classes*, to construct one for the chart overlay or to hand to
`build_engine()`, and a published contract must not carry a domain type. All of
those callers become intra-module in PR 2.1e, which is where the port is worth
writing.

**PR 2.1d publishes the second port, `ISizingPolicy`** (ADR D17) — how much
capital one order may use — and binds **nothing**, on purpose. Its consumers
hold it rather than resolve it: `PaperExchange` takes it as a constructor
parameter, and this module's own `position_sizing_bridge` constructs the one
implementation directly, because a sizing rule is a domain policy and not a
collaborator with a lifecycle. A container binding nothing resolves is the dead
wiring `BUG-120` was; it arrives in Phase 3 with `backtesting`, which will
resolve it (`EPIC-025D`).

Everything else is still that strangler root's: the registry itself, the live
session, the factory, the config store and the two command handlers. It costs no
boundary violation because the boundary scan skips that file by name
(`tests/unit/architecture/boundaries/scan.py`) — it *is* the composition root
the strangler is replacing. They were scheduled to move in PR 2.1d, on the
expectation that `ISizingPolicy` would pass through `LiveStrategyFactory`'s
arguments; measured, it does not touch them at all, so the move travels with
PR 2.1e, where the strategy card and the chart overlay give it a reason.

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

from typing import Any

from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.composition.port_bindings import (
    bind_published_ports,
)


class StrategyModule(BoundedContextModule):
    """The strategies, the engine that runs them, and the live armed session."""

    module_id = "strategy"

    #: `trading`, and checked: `test_module_declarations.py` reads the imports
    #: actually present under `modules/strategy/` and fails on both surplus and
    #: shortfall. This context is the **customer** in its one relationship —
    #: it reads `trading/contracts/` for `IOrderSubmission`, `ITradingSession`,
    #: `IMarketMetadataProvider`, `ITradingAccountReader`, `PositionSide` and
    #: (since PR 2.1d) `OrderQuantityRoundingPolicy`, the exchange's lot filter
    #: ADR D17 leaves on trading's side of the sizing line —
    #: and `market_data` reaches it the other way round, through the bus, so no
    #: dependency on that module appears here.
    dependencies: list[str] = ["trading"]  # noqa: RUF012 — the Engine reads a plain attribute

    def register(self, context: Any) -> None:
        """The one published port, and only that (PR 2.1c).

        The adapter and handler registrations still live in
        `binance_bot_module.py` — see this module's docstring for why, and for
        the pull request that moves them. This one needs nothing but the
        container, and the lambda behind it resolves lazily, so the published
        surface can be bound from inside the module while its internals wait.
        """
        bind_published_ports(context.container)
