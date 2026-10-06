"""`trading` as one Engine extension — the second real module (HLD §3.2, §3.4).

This is the only file under `modules/trading/` that `shell/` may import
(`is_module_entry_point` in the boundary guard). `shell/modules.py` lists the
class; `shell/module_registration.py` instantiates it and hands it to
`app.use()`.

**The context's one question:** *what is this account's position in the market,
and how does an order get there?* Order shaping and submission, the live
trading session and its limits, positions and open orders as a read model, the
account's own connection state. Deciding *whether* to send an order — a signal,
a strategy, a backtest — belongs to another context and reaches this one
through `contracts/`.

@par `register()` binds this module's own adapters and handlers, since PR 4.4f-4
PR 1.3b published the first three ports; PR 1.3c-3 added `IEquityCurve`. PR
1.3c-4 split the one shared `ExchangeSessionFactory` into one factory per
context (`FuturesSessionFactory` here, `MarketDataSessionFactory` in
`market_data`), which is what let the rest of this module's registrations
move at all — before that split, moving them meant either resolving
`market_data`'s own factory instance from the container or building a second
one, a behaviour change ADR D12 keeps out of a move. `EPIC-025E` PR 4.4f-4
is that move: `composition/adapter_bindings.py` (the session factory,
metadata provider/cache, credentials provider, account reader, equity
recorder, user-data stream, trading-venue and trading-limits singletons),
`composition/state_bindings.py` (`TradingSessionState`,
`PositionRefreshService`), `composition/command_bindings.py` (the six
trading commands) and `composition/query_bindings.py` (the three queries)
all move in together — the last of `binance_bot_module.py`'s bindings that
are genuinely this module's own; what remains there after this PR is the
shared core engine-adapter ports and the indicator scripts, neither owned by
any one module (`EPIC-025E_phase4_support_and_dissolve_common.md` §3.16).

**No binding lives in `boot()` any more.** `ITradingClient` used to be bound
there, conditionally on the one `TradingVenue`. `EPIC-028B` deleted that
bind: every venue's client is created from its own `VenueContext`
(`IVenueContexts.get(venue).client_factory`), by the handler of the command
that names the venue.

**`contribute()` since PR 1.4c-4, and what it contributes.** One
`DEV_PROBE`: the live trading session's own state, in the Developer mode
(`EPIC-033P`) — the first widget any bounded context owns. `EPIC-025E` PR 4.4e adds a second: this
module's own credentials, order venue and connection check, split off the old
monolithic Settings screen, and a page of Tools → Options since `EPIC-033E`.

**`subscribe()` not implemented, and why:** this context's Qt-side
subscriptions still live in the two legacy Presenters, and they move with those
screens. It is a default inherited from `BoundedContextModule`, so the absence
is a statement, not an omission.
"""

from __future__ import annotations

import logging
from typing import Any

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)
from Sagittarius_Elite_Warrior.src.core.contracts.contribution_descriptor import (
    ContributionDescriptor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.deferred import Deferred
from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_registry import (
    IContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_options_section import (
    IOptionsSection,
)
from Sagittarius_Elite_Warrior.src.core.contracts.options_page_contribution import (
    OptionsPageContribution,
)
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.size_hint import SizeHint
from Sagittarius_Elite_Warrior.src.modules.trading.composition.adapter_bindings import (
    bind_adapters,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.command_bindings import (
    bind_commands,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.port_bindings import (
    bind_published_ports,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.query_bindings import (
    bind_queries,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.state_bindings import (
    bind_state,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_refresh_services import (
    build_account_summary_refreshes,
    build_venue_refresh_services,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_commands import (
    market_commands,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_screen import (
    MARKET_ROUTE,
    market_screen,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.probes import (
    build_trading_session_probe,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_commands import (
    trade_commands,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_screen import (
    TRADE_ROUTE,
    trade_screen,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.runtime.scheduler.scheduler import Scheduler

logger = logging.getLogger("App.TradingModule")

#: `BUG-117` — Binance's own UI recomputes unrealized PnL roughly every
#: second; polling `GetOpenPositionsQuery` that often for a number that only
#: needs to look alive, not tick-perfect, would spend request weight for
#: nothing. 5s keeps the Positions table honestly current without it.
#: Overridable via `ConfigKeys.TRADING_POSITION_REFRESH_INTERVAL_SECONDS`,
#: clamped to `_MIN_POSITION_REFRESH_INTERVAL_SECONDS` below.
_DEFAULT_POSITION_REFRESH_INTERVAL_SECONDS: float = 5.0

#: `BUG-117` — floor for the config override above. `futures_position_
#: information()` (`python-binance`) calls Binance's documented "Position
#: Information V3" (`GET /fapi/v3/positionRisk`), weight 5 per Binance's
#: published USDⓈ-M Futures API weight table. Binance's default IP weight
#: budget is 2400/min; at 1 call/s this poll alone spends `60 * 5 = 300`
#: weight/min (12.5% of that budget), leaving headroom for every other
#: request this app makes. Below 1s the app would be trading budget for a
#: number that does not need sub-second freshness.
#: `EPIC-028O` — the account-summary check on the same cadence reads the
#: Futures Multi-Assets mode (weight 30) only every five minutes
#: (`futures_account_reader.ASSET_MODE_TTL_SECONDS`), about 6 weight/min.
_MIN_POSITION_REFRESH_INTERVAL_SECONDS: float = 1.0


#: Tools → Options → Trading (`EPIC-033E`), built when the shell
#: assembles the dialog's pages.
_OPTIONS_PAGE: Deferred[IOptionsSection] = Deferred(
    "Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.trading_options_page"
    ":build_trading_options_page"
)


class TradingModule(BoundedContextModule):
    """Order submission, the live trading session, and the positions read model."""

    module_id = "trading"

    #: Checked, not declared by hand: `test_module_declarations.py` reads the
    #: imports actually present under `modules/trading/` and fails on both
    #: surplus and shortfall.
    #:
    #: **This was `[]` until PR 4.1a, and the guard is what corrected it.** The
    #: comment here said *"this context reads no other module's `contracts/` —
    #: it is the supplier in every relationship it has"*, and that was true of
    #: everything under `modules/trading/` at the time. What made it false is
    #: `market_tick_feed`, one of the six feeds that moved in from
    #: `presentation/ui/common/`: it normalises `market_data`'s published
    #: `MarketTickEvent` onto a Qt signal for the live chart, which is the
    #: Open Host Service relationship HLD §02 has always drawn
    #: (`market_data → trading`) and which no file in this module had happened
    #: to exercise yet. The coupling did not arrive with the move; only its
    #: visibility did, which is the whole point of declaring it where the
    #: module list is read.
    dependencies: list[str] = ["market_data"]  # noqa: RUF012 — the Engine reads a plain attribute

    def __init__(self) -> None:
        super().__init__()
        #: Stashed by `boot()`; `contribute()` refuses to run before it
        #: (`EPIC-025F` PR 5.2 began it for the Dev Board, which `EPIC-033P`
        #: deleted, and the desks' screens read it until `EPIC-033I`). `boot()`
        #: always runs before `contribute()` (`BoundedContextModule`'s own
        #: hook table), and this is the same single container the app has
        #: for its whole lifetime — see `boot()`'s own docstring for why it
        #: must come from there and not from `register()`.
        self._container: IContainer | None = None
        #: The venues enabled in this run, read by `boot()` from
        #: `IVenueContexts`: the Trade menu lists them (`EPIC-033I`).
        self._venues: tuple[TradingVenue, ...] = ()

    def register(self, context: Any) -> None:
        """This module's own adapters, state, commands, queries, and the
        published ports (PR 1.3b, plus `IEquityCurve` from PR 1.3c-3).

        `EPIC-025E` PR 4.4f-4: `bind_state()` runs before `bind_adapters()`
        would matter if either resolved eagerly, but every binding in both
        is a lazy singleton or factory, so the actual order here only
        matters for readability — adapters (what this module talks to),
        then state (what depends on `TradingSessionState`), then the two
        CQRS tables, then the ports another context may depend on.
        """
        container = context.container
        bind_adapters(container)
        bind_state(container)
        bind_commands(container)
        bind_queries(container)
        bind_published_ports(container)

    def contribute(self, registry: IContributionRegistry) -> None:
        """The Developer mode's probe for this context's own session state
        (`EPIC-033P` moved it there from the Dev Board), its Settings section,
        and — since `EPIC-025F` PR 5.2 — its screens.

        `DEV_PROBE` is the Developer mode's place and it is gated: with `dev.mode` off,
        the registry drops this contribution with one log line and the app
        boots — the normal user run, not an error (`shell/surfaces.py`).

        The factory is `ui/probes.py`'s, which imports no widget module until
        it is called. That is the rule and the reason: `contribute()` runs at
        boot for every run, a headless `sync` included, and a probe nobody
        opened must not cost a Qt import.

        The Trade mode's commands list the venues `boot()` read as enabled
        (`EPIC-033I`): only an enabled venue can be chosen.
        """
        if self._container is None:
            raise RuntimeError("TradingModule.contribute() called before boot()")
        registry.contribute(
            ContributionDescriptor(
                contributor_id=self.module_id,
                surface_id="developer",
                place=Place.DEV_PROBE,
                order=10,
                size_hint=SizeHint.REGULAR,
                factory=build_trading_session_probe,
                title="Trading session",
            )
        )
        registry.contribute_options_page(
            OptionsPageContribution(
                contributor_id=self.module_id,
                order=10,
                factory=_OPTIONS_PAGE,
            )
        )
        # `EPIC-033H` — the Market mode, first on the mode bar.
        registry.contribute_screen(market_screen())
        # `EPIC-033I` — one Trade mode for every venue, replacing the two
        # desks of `EPIC-028K`/`028L`.
        registry.contribute_screen(trade_screen())
        # `EPIC-033D` — each screen's commands; the Trade menu lists the
        # venues `boot()` read as enabled.
        for command in (
            *market_commands(MARKET_ROUTE),
            *trade_commands(TRADE_ROUTE, self._venues),
        ):
            registry.contribute_command(command)

    def boot(self, context: Any) -> None:
        """Two things `register()` could not decide or start.

        Each venue's `IUserDataStream` is built but deliberately never started by
        booting: only a successful `EnableTradingCommand` calls `.start()`
        on it, so opening the app opens no user-data socket (`EPIC-021H`).
        That stays true whoever registers it.

        `EPIC-025E` PR 4.4f-4 added the first:

        1. **The account refresh scheduling** (`BUG-117`) — one recurring
           job per enabled venue since `EPIC-028C`, registered once, for the
           lifetime of the process; each `refresh_once()` is a no-op while
           its venue's trading is disabled, so nothing else needs to start
           or stop it alongside Enable/Disable/Emergency-Stop.

        `EPIC-025F` PR 5.2 added the second: stashing `container` (see
        `__init__`'s docstring), and since `EPIC-033I` the venues enabled in
        this run, which the Trade menu lists. Stashed here, not in `register()` — the
        `context.container` `register()` receives is `RegisteringContainer`,
        a spy that raises on every `resolve()` call **forever**, not only
        during registration (`shell/registering_container.py`'s own
        docstring: "the shell wraps the real container for the duration of
        one module's `register()`"); a reference to it captured there and
        used later, inside a screen's lazily-run view factory, would raise
        `ResolveDuringRegisterError` on a call that has nothing to do with
        registration any more. `boot()`'s `container` is the real one —
        every existing `container.resolve(...)` call below already depends
        on that being true.
        """
        container = context.container
        self._container = container
        self._venues = tuple(container.resolve(IVenueContexts).enabled())

        config = container.resolve(IConfig)
        scheduler = container.resolve(Scheduler)
        interval_seconds = self._position_refresh_interval_seconds(config)
        # `EPIC-028C` — one refresh per enabled venue, chosen by its market
        # (`venue_refresh_services.py`): positions on Futures, holdings on
        # Spot, each reading and addressing its own venue.
        for service in build_venue_refresh_services(container):
            scheduler.every(seconds=interval_seconds).do(service.refresh_once)
            logger.info(
                "Scheduled %s for %s every %.1fs.",
                type(service).__name__,
                service.venue.value,
                interval_seconds,
            )
        # `EPIC-028D` — each venue's account summary, on the same cadence and
        # straight after each of that venue's fills.
        event_bus = container.resolve(IEventBus)
        for summary in build_account_summary_refreshes(container):
            scheduler.every(seconds=interval_seconds).do(summary.refresh_once)
            event_bus.on(OrderFilledEvent, summary.on_order_filled)
            logger.info(
                "Scheduled the account summary refresh for %s every %.1fs, "
                "and after each of its fills.",
                summary.venue.value,
                interval_seconds,
            )

    @staticmethod
    def _position_refresh_interval_seconds(config: IConfig) -> float:
        """`BUG-117` — reads `TRADING_POSITION_REFRESH_INTERVAL_SECONDS`,
        clamped to `_MIN_POSITION_REFRESH_INTERVAL_SECONDS` (see that
        constant's own comment for the Binance request-weight reasoning
        behind the floor). Logs once, at boot, if the configured value was
        raised — silently ignoring a below-floor setting would leave an
        admin who deliberately tightened it with no idea it never took
        effect."""
        configured = float(
            config.get(
                ConfigKeys.TRADING_POSITION_REFRESH_INTERVAL_SECONDS.value,
                _DEFAULT_POSITION_REFRESH_INTERVAL_SECONDS,
            )
        )
        if configured < _MIN_POSITION_REFRESH_INTERVAL_SECONDS:
            logger.warning(
                "%s=%.3f is below the %.3fs floor (Binance request-weight "
                "budget) — using %.3fs instead.",
                ConfigKeys.TRADING_POSITION_REFRESH_INTERVAL_SECONDS.value,
                configured,
                _MIN_POSITION_REFRESH_INTERVAL_SECONDS,
                _MIN_POSITION_REFRESH_INTERVAL_SECONDS,
            )
            return _MIN_POSITION_REFRESH_INTERVAL_SECONDS
        return configured

    def shutdown(self, context: Any) -> None:
        """Release the external connections this module owns.

        `EPIC-025E` PR 4.4f-4 — moved out of `binance_bot_module.py`, same
        shape `MarketDataModule.shutdown()` already uses: each user-data
        stream is closed inside `try`/`except` because a shutdown path that
        raises turns a clean exit into a stack trace the user cannot act on,
        and by then there is nothing left to salvage anyway — so the
        failure is logged at debug and swallowed.

        **`IUserDataStream.stop()` is harmless even if trading was never
        enabled this session** (`EPIC-021H` — it returns `False`, does not
        raise) — still worth calling unconditionally so a session that
        *did* enable trading always tears its stream down.

        `EPIC-028B` — one stream per enabled venue, each stopped on its own,
        so one venue failing to close never leaves the other's socket open.
        `TradingVenue.DISABLED` is never enabled and can never start a
        stream (`EnableTradingCommandHandler` refuses it first).
        """
        contexts = context.container.resolve(IVenueContexts)
        for venue in contexts.enabled():
            try:
                contexts.get(venue).user_data_stream.stop()
            except Exception as exc:  # noqa: BLE001 — see the docstring
                logger.debug(
                    "User data stream shutdown error on %s: %s", venue.value, exc
                )
