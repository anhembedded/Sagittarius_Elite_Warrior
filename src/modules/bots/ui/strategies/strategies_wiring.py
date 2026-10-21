"""The Bots presenter's strategy commands, built from the app's container
(`EPIC-033K` stage 3, `BOT-219`).

One function, so `BotsPresenter` names the strategies in a line and a test builds
`VenueStrategies` from fakes instead: the venues this run serves, each
venue's own strategy ports and trading switch, the strategy catalog and the
app's symbol list. The questions are the presenter's (`BotsDialogs.ask_arm_strategy`,
`choose_venue`), so a test answers them as it answers Stop.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_dialogs import (
    BotsDialogs,
)
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

from .venue_strategies import StrategyPorts, VenueStrategies


def strategies_for(
    container: IContainer,
    dialogs: BotsDialogs,
    tell: Callable[[str], None],
    set_status: Callable[[str, bool], None],
) -> VenueStrategies:
    """The strategy commands of every venue this run serves."""
    controls = container.resolve(IVenueStrategyControls)
    trading = container.resolve(IVenueTradingPorts)
    venues = trading.enabled()
    config = container.resolve(IConfig).get_all()
    return VenueStrategies(
        StrategyPorts(
            venues=tuple(controls.get(venue) for venue in venues),
            catalog=container.resolve(IStrategyCatalogReader),
            symbol_options=default_symbol_options(config, FALLBACK_SYMBOL_OPTIONS),
            ask=dialogs.ask_arm_strategy,
            choose=dialogs.choose_venue,
            set_status=set_status,
            tell=tell,
            notifier=container.resolve(INotifier),
        )
    )
