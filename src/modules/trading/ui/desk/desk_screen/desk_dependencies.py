"""`EPIC-028K` — everything one desk is built from, already bound to its
venue, and where it comes from.

@details The presenter takes this value rather than reaching into the
container for each port (`async-ui-action-rule.md` §2: collaborators are
injected), so a test builds a desk from verified fakes and the screen
factory builds it from the app's own bindings (`desk_dependencies_for`).
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_chart_overlay_reader import (
    IStrategyChartOverlayReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_strategy_controls import (
    IVenueStrategyControls,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_strategy_controls import (
    VenueStrategyControls,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_trading_ports import (
    VenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_chart_ports import (
    DeskChartPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_confirmation import (
    ConfirmOrder,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.app_defaults import (
    FALLBACK_INTERVAL,
    default_interval,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.filter_precisions import (
    FilterPrecisions,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.i_symbol_precisions import (
    ISymbolPrecisions,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.no_symbol_precisions import (
    NO_SYMBOL_PRECISIONS,
)
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


@dataclass(frozen=True)
class DeskDependencies:
    """One desk's ports: its venue's trading ports and armed strategy (the
    chart draws it), the chart's market data, how an order is confirmed,
    and the symbols' filters its tables write numbers in."""

    ports: VenueTradingPorts
    strategy: VenueStrategyControls
    chart: DeskChartPorts
    thread_manager: IThreadManager
    #: `None` asks with the real dialog (`confirm_with_message_box`).
    confirm: ConfirmOrder | None = None
    #: The venue's tick and step sizes the account tabs write prices and
    #: sizes in; none known keeps the formatter's magnitude rule.
    precisions: ISymbolPrecisions = NO_SYMBOL_PRECISIONS


def stream_owner_for(venue: TradingVenue) -> str:
    """The desk's own owner on `IMarketStream`, one per venue."""
    return f"desk.{venue.value}"


def desk_dependencies_for(
    container: IContainer, venue: TradingVenue
) -> DeskDependencies:
    """The app's own ports for `venue`'s desk.
    @raise VenueNotEnabledError `venue` is not served."""
    ports = container.resolve(IVenueTradingPorts).get(venue)
    threads = container.resolve(IThreadManager)
    interval = default_interval(container.resolve(IConfig).get_all(), FALLBACK_INTERVAL)
    market = venue.market_type
    if market is None:
        raise ValueError(f"{venue.value} trades no market; it has no desk")
    return DeskDependencies(
        ports=ports,
        strategy=container.resolve(IVenueStrategyControls).get(venue),
        chart=DeskChartPorts(
            thread_manager=threads,
            market_data_sync=container.resolve(IMarketDataSync),
            historical_klines=container.resolve(IHistoricalKlines),
            market_stream=container.resolve(IMarketStream),
            overlay=container.resolve(IStrategyChartOverlayReader),
            market=market,
            stream_owner=stream_owner_for(venue),
            interval=interval,
        ),
        thread_manager=threads,
        precisions=FilterPrecisions(
            container.resolve(IVenueContexts).get(venue).metadata_cache
        ),
    )
