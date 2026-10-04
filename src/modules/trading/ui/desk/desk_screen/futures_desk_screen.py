"""`EPIC-028K` — the Futures desk: `trading.futures`, Futures Testnet's own
screen (`desk_factories.py` holds what it shares with the Spot desk)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.contracts.nav_metadata import NavMetadata
from Sagittarius_Elite_Warrior.src.core.contracts.screen_contribution import (
    ScreenContribution,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_factories import (
    desk_factories,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

FUTURES_DESK_ROUTE = "trading.futures"


def futures_desk_screen(container: IContainer) -> ScreenContribution:
    """Beside the single Trading screen (item 15) until `EPIC-028M`.

    The default mode (`EPIC-033C`): the first run opens here; later runs open
    on the mode the last one ended in. Welcome, which used to be the default,
    is gone, and its Start button already led here."""
    factories = desk_factories(container, TradingVenue.FUTURES_TESTNET)
    return ScreenContribution(
        contributor_id="trading",
        route=FUTURES_DESK_ROUTE,
        view_factory=factories.view,
        presenter_factory=factories.presenter,
        nav=NavMetadata(
            title="Futures",
            icon="chart-candlestick",
            section_sequence=10,
            item_sequence=16,
        ),
        is_default=True,
    )
