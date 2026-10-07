"""`market_data` as one Engine extension — the first real module (HLD §3.2).

This is the only file under `modules/market_data/` that `shell/` may import
(`is_module_entry_point` in the boundary guard), and the only place the module's
internals are named from outside its own packages. `shell/modules.py` lists the
class; `shell/module_registration.py` instantiates it, spies on its `register()`
and hands it to `app.use()`.

**The context's one question:** *what has the market done, and what of it do we
have stored?* Fetching candles from Binance, storing them per symbol and
timeframe, reporting gaps and repairing them, opening the live kline stream, and
knowing which symbols exist. Anything that decides what to *do* with a price —
a strategy, an order, a backtest run — belongs to another context and reaches
this one through `contracts/`.

**Why this file is almost empty.** The four binding tables live in
`composition/`, one file each, because they change for different reasons
(`architecture-rule.md` §5 rule 5): the adapters when storage or the exchange
changes, the commands and queries when this module gains a use case, and
`port_bindings.py` when the module's **published** API changes — the only one
of the four whose audience is another bounded context. What is left here is the
module's *identity* — the id, the declared dependencies, and which hooks it
uses — which is exactly what a reader opens this file to find.

**Hooks not implemented, and why:**

- `subscribe()` — the market-tick handler still lives in the legacy tree
  (`application/event_handlers/market_data/`) and moves in Phase 1.

That is a default inherited from `BoundedContextModule`, so the absence is a
statement, not an omission. `contribute()` **is** implemented: one page of
Tools → Options (`EPIC-025E` PR 4.4e, an Options page since `EPIC-033E`), the
Database screen itself since
`EPIC-025F` PR 5.2 (`database_screen()` describes it as a
`ScreenContribution`, retiring the last of
this module's tenancy in `shell/legacy_screen_adapter.py`), and the
Watchlist screen (`BOT-019`) — a second, independent screen this module
contributes, describing multiple tracked symbols at once rather than the
one `ChartCard` Dashboard/Trading each focus on.
"""

from __future__ import annotations

import logging
from typing import Any

from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)
from Sagittarius_Elite_Warrior.src.core.contracts.deferred import Deferred
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_registry import (
    CliCommandDescriptor,
    ICliRegistry,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_registry import (
    IContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_options_section import (
    IOptionsSection,
)
from Sagittarius_Elite_Warrior.src.core.contracts.options_page_contribution import (
    OptionsPageContribution,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.live_stream_adapter import (
    LiveStreamEngineAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.database_manager import (
    DatabaseManager,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.cli.stream_cli_handler import (
    StreamCliHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.cli.sync_cli_handler import (
    SyncCliHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.composition.adapter_bindings import (
    bind_adapters,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.composition.command_bindings import (
    bind_commands,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.composition.port_bindings import (
    bind_published_ports,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.composition.query_bindings import (
    bind_queries,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_venues import (
    IMarketDataVenues,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_commands import (
    data_commands,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.database_screen import (
    DATABASE_ROUTE,
    database_screen,
)

logger = logging.getLogger("App.MarketDataModule")


#: Tools → Options → Market Data (`EPIC-033E`), built when the shell
#: assembles the dialog's pages.
_OPTIONS_PAGE: Deferred[IOptionsSection] = Deferred(
    "Sagittarius_Elite_Warrior.src.modules.market_data.ui.settings.market_data_options_page"
    ":build_market_data_options_page"
)


class MarketDataModule(BoundedContextModule):
    """Market history, the symbol catalog and the live kline stream."""

    module_id = "market_data"

    #: Empty, and checked: `test_module_declarations.py` reads the imports
    #: actually present under `modules/market_data/` and fails on both surplus
    #: and shortfall. This context depends on `core/` (the Published Language)
    #: and on `support/binance_gateway`'s contracts — neither is a module, so
    #: neither appears here. It is the *first* context precisely because it
    #: needs no other one.
    dependencies: list[str] = []  # noqa: RUF012 — the Engine reads a plain attribute

    def register(self, context: Any) -> None:
        container = context.container
        bind_adapters(container)
        bind_commands(container)
        bind_queries(container)
        bind_published_ports(container)

    def contribute(self, registry: IContributionRegistry) -> None:
        """This context's own venue and sync defaults, as a page of Tools →
        Options, and the Database screen. The Watchlist is a panel of the
        Market mode (`EPIC-033H`), which `trading` contributes.

        `EPIC-025E` PR 4.4e: the old monolithic Settings screen knew every
        module's config keys; this section knows only this module's four
        (`EXCHANGE_MARKET_DATA_VENUE`, `DEFAULT_SYMBOLS`, `DEFAULT_INTERVAL`,
        `DEFAULT_SYNC_DAYS`). The page is a `Deferred` (`_OPTIONS_PAGE`), so
        no widget module is imported until the shell builds the dialog's pages.

        `EPIC-025F` PR 5.2: `database_screen()` needs no `container` at
        contribute time — `DataManagementView()` takes none — unlike
        `trading`'s two screens in the same pull request.
        """
        registry.contribute_options_page(
            OptionsPageContribution(
                contributor_id=self.module_id,
                order=20,
                factory=_OPTIONS_PAGE,
            )
        )
        registry.contribute_screen(database_screen())
        # `EPIC-033D` — the Data mode's commands.
        for command in data_commands(DATABASE_ROUTE):
            registry.contribute_command(command)

    def declare_cli(self, registry: ICliRegistry) -> None:
        """`sync` and `stream` are this context's commands, so this context
        names their handlers (`EPIC-025` PR 1.3c-5).

        Before this, `interactive_shell.py` held a dict literal naming both
        classes — two boundary-allowlist entries for a shell reaching into a
        module, which PR 1.1b tried to fix by moving the shell instead and
        measured that it only traded them for two lines on another
        shrink-only baseline. Declaring is the inversion that costs nothing:
        the shell names no module class, and adding a command touches the one
        module that owns it.
        """
        for name, handler in (("sync", SyncCliHandler), ("stream", StreamCliHandler)):
            registry.declare(
                CliCommandDescriptor(
                    name=name, handler=handler, contributor_id=self.module_id
                )
            )

    def boot(self, context: Any) -> None:
        """Hand the live-stream adapter to the Engine's lifecycle.

        `LiveStreamEngineAdapter` is a hosted service, not a thread this module
        starts itself: registering it here is what gives it the `EngineContext`
        and gets it stopped on shutdown, while the pure `ILiveStreamService`
        behind it stays free of any Engine type. Registering is not opening —
        the websocket connects only when `StartLiveStreamCommand` asks, so
        booting the app costs no request weight for a screen nobody opened.
        """
        context.hosted_services.register(
            context.container.resolve(LiveStreamEngineAdapter)
        )

    def shutdown(self, context: Any) -> None:
        """Close what holds an OS resource: the SQLite engines and the client.

        `dispose_all()` is not optional bookkeeping — an undisposed SQLAlchemy
        engine keeps its connection pool open, which is what
        `ResourceWarning`s in the gate's log come from, and the gate greps for
        exactly that string.

        The exchange client is closed inside `try`/`except` because a shutdown
        path that raises turns a clean exit into a stack trace the user cannot
        act on, and by then there is nothing left to salvage anyway — so the
        failure is logged at debug and swallowed.

        **The client is closed only if one was ever built** (`BUG-122`). It
        used to be resolved unconditionally, carried over from
        `binance_bot_module.py`, and `IExchangeClient` is bound lazily — so a
        session that never asked for market data *constructed* a client here,
        purely in order to close it: a network call on the way out
        (`BUG-045`'s shape), and `python-binance`'s `Client.__init__` creates
        an asyncio event loop in its websocket helper that nothing then
        closes, which the interpreter reports on exit as
        `Exception ignored in BaseEventLoop.__del__`.

        This method's own docstring used to say the fix "needs a way to ask
        the container whether a singleton was ever instantiated, which it does
        not currently offer". The Engine offers it: `Registration.instantiated`
        on `registrations()`, whose docstring names this exact question — and a
        registry read builds nothing, which is the point.
        """
        context.container.resolve(DatabaseManager).dispose_all()
        # `BUG-172`: the venues other than the default own their stores, clients
        # and streams; closed only if the registry was ever built.
        venues = context.container.registrations().get(IMarketDataVenues)
        if venues is not None and venues.instantiated:
            context.container.resolve(IMarketDataVenues).close()
        registration = context.container.registrations().get(IExchangeClient)
        if registration is None or not registration.instantiated:
            return
        try:
            exchange_client = context.container.resolve(IExchangeClient)
            if hasattr(exchange_client, "close"):
                exchange_client.close()
        except Exception as exc:  # noqa: BLE001 — see the docstring
            logger.debug("Exchange client shutdown error: %s", exc)
