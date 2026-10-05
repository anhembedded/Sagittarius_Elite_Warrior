"""What the Market mode needs, resolved once from the container (`EPIC-033H`).

One value (`code/quality.md` §7), built by `market_dependencies_for`, so the
presenter is constructed with its ports rather than reaching into the
container for each, and a test builds the value from fakes.
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
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

#: The mode watches Spot, as the Watchlist it replaces always has; a market
#: choice is the Trade mode's (`EPIC-033I`).
MARKET = MarketType.SPOT
#: The Watchlist's own floor when no symbols are configured.
FALLBACK_SYMBOLS: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "BNBUSDT")

ScriptParams = Callable[[str], Mapping[str, Any] | None]


@dataclass(frozen=True)
class MarketDependencies:
    """The stream, the charts' candles, the indicator scripts, the account
    the connection check asks, and where to start."""

    stream: IMarketStream
    candles: ICandleFeed
    thread_manager: IThreadManager
    scripts: IndicatorScriptRegistry
    #: A script's saved parameters (Tools → the Dev Board's script dialog),
    #: read on each build so an edit applies to the next chart drawn.
    script_params: ScriptParams
    account: IAccountSnapshot
    symbols: tuple[str, ...]
    interval: str


def market_dependencies_for(container: IContainer) -> MarketDependencies:
    config = container.resolve(IConfig)
    values = config.get_all()
    stream = container.resolve(IMarketStream)
    params = IndicatorScriptParamsStore(config)
    return MarketDependencies(
        stream=stream,
        candles=MarketDataCandleFeed(
            container.resolve(IMarketDataSync),
            container.resolve(IHistoricalKlines),
            stream,
            MARKET,
        ),
        thread_manager=container.resolve(IThreadManager),
        scripts=container.resolve(IndicatorScriptRegistry),
        script_params=lambda key: params.load_all().get(key),
        account=container.resolve(IAccountSnapshot),
        symbols=tuple(default_symbol_options(values, FALLBACK_SYMBOLS)),
        interval=default_interval(values, FALLBACK_INTERVAL),
    )
