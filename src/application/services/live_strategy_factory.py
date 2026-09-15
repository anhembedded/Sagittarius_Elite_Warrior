"""`EPIC-022A` — builds the (engine, coordinator) pair one
`LiveStrategyConfig` describes.

@details This is the block that used to live inline inside
`binance_bot_module.py::boot()`, lifted out for one reason: boot could
only ever run it **once**, at startup, from config. A user picking a
strategy on the Trading screen needs the same construction to happen
again, mid-session, with different values — so it has to be callable, not
a stretch of startup script.

Both objects are rebuilt together on purpose. `LiveTradingCoordinator`
bakes `live_symbol`/`sizing_percent`/`leverage` in at construction, and
`StrategyEngine`'s indicators carry mutable incremental state
(`BOT-042B`/`C`), so there is no such thing as "keep the engine, swap the
sizing": every field of `LiveStrategyConfig` invalidates one of the two.
Rebuilding both is what makes a re-arm honest rather than a partial
update nobody can reason about.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.application.services.live_trading_coordinator import (
    LiveTradingCoordinator,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_engine import (
    StrategyEngine,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_factory import (
    build_engine,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.live_strategy_config import (
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
    IOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)

logger = logging.getLogger("App.LiveStrategyFactory")


class LiveStrategyFactory:
    """@brief Turns a chosen `LiveStrategyConfig` into the two live objects
    that actually run it."""

    def __init__(
        self,
        registry: StrategyRegistry,
        event_publisher: IEventPublisher,
        order_submission: IOrderSubmission,
        account_reader: ITradingAccountReader,
        metadata_provider: IMarketMetadataProvider,
    ) -> None:
        self._registry = registry
        self._event_publisher = event_publisher
        self._order_submission = order_submission
        self._account_reader = account_reader
        self._metadata_provider = metadata_provider

    @property
    def registry(self) -> StrategyRegistry:
        """@brief The same registry the engines are built from.

        @details Exposed so a caller validating a key/params pair before
        arming (`ArmStrategyCommandHandler`) checks against exactly the
        registry this factory would build from, rather than resolving a
        second one from the container and hoping they match.
        """
        return self._registry

    def build(
        self, config: LiveStrategyConfig
    ) -> tuple[StrategyEngine, LiveTradingCoordinator]:
        """
        @raises ValueError If the strategy key is not registered, or a
        parameter the config carries is not one the strategy declares —
        both raised by `StrategyRegistry.create()`/`BaseStrategy.__init__`,
        deliberately not re-validated here (one validator, not two).
        """
        engine = build_engine(
            self._registry,
            config.strategy_key,
            self._event_publisher,
            config.strategy_params,
        )
        coordinator = LiveTradingCoordinator(
            config.symbol,
            self._order_submission,
            self._account_reader,
            self._metadata_provider,
            self._event_publisher,
            config.sizing_percent,
            config.leverage,
        )
        logger.info(
            "Built live strategy '%s' for %s %s (sizing %.2f%%, leverage %.2fx).",
            config.strategy_key,
            config.symbol,
            config.interval,
            config.sizing_percent,
            config.leverage,
        )
        return engine, coordinator
