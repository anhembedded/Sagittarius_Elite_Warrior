"""`EPIC-028L` — the Spot desk: `trading.spot`, Spot Testnet's own screen
(`desk_factories.py` holds what it shares with the Futures desk)."""

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

SPOT_DESK_ROUTE = "trading.spot"


def spot_desk_screen(container: IContainer) -> ScreenContribution:
    """After the Futures desk (item 16)."""
    factories = desk_factories(container, TradingVenue.SPOT_TESTNET)
    return ScreenContribution(
        contributor_id="trading",
        route=SPOT_DESK_ROUTE,
        view_factory=factories.view,
        presenter_factory=factories.presenter,
        nav=NavMetadata(
            title="Spot",
            icon="chart-candlestick",
            section_sequence=10,
            item_sequence=17,
        ),
    )
