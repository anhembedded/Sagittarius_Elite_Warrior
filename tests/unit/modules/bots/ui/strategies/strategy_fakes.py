"""Fakes for the Bots mode's strategy rows (`EPIC-033K` stage 3).

Each venue's arming and armed state are the strategy module's own fakes,
behind the adapters `StrategyModule.register()` binds in production; a
successful arm or disarm moves the armed state, as the real session does, so
the rows re-read what a test armed. Derived from the ports
(`testing-rule.md` §2): `IVenueStrategyControls` and the catalog's real,
cheap service over an in-memory registry.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.strategy_form_view_model import (
    StrategyFormViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.strategy_rows import (
    StrategiesPanel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.venue_strategies import (
    StrategyPorts,
    VenueStrategies,
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
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_catalog_service import (
    StrategyCatalogService,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.testing import (
    FakeArmedStrategy,
    FakeStrategyArming,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    ArmedStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_arming_control import (
    IStrategyArmingControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_catalog_reader import (
    IStrategyCatalogReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_strategy_controls import (
    IVenueStrategyControls,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_arm_result import (
    ArmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_disarm_result import (
    DisarmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_strategy_controls import (
    VenueStrategyControls,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

STRATEGY_KEY = "ema_crossover"
SYMBOLS = ("BTCUSDT", "ETHUSDT")


class VenueArming:
    """One venue's arming fake and armed-state fake, joined."""

    def __init__(self, venue: TradingVenue) -> None:
        self.venue = venue
        #: The venue's live trading switch, as a test sets it.
        self.trading_on = False
        self.arming = FakeStrategyArming()
        self.armed = FakeArmedStrategy()
        self.controls = VenueStrategyControls(
            venue=venue,
            arming=_JoinedArming(self),
            armed=ArmedStrategyReaderAdapter(self.armed),
        )


class _JoinedArming(IStrategyArmingControl):
    """The production adapter over the arming fake; an accepted arm or
    disarm also moves the armed state, as `LiveStrategySession` does."""

    def __init__(self, venue: VenueArming) -> None:
        self._venue = venue
        self._adapter = StrategyArmingControlAdapter(venue.arming)

    def arm(self, config: ArmedStrategyConfig) -> ArmStrategyResult:
        result = self._adapter.arm(config)
        if result.armed:
            self._venue.armed.seed(self._venue.arming.armed_with)
        return result

    def disarm(self) -> DisarmStrategyResult:
        result = self._adapter.disarm()
        if result.disarmed:
            self._venue.armed.seed(None)
        return result

    def saved_selection(self) -> ArmedStrategyConfig:
        return self._adapter.saved_selection()


class FakeVenueStrategyControls(IVenueStrategyControls):
    def __init__(self, *venues: VenueArming) -> None:
        self._by_venue = {venue.venue: venue.controls for venue in venues}

    def get(self, venue: TradingVenue) -> VenueStrategyControls:
        return self._by_venue[venue]


def strategy_catalog() -> IStrategyCatalogReader:
    registry = StrategyRegistry()
    registry.register(STRATEGY_KEY, EmaCrossoverStrategy)
    return StrategyCatalogReaderAdapter(StrategyCatalogService(registry))


class Asked:
    """What the Arm strategy dialog was asked, and how a test answers it."""

    def __init__(self) -> None:
        self.answer = True
        self.edit: Callable[[StrategyFormViewModel], None] = lambda _form: None
        self.venues: list[TradingVenue] = []

    def __call__(self, venue: TradingVenue, form: StrategyFormViewModel) -> bool:
        self.venues.append(venue)
        self.edit(form)
        return self.answer


class Statuses(list[tuple[str, bool]]):
    def __call__(self, text: str, is_error: bool) -> None:
        self.append((text, is_error))


def venue_strategies(
    panel: StrategiesPanel,
    venues: Sequence[VenueArming],
    ask: Asked | None = None,
    statuses: Statuses | None = None,
) -> VenueStrategies:
    by_venue = {venue.venue: venue for venue in venues}
    return VenueStrategies(
        panel,
        StrategyPorts(
            venues=tuple(venue.controls for venue in venues),
            catalog=strategy_catalog(),
            symbol_options=SYMBOLS,
            ask=ask or Asked(),
            set_status=statuses if statuses is not None else Statuses(),
            trading_on=lambda venue: by_venue[venue].trading_on,
        ),
    )
