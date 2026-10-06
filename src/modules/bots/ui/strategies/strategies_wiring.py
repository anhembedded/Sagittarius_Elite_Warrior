"""The Bots presenter's strategy rows, built from the app's container
(`EPIC-033K` stage 3).

One function, so `BotsPresenter` names the rows in a line and a test builds
`VenueStrategies` from fakes instead: the venues this run serves, each
venue's own strategy ports and trading switch, the strategy catalog and the
app's symbol list. The question is the presenter's
(`BotsDialogs.ask_arm_strategy`), so a test answers it as it answers Stop.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_catalog_reader import (
    IStrategyCatalogReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_strategy_controls import (
    IVenueStrategyControls,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.app_defaults import (
    FALLBACK_SYMBOL_OPTIONS,
    default_symbol_options,
)
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_container import IContainer

from .arm_strategy_dialog import AskArmStrategy
from .strategy_rows import StrategiesPanel
from .venue_strategies import StrategyPorts, VenueStrategies


def strategies_for(
    container: IContainer,
    panel: StrategiesPanel,
    ask: AskArmStrategy,
    set_status: Callable[[str, bool], None],
) -> VenueStrategies:
    """The rows of every venue this run serves, shown in `panel`."""
    controls = container.resolve(IVenueStrategyControls)
    trading = container.resolve(IVenueTradingPorts)
    venues = trading.enabled()
    config = container.resolve(IConfig).get_all()
    return VenueStrategies(
        panel,
        StrategyPorts(
            venues=tuple(controls.get(venue) for venue in venues),
            catalog=container.resolve(IStrategyCatalogReader),
            symbol_options=default_symbol_options(config, FALLBACK_SYMBOL_OPTIONS),
            ask=ask,
            set_status=set_status,
            trading_on=lambda venue: (
                trading.get(venue).trading_session.snapshot().enabled
            ),
        ),
        panel,
    )
