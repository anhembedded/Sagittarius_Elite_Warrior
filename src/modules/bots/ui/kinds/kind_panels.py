"""`EPIC-029F` — each kind's parameter editor and backtest, by `kind_id`.

The one place the UI names a kind: a new kind adds its editor (and its
backtest, if it has one, `EPIC-029D`) here and its `IBotKind` to the catalog,
and the screen does not change.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    UnknownBotKindError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    PROFILE_MARKETS,
    VenueProfile,
    is_in_markets,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_KIND_ID,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_backtest import (
    BacktestPorts,
    BotBacktest,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_kind_panel import (
    BotKindPanel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.grid_backtest import (
    GridBacktest,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_panel import (
    GridPanel,
)

_PANELS: Mapping[str, Callable[[], BotKindPanel]] = {GRID_KIND_ID: GridPanel}

#: A kind with no entry has no backtest, and its Backtest tab stays hidden.
_BACKTESTS: Mapping[str, Callable[[BacktestPorts], BotBacktest]] = {
    GRID_KIND_ID: GridBacktest
}

#: The markets each kind's backtest can replay. On a venue outside its set the tab stays
#: hidden rather than replaying another market's candles as the bot's own; the Futures
#: backtest (funding and liquidation included, decision O9, `EPIC-039K`) is the Grid's too.
_BACKTEST_PROFILES: Mapping[str, frozenset[MarketType]] = {
    GRID_KIND_ID: PROFILE_MARKETS
}

#: What a kind is called, by `kind_id`.
_KIND_NAMES: Mapping[str, str] = {GRID_KIND_ID: "Grid"}

#: Which definition key holds the capital the bot may use, by `kind_id`; the
#: detail panel shows it beside every kind's profit.
KIND_CAPITAL_KEYS: Mapping[str, str] = {GRID_KIND_ID: "capital_quote"}


def kind_title(kind_id: str) -> str:
    """The kind as the user reads it: "Grid", on Spot and on Futures alike. The venue says
    which market; a kind with no name is shown by its id (`BUG-208`)."""
    return _KIND_NAMES.get(kind_id, kind_id)


def panel_for(kind_id: str) -> BotKindPanel:
    """@raise UnknownBotKindError No editor is registered for `kind_id`."""
    try:
        return _PANELS[kind_id]()
    except KeyError:
        raise UnknownBotKindError(kind_id) from None


def backtest_supports(kind_id: str, profile: VenueProfile | None) -> bool:
    """Whether `kind_id`'s backtest replays the market `profile` names. A venue with no
    profile is judged as before profiles existed: it is not turned away here."""
    markets = _BACKTEST_PROFILES.get(kind_id)
    return markets is not None and (profile is None or is_in_markets(profile, markets))


def backtest_for(kind_id: str, ports: BacktestPorts) -> BotBacktest | None:
    """`kind_id`'s backtest built on `ports`; `None` when the kind has none."""
    factory = _BACKTESTS.get(kind_id)
    return factory(ports) if factory is not None else None
