"""What the Market mode needs, resolved once from the container (`EPIC-033H`).

One value (`code/quality.md` §7), built by `market_dependencies_for`, so the
presenter is constructed with its ports rather than reaching into the
container for each, and a test builds the value from fakes.

The mode shows Spot or Futures candles, as the person chooses (`EPIC-033Q`):
a candle feed is bound to one market (`MarketDataCandleFeed`), so there is
one feed per market the mode offers, and the chosen one is remembered
through the UI state store when the application has one.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.market_data_candle_feed import (
    MarketDataCandleFeed,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
    IAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    ICandleFeed,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_params_store import (
    IndicatorScriptParamsStore,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.app_defaults import (
    FALLBACK_INTERVAL,
    default_interval,
    default_symbol_options,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.container_lookup import (
    find_state_coordinator,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.ui_state_coordinator import (
    UiStateCoordinator,
)
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

#: The markets the mode offers, in menu order: Spot and the USDⓈ-M Futures the
#: Futures desk trades (`desk_profile.py`).
MARKETS: tuple[MarketType, ...] = (MarketType.SPOT, MarketType.FUTURES_USD_M)
#: Until the person chooses, the mode watches Spot, as the Watchlist it
#: replaced always had.
DEFAULT_MARKET = MarketType.SPOT
#: The Watchlist's own floor when no symbols are configured.
FALLBACK_SYMBOLS: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "BNBUSDT")

ScriptParams = Callable[[str], Mapping[str, Any] | None]


@dataclass(frozen=True)
class MarketDependencies:
    """The stream, the charts' candles, the indicator scripts, the account
    the connection check asks, and where to start."""

    stream: IMarketStream
    #: One feed per market of `MARKETS`.
    candles: Mapping[MarketType, ICandleFeed]
    #: The stored candles a chart reads beyond its first window (`EPIC-033S`).
    history: IHistoricalKlines
    thread_manager: IThreadManager
    scripts: IndicatorScriptRegistry
    #: A script's saved parameters (Tools → the Dev Board's script dialog),
    #: read on each build so an edit applies to the next chart drawn.
    script_params: ScriptParams
    account: IAccountSnapshot
    symbols: tuple[str, ...]
    interval: str
    #: Where the chosen market is remembered; `None` keeps the default.
    state: UiStateCoordinator | None = None


def market_dependencies_for(container: IContainer) -> MarketDependencies:
    config = container.resolve(IConfig)
    values = config.get_all()
    stream = container.resolve(IMarketStream)
    params = IndicatorScriptParamsStore(config)
    sync = container.resolve(IMarketDataSync)
    history = container.resolve(IHistoricalKlines)
    return MarketDependencies(
        stream=stream,
        candles={
            market: MarketDataCandleFeed(sync, history, stream, market)
            for market in MARKETS
        },
        history=history,
        thread_manager=container.resolve(IThreadManager),
        scripts=container.resolve(IndicatorScriptRegistry),
        script_params=lambda key: params.load_all().get(key),
        account=container.resolve(IAccountSnapshot),
        symbols=tuple(default_symbol_options(values, FALLBACK_SYMBOLS)),
        interval=default_interval(values, FALLBACK_INTERVAL),
        state=find_state_coordinator(container),
    )
