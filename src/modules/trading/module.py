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

**One binding did not move into `register()`.** `ITradingClient` was
registered *conditionally* in the legacy root, gated on `TradingVenue !=
DISABLED` — a decision `register()` cannot make (`resolve()` is refused
there; see `composition/adapter_bindings.py`'s own docstring for the full
reasoning). It moved into `boot()` instead, alongside the
`PositionRefreshService` scheduling that already lived here.

**`contribute()` since PR 1.4c-4, and what it contributes.** One
`DEV_PROBE`: the live trading session's own state, on the Dev Board — the
first widget any bounded context owns. `EPIC-025E` PR 4.4e adds a second: one
`SETTINGS_SECTION` for this module's own credentials, order venue and
connection check, split off the old monolithic Settings screen.

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
from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_registry import (
    IContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.size_hint import SizeHint
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client import (
    FuturesTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.position_refresh_service import (
    PositionRefreshService,
)
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_user_data_stream import (
    IUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dashboard_screen import (
    dashboard_screen,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.probes import (
    build_trading_session_probe,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings_contribution import (
    build_trading_settings_section,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trading.trading_screen import (
    trading_screen,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionFactory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_container import IContainer
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
_MIN_POSITION_REFRESH_INTERVAL_SECONDS: float = 1.0


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
        #: Stashed by `boot()`, read by `contribute()`'s `dashboard_
        #: screen(self._container)` call (`EPIC-025F` PR 5.2). `boot()`
        #: always runs before `contribute()` (`BoundedContextModule`'s own
        #: hook table), and this is the same single container the app has
        #: for its whole lifetime — see `boot()`'s own docstring for why it
        #: must come from there and not from `register()`.
        self._container: IContainer | None = None

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
        """The Dev Board probe for this context's own session state, its
        Settings section, and — since `EPIC-025F` PR 5.2 — its two screens.

        `DEV_PROBE` is Dev Board's place and it is gated: with `dev.mode` off,
        the registry drops this contribution with one log line and the app
        boots — the normal user run, not an error (`shell/surfaces.py`).

        The factory is `ui/probes.py`'s, which imports no widget module until
        it is called. That is the rule and the reason: `contribute()` runs at
        boot for every run, a headless `sync` included, and a probe nobody
        opened must not cost a Qt import.

        `dashboard_screen(self._container)` needs the container `register()`
        stashed (see `__init__`'s docstring); `trading_screen()` does not —
        `TradingView()` takes no constructor arguments.
        """
        if self._container is None:
            raise RuntimeError("TradingModule.contribute() called before register()")
        registry.contribute(
            ContributionDescriptor(
                contributor_id=self.module_id,
                surface_id="dev_board",
                place=Place.DEV_PROBE,
                order=10,
                size_hint=SizeHint.REGULAR,
                factory=build_trading_session_probe,
                title="Trading session",
            )
        )
        registry.contribute(
            ContributionDescriptor(
                contributor_id=self.module_id,
                surface_id="settings",
                place=Place.SETTINGS_SECTION,
                order=10,
                size_hint=SizeHint.REGULAR,
                factory=build_trading_settings_section,
                title="Trading",
            )
        )
        registry.contribute_screen(dashboard_screen(self._container))
        registry.contribute_screen(trading_screen())

    def boot(self, context: Any) -> None:
        """Two things `register()` could not decide or start.

        `IUserDataStream` is registered but deliberately never started by
        booting: only a successful `EnableTradingCommand` calls `.start()`
        on it, so opening the app opens no user-data socket (`EPIC-021H`).
        That stays true whoever registers it.

        `EPIC-025E` PR 4.4f-4 added the other two:

        1. **`ITradingClient`'s conditional bind** (`_bind_trading_client_
           if_enabled`, below — its own method so `tests/unit/modules/
           trading/test_module_trading_client_binding.py` can drive both
           branches against a real container without also needing this
           method's scheduler half). `register()` cannot make this call —
           see `composition/adapter_bindings.py`'s own docstring for why —
           so `boot()` makes it instead, once every module has registered
           and `resolve()` is allowed again.
        2. **`PositionRefreshService`'s scheduling** (`BUG-117`) — one
           recurring job, registered once, for the lifetime of the process;
           `PositionRefreshService.refresh_once()` is a no-op while trading
           is disabled, so nothing else needs to start or stop this
           alongside Enable/Disable/Emergency-Stop.

        `EPIC-025F` PR 5.2 added the third: stashing `container` for
        `contribute()`'s `dashboard_screen(self._container)` call (see
        `__init__`'s docstring). Stashed here, not in `register()` — the
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

        self._bind_trading_client_if_enabled(container)

        config = container.resolve(IConfig)
        position_refresh = container.resolve(PositionRefreshService)
        container.resolve(Scheduler).every(
            seconds=self._position_refresh_interval_seconds(config)
        ).do(position_refresh.refresh_once)

    @staticmethod
    def _bind_trading_client_if_enabled(container: Any) -> None:
        """`EPIC-021F` — unlike `ITradingAccountReader` (read-only, always
        safe), `ITradingClient` can place/cancel a real order, so it is
        registered only when trading is explicitly turned on; resolving
        this port anywhere trading is `DISABLED` fails loudly (an
        unbound-type error) instead of silently handing back a client
        nobody asked to enable.

        `tests/sanity/test_composition_root.py`'s `_NOT_DISPATCHED` entry
        for `SubmitOrderCommand` only *skips* asserting a resolve under the
        default (disabled) boot — it does not positively prove either
        branch. `test_module_trading_client_binding.py` does: it resolves
        `ITradingClient` against a real container in both states and
        asserts the unbound-type error in one, a real `FuturesTradingClient`
        in the other — the type-and-test pair `architecture-rule.md` §7.3
        asks for wherever a docstring alone would otherwise be the only
        thing saying this still holds.
        """
        trading_venue = container.resolve(TradingVenue)
        if trading_venue is not TradingVenue.DISABLED:
            container.singleton(
                ITradingClient,
                lambda c: FuturesTradingClient(
                    c.resolve(ITradingSessionFactory),
                    c.resolve(IExchangeCredentialsProvider),
                    c.resolve(IMarketMetadataProvider),
                    OrderSubmissionMode.VALIDATE_ONLY,
                ),
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
        shape `MarketDataModule.shutdown()` already uses: the user-data
        stream is closed inside `try`/`except` because a shutdown path that
        raises turns a clean exit into a stack trace the user cannot act on,
        and by then there is nothing left to salvage anyway — so the
        failure is logged at debug and swallowed.

        **`IUserDataStream.stop()` is harmless even if trading was never
        enabled this session** (`EPIC-021H` — it returns `False`, does not
        raise) — still worth calling unconditionally so a session that
        *did* enable trading always tears its stream down.
        """
        try:
            context.container.resolve(IUserDataStream).stop()
        except Exception as exc:  # noqa: BLE001 — see the docstring
            logger.debug("User data stream shutdown error: %s", exc)
