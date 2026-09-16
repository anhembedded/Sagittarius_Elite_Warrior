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

@par `ui/` since PR 2.1e — this context's own display code
Eleven files: `strategy_arming_coordinator` (the arm/disarm behaviour),
`signal_feed` (the `SignalGeneratedEvent` normaliser), `strategy_display`,
`strategy_params/` (the parameter form, its fields and its dialog),
`strategy_overlay/` (the chart's indicator lines and trend zones), and
**`strategy_card_view_model`** — which is the one file that was not a move.
`TradingViewModel` and `DashboardViewModel` each carried the card's *nineteen*
members, identical name for name, with a note saying they could not be shared
because Shiboken forbids inheriting Qt `Property`/`Signal` from two `QObject`
bases. True of inheritance; composition was always available, and the Backtest
screen had been using it since `EPIC-003F2`. Extracting it took the duplicated-
member census **132 → 115** and the Phase 1 pair **59 → 39** — the first fall in
that number since `PRO-004` measured it.

@par `boot()` owns the live tick path since PR 2.1c-2
`MarketTickEventHandler` moved out of `src/application/event_handlers/
market_data/` — a folder name was the only market-data thing about it — and the
subscription `binance_bot_module.boot()` used to make is this module's now. It
is the last coded step of Phase 2, and it emptied `src/application/
event_handlers/` entirely: what is left under `src/application/` is the four
backtest use cases, which are Phase 3's. `boot()`'s own docstring carries why
the raw bus rather than the `subscribe(bridge)` hook, and it is a measurement
about threading, not a preference.

@par `contribute()`, `declare_cli()` and `subscribe()` are still not implemented
Each absence is a measurement, not an omission:

  · **no contribution** — the card's *state* is this module's since PR 2.1e; the
    card's *widget* is still built twice, once in `TradingView` and once in
    `DevBoardPanel`, under identical object names. `EPIC-025C` §1 item 4 makes
    one contributed widget of them, and it is a rewrite with two deletions
    rather than a move: ADR D18 wants an assertion inventory first, and §2's
    done-when wants the user on Testnet. It travels with the screens.
  · **no `declare_cli()`, and `trade-once` still does not need one** —
    `modules/strategy/cli/{trade_once_cmd,trade_once_formatter}.py` since PR
    2.1g, imported by `main.py` exactly as `modules/market_data/cli/
    {sync,stream}_cmd.py` have been since PR 0.4a-2. `declare_cli()` was read
    before assuming otherwise: `ICliRegistry` is the **interactive shell**'s,
    and `trade-once` has never been one of its commands — it is an argparse
    subcommand, and `main.py` dispatches those. So this absence is now about a
    registry this context has nothing to put in, which is a different statement
    from the one that stood here before.
  · **no `subscribe()`** — and PR 2.1c-2 read the hook before using it. Two
    things are true of it: **no code path calls it** (the composition root
    calls `declare_cli()`, the entry point calls `contribute()`, and nothing
    calls this one — the state `contribute()` was in before PR 1.4c-4), and the
    `QtEventBridge` it hands over would be the wrong mechanism for the tick
    path anyway, because that bridge marshals onto the Qt main thread and the
    headless entry point has no Qt. `signal_feed` is the subscription that
    genuinely wants it, being a Qt normaliser — but the Presenter that owns its
    lifetime is still a legacy screen, and a feed subscribed here while a
    screen still constructs one would put two normalisers on one event. So the
    hook stays unimplemented, and whether it should exist at all is a question
    for the pull request that moves the screens.
"""

from __future__ import annotations

from typing import Any

from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.event_handlers.market_tick_event_handler import (
    MarketTickEventHandler,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_session import (
    LiveStrategySession,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.composition.port_bindings import (
    bind_published_ports,
)


class StrategyModule(BoundedContextModule):
    """The strategies, the engine that runs them, and the live armed session."""

    module_id = "strategy"

    #: Checked, not declared by hand: `test_module_declarations.py` reads the
    #: imports actually present under `modules/strategy/` and fails on both
    #: surplus and shortfall — which is how `market_data` got here. It reads
    #: `trading/contracts/` for `IOrderSubmission`, `ITradingSession`,
    #: `IMarketMetadataProvider`, `ITradingAccountReader`, `PositionSide`,
    #: `OrderQuantityRoundingPolicy` (PR 2.1d) and the four limit types
    #: (PR 2.1g), as the **customer** in that Customer/Supplier pair.
    #:
    #: `market_data` arrived with PR 2.1g and corrects a sentence this comment
    #: used to carry: *"`market_data` reaches it the other way round, through
    #: the bus, so no dependency on that module appears here"*. True of the
    #: tick path — `MarketTickEvent` is published, not called, and PR 2.1c-2's
    #: subscription names the event type without calling into that module —
    #: and false since
    #: `trade-once` moved in: that command asks `IHistoricalKlines` for the
    #: candles it evaluates a strategy against, which is a direct read of
    #: another module's contract. HLD §02 has it as the expected direction
    #: (`market_data → strategy`, Open Host Service), so what was missing was
    #: the declaration, not the permission.
    dependencies: list[str] = ["market_data", "trading"]  # noqa: RUF012 — the Engine reads a plain attribute

    #: The tick subscriber, held for the life of the module instance
    #: (PR 2.1c-2). `bus.on()` alone would keep it alive through the bound
    #: method it registered — a lifetime nobody reading this file could see,
    #: which is the objection `composition_root.py` records against exactly
    #: that shape for `SystemFailureLog`. `RegisteredModules` holds this
    #: instance, so the chain from the container to the subscriber is
    #: readable in one direction.
    _tick_handler: MarketTickEventHandler | None = None

    def register(self, context: Any) -> None:
        """The one published port, and only that (PR 2.1c).

        The adapter and handler registrations still live in
        `binance_bot_module.py` — see this module's docstring for why, and for
        the pull request that moves them. This one needs nothing but the
        container, and the lambda behind it resolves lazily, so the published
        surface can be bound from inside the module while its internals wait.
        """
        bind_published_ports(context.container)

    def boot(self, context: Any) -> None:
        """Subscribe the live tick path — this context's own since PR 2.1c-2.

        `MarketTickEventHandler` used to live in
        `src/application/event_handlers/market_data/` and be subscribed by
        `binance_bot_module.boot()`. It reads one thing from `market_data`
        (the published `MarketTickEvent`) and drives one thing, this module's
        `LiveStrategySession` — so it is this module's subscriber, and its own
        docstring carries the measurement.

        @par Why `boot()` and the raw bus, not the `subscribe(bridge)` hook
        `BoundedContextModule` declares `subscribe(bridge: QtEventBridge)`
        "after `contribute()`", and it was read before being used rather than
        assumed to be the door — the mistake PR 2.1g caught with
        `declare_cli()`. Two measurements say it is the wrong one here:

          · **nothing calls it.** No code path in `src/` or `scripts/` invokes
            `subscribe()` on a module; the composition root calls
            `declare_cli()` and the entry point calls `contribute()`. It is a
            hook in the same state `contribute()` was in before PR 1.4c-4.
          · **`QtEventBridge` would change what this path does.** It marshals
            every payload onto the Qt main thread and needs a `QApplication`.
            This handler runs the strategy engine and submits orders on the
            websocket thread that delivered the candle, and the headless entry
            point (`main.py sync`/`stream`) has no Qt at all. Bridging it would
            move live order submission onto the GUI thread — a behaviour
            change, in a pull request whose done-when is "exactly as before".

        So this is `boot()`: after every module registered, so
        `LiveStrategySession` resolves, and on the same bus with the same
        threading the tick path has always had.

        @par No `shutdown()` counterpart
        A subscription holds no OS resource — unlike `market_data`'s SQLite
        engines and exchange client, which is why that module has one. The bus
        is the `App`'s, created beside it in `composition_root.py` and gone
        when it is, so an `off()` here would release nothing that outlives the
        process.
        """
        self._tick_handler = MarketTickEventHandler(
            context.container.resolve(LiveStrategySession)
        )
        context.event_bus.on(MarketTickEvent, self._tick_handler.handle)
