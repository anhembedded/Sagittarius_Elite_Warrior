"""`EPIC-047H` — what the host reads and writes for the VPS tab, bound in one place.

@details The settings (judged once, `VpsFeedSettings`), the market recorder, the facts refresher with its
worker, and the port that asks the worker for a read (`IFactsRefreshRequests`) are singletons of the module;
`OperationsModule.boot()` starts the workers of a writable copy and `shutdown()` ends them. Nothing here
starts a thread or reads the exchange at registration.
"""

from __future__ import annotations

import logging
import time

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.vo.market_timeframes import (
    DEFAULT_CHART_TIMEFRAMES,
)
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_read_refresh import (
    IBotReadRefresh,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.facts_refreshing import (
    FactsRefreshing,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.market_recorder import (
    MarketRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.vps_facts_refresher import (
    FactsRefresher,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.vps_refresh_work import (
    RefreshWake,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_facts_refresh_requests import (
    IFactsRefreshRequests,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_market_snapshots import (
    IMarketSnapshots,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.vps_feed_settings import (
    CEILING_DEFAULT_PCT,
    REFRESH_INTERVAL_DEFAULT_S,
    VpsFeedSettings,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_mark_board import (
    IMarkBoard,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_weight_meter import (
    IVenueWeightMeter,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_container import IContainer

logger = logging.getLogger("App.Operations")


def bind_vps_feed(container: IContainer) -> None:
    container.singleton(VpsFeedSettings, _settings)
    container.singleton(
        MarketRecorder,
        lambda c: MarketRecorder(
            [TimeFrame(code) for code in DEFAULT_CHART_TIMEFRAMES],
            c.resolve(IVenueContexts).enabled,
            c.resolve(IMarkBoard),
            c.resolve(IOperationsClock),
        ),
    )
    container.singleton(IMarketSnapshots, lambda c: c.resolve(MarketRecorder))
    container.singleton(RefreshWake, RefreshWake())
    container.singleton(FactsRefresher, _refresher)
    container.singleton(IFactsRefreshRequests, lambda c: c.resolve(FactsRefresher))
    container.singleton(
        FactsRefreshing,
        lambda c: FactsRefreshing(c.resolve(FactsRefresher), c.resolve(RefreshWake)),
    )


def _settings(container: IContainer) -> VpsFeedSettings:
    config = container.resolve(IConfig)
    settings = VpsFeedSettings.judged(
        float(
            config.get(
                ConfigKeys.OPERATIONS_VPS_FACTS_REFRESH_INTERVAL_S.value,
                REFRESH_INTERVAL_DEFAULT_S,
            )
        ),
        float(
            config.get(
                ConfigKeys.OPERATIONS_VPS_FACTS_WEIGHT_CEILING_PCT.value,
                CEILING_DEFAULT_PCT,
            )
        ),
        bool(config.get(ConfigKeys.OPERATIONS_VPS_MARKET_RECORDER_ENABLED.value, True)),
    )
    for note in settings.notes:
        logger.warning("[vps-feed] setting adjusted: %s [vps-feed-setting]", note)
    return settings


def _refresher(container: IContainer) -> FactsRefresher:
    contexts = container.resolve(IVenueContexts)

    def meter_of(venue: TradingVenue) -> IVenueWeightMeter | None:
        try:
            return contexts.get(venue).weight_meter
        except VenueNotEnabledError:
            return None

    return FactsRefresher(
        container.resolve(IBotReadRefresh),
        meter_of,
        container.resolve(VpsFeedSettings),
        time.monotonic,
        time.time,
        container.resolve(RefreshWake).set,
    )
