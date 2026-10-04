"""This module's published ports, bound to their implementations.

Mirrors `modules/trading/composition/port_bindings.py`: the module's own
`register()` binds **only what it publishes**, and the rest of the strategy
bindings stay in `binance_bot_module.py` — the composition root the strangler is
replacing, which the boundary scan skips by name and which shrinks one phase at
a time.

Why a lambda rather than construction here. `LiveStrategySession` is already a
singleton registered by that strangler root, built from a factory that needs
`IEventPublisher`, `IOrderSubmission`, `ITradingAccountReader` and
`IMarketMetadataProvider`. Building a *second* session here would mean two
armed states — one the tick path drives, one the screens read — which is the
class of bug `ExchangeSessionFactory` took four pull requests to get out of
(PR 1.3c-4). Resolving the existing one inside a factory lambda keeps one
instance, and the lambda runs at first `resolve()`, never during `register()`,
which SDD §4 forbids from resolving anything.

@par What PR 2.1d measured, against what this file predicted
It said the rest of the bindings would move here with `ISizingPolicy`, *"that
pull request already has to touch the factory's arguments"*. It does not.
`ISizingPolicy` turned out to be a **domain policy**, not a collaborator a
session holds: `position_sizing_bridge` — inside this module since 2.1d —
constructs `MarginSizingPolicy` and calls it, exactly as it used to construct
`MarginRiskPolicy`, so `LiveStrategyFactory`, `LiveStrategySession` and
`LiveTradingCoordinator` all kept the arguments they had. Moving the registry,
the session, the factory, the config store and the two handlers out of
`binance_bot_module.py` is therefore a move with no reason in this pull
request, and it travels with PR 2.1e, which has one: the strategy card and the
overlay need the registry, and they arrive there.

**`ISizingPolicy` is bound since PR 3.1b, and this file predicted the pull
request that would do it.** It used to read: *"deliberately not bound here.
Nothing resolves it … so it arrives in Phase 3 with the consumer that resolves it
(`EPIC-025D`)."* That is exactly what happened. `PaperExchange` no longer defaults
to `MarginSizingPolicy()` — a default is how a paper broker came to import
another module's *domain policy* directly, which is the allowlist line PR 2.1d
scheduled for this phase — so the two backtest handlers resolve the port and pass
it in. The binding is a class rather than a lambda because the policy is pure
arithmetic with nothing to inject.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_reader import IConfigReader
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_writer import IConfigWriter
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.armed_strategy_reader_adapter import (
    ArmedStrategyReaderAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.strategy_arming_control_adapter import (
    StrategyArmingControlAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.strategy_catalog_reader_adapter import (
    StrategyCatalogReaderAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.strategy_chart_overlay_reader_adapter import (
    StrategyChartOverlayReaderAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.venue_strategy_controls_adapter import (
    VenueStrategyControlsAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_config_store import (
    LiveStrategyConfigStore,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_session import (
    LiveStrategySession,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_arming_service import (
    StrategyArmingService,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_catalog_service import (
    StrategyCatalogService,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_chart_overlay_service import (
    StrategyChartOverlayService,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_engine_factory import (
    StrategyEngineFactory,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.venue_strategy_sessions import (
    VenueStrategySessions,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_armed_strategy import (
    IArmedStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_sizing_policy import (
    ISizingPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_arming import (
    IStrategyArming,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_catalog import (
    IStrategyCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_chart_overlay import (
    IStrategyChartOverlay,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_engine import (
    IStrategyEngineFactory,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.policies.margin_sizing_policy import (
    MarginSizingPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_armed_strategy_reader import (
    IArmedStrategyReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_arming_control import (
    IStrategyArmingControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_catalog_reader import (
    IStrategyCatalogReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_chart_overlay_reader import (
    IStrategyChartOverlayReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_strategy_controls import (
    IVenueStrategyControls,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.interfaces.i_container import IContainer


def bind_published_ports(container: IContainer) -> None:
    """`IArmedStrategy` (PR 2.1c), PR 3.1b's two for `backtesting`, PR
    4.3m's three, and PR 4.4c's four trading-owned reader/control ports
    (`DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`
    §8) — `trading`/`dashboard`/`backtest` stop importing this module's
    `ui/`/`application/`/`contracts/` directly and read/write through
    these instead. The four §8 ports bind adapters, never the services
    themselves: `trading`'s own contract, implemented on this side of the
    boundary, is what keeps `trading.dependencies` free of `"strategy"`.
    `EPIC-028K` adds `IVenueStrategyControls`: the same arming and reader
    ports, one pair per venue, for the desks."""
    container.singleton(IArmedStrategy, _the_live_session)
    container.singleton(IStrategyEngineFactory, _the_engine_factory)
    container.singleton(ISizingPolicy, MarginSizingPolicy)
    container.singleton(IStrategyCatalog, _the_catalog)
    container.singleton(IStrategyChartOverlay, _the_chart_overlay)
    container.singleton(IStrategyArming, _the_strategy_arming)
    container.singleton(IArmedStrategyReader, _the_armed_strategy_reader)
    container.singleton(IStrategyCatalogReader, _the_strategy_catalog_reader)
    container.singleton(IStrategyArmingControl, _the_strategy_arming_control)
    container.singleton(IStrategyChartOverlayReader, _the_strategy_chart_overlay_reader)
    container.singleton(IVenueStrategyControls, _the_venue_strategy_controls)


def _the_strategy_arming(container: IContainer) -> IStrategyArming:
    """`EPIC-028B` — the primary venue's arming: what the Dev Board arms and
    disarms (each desk arms its own venue through `IVenueStrategyControls`)."""
    return venue_strategy_arming(container, container.resolve(TradingVenue))


def venue_strategy_arming(
    container: IContainer, venue: TradingVenue
) -> IStrategyArming:
    """The arming of one venue: every command it sends is addressed to
    `venue`, and what it restores is `venue`'s own saved configuration
    (`EPIC-028C`)."""
    return StrategyArmingService(
        container.resolve(ICommandDispatcher),
        live_strategy_config_store(container),
        venue,
    )


def live_strategy_config_store(container: IContainer) -> LiveStrategyConfigStore:
    """Each venue's saved strategy, over the application's own configuration
    ports (`IConfigReader`/`IConfigWriter`), never the Engine's `IConfig`."""
    return LiveStrategyConfigStore(
        container.resolve(IConfigReader), container.resolve(IConfigWriter)
    )


def _the_venue_strategy_controls(container: IContainer) -> IVenueStrategyControls:
    """`EPIC-028K` — each desk's own venue's arming and armed state, over
    the same per-venue sessions the tick path drives (one session per venue,
    never a second one)."""
    return VenueStrategyControlsAdapter(
        lambda venue: venue_strategy_arming(container, venue),
        container.resolve(VenueStrategySessions),
    )


def _the_live_session(container: IContainer) -> IArmedStrategy:
    return container.resolve(LiveStrategySession)


def _the_engine_factory(container: IContainer) -> IStrategyEngineFactory:
    """`EPIC-025C` §1 item 2's port, bound at the phase that asked for it.

    A named factory rather than a lambda, and late-resolving, for the reason
    `market_data/composition/port_bindings.py` records: `StrategyRegistry` is
    registered by another part of the boot, and resolving during `register()` is
    what `shell/registering_container.py` refuses. It holds the *one* registry
    the app has — two would mean a backtest could run a strategy the live
    screens cannot see, which is the class of bug the `ExchangeSessionFactory`
    split took four pull requests to leave behind (PR 1.3c-4).
    """
    return StrategyEngineFactory(
        container.resolve(StrategyRegistry), container.resolve(IEventPublisher)
    )


def _the_catalog(container: IContainer) -> IStrategyCatalog:
    """Same reason as `_the_engine_factory`: one `StrategyRegistry`, resolved
    late rather than during `register()`."""
    return StrategyCatalogService(container.resolve(StrategyRegistry))


def _the_chart_overlay(container: IContainer) -> IStrategyChartOverlay:
    return StrategyChartOverlayService(container.resolve(StrategyRegistry))


def _the_armed_strategy_reader(container: IContainer) -> IArmedStrategyReader:
    """Wraps the already-bound `IArmedStrategy`, never a fresh
    `LiveStrategySession` — one armed session for the whole app, as above."""
    return ArmedStrategyReaderAdapter(container.resolve(IArmedStrategy))


def _the_strategy_catalog_reader(container: IContainer) -> IStrategyCatalogReader:
    return StrategyCatalogReaderAdapter(container.resolve(IStrategyCatalog))


def _the_strategy_arming_control(container: IContainer) -> IStrategyArmingControl:
    return StrategyArmingControlAdapter(container.resolve(IStrategyArming))


def _the_strategy_chart_overlay_reader(
    container: IContainer,
) -> IStrategyChartOverlayReader:
    return StrategyChartOverlayReaderAdapter(container.resolve(IStrategyChartOverlay))
