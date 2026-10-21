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

from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.arm_strategy_dialog import (
    ArmQuestion,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.disarm_choice import (
    VenueQuestion,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.strategy_form_view_model import (
    StrategyFormViewModel,
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
    """What the Arm strategy dialog was asked, and how a test answers it: the venue to arm on
    (`None` cancels). By default it picks the first venue offered."""

    def __init__(self) -> None:
        self.cancel = False
        #: The venue to answer with; `None` picks the first one offered.
        self.venue: TradingVenue | None = None
        self.edit: Callable[[StrategyFormViewModel], None] = lambda _form: None
        #: Every question asked, in order.
        self.questions: list[ArmQuestion] = []

    @property
    def offered(self) -> list[TradingVenue]:
        """The venues the last question offered."""
        return list(self.questions[-1].forms) if self.questions else []

    def __call__(self, question: ArmQuestion) -> TradingVenue | None:
        self.questions.append(question)
        if self.cancel:
            return None
        venue = self.venue or next(iter(question.forms))
        self.edit(question.forms[venue])
        return venue


class Chose:
    """Which armed venue a Disarm question was answered with (`None` cancels)."""

    def __init__(self) -> None:
        self.venue: TradingVenue | None = None
        self.choices: list[VenueQuestion] = []

    def __call__(self, choice: VenueQuestion) -> TradingVenue | None:
        self.choices.append(choice)
        return self.venue


class Told(list[str]):
    """The lines told to the Output pane."""

    def __call__(self, line: str) -> None:
        self.append(line)


class Statuses(list[tuple[str, bool]]):
    def __call__(self, text: str, is_error: bool) -> None:
        self.append((text, is_error))


def venue_strategies(
    venues: Sequence[VenueArming],
    ask: Asked | None = None,
    statuses: Statuses | None = None,
    notifier: RecordingNotifier | None = None,
    chose: Chose | None = None,
    told: Told | None = None,
) -> VenueStrategies:
    return VenueStrategies(
        StrategyPorts(
            venues=tuple(venue.controls for venue in venues),
            catalog=strategy_catalog(),
            symbol_options=SYMBOLS,
            ask=ask or Asked(),
            choose=chose or Chose(),
            set_status=statuses if statuses is not None else Statuses(),
            tell=told if told is not None else Told(),
            notifier=notifier if notifier is not None else RecordingNotifier(),
        ),
    )
