"""`EPIC-028A` — the one place a venue's live-trading adapters are built.

@details Absorbs the `TradingVenue` branches `adapter_bindings.py` carried one
per port (`EPIC-027G`–`027L`). Each part is built on first use and cached, so
asking for one venue's metadata provider never builds its user data stream —
and never resolves `IEventBus`/`ITaskManager`, which a caller that only wants
rounding rules may not have bound.

Everything a venue owns is its own: credentials for its own env-var pair, its
own metadata cache (a Futures and a Spot `BTCUSDT` are different
instruments), its own `TradingSessionState` and `EquityCurveRecorder` wired
into its own user data stream (the state itself is owned by
`VenueSessionStates`, `EPIC-028B`). `DISABLED` builds the Futures-shaped read-only
adapters the process has always bound while trading is off.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Self, overload

from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_reader import (
    FuturesAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_metadata_provider import (
    FuturesMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_session_factory import (
    FuturesSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client_factory import (
    FuturesTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_user_data_stream import (
    FuturesUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_account_reader import (
    SpotAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_metadata_provider import (
    SpotMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_session_factory import (
    SpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_trading_client_factory import (
    SpotTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_user_data_stream import (
    SpotUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_session_states import (
    VenueSessionStates,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_symbol_order_metadata_cache import (
    ISymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client_factory import (
    ITradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_user_data_stream import (
    IUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_context import (
    VenueContext,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    EnvFirstCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.secrets_file_source import (
    SecretsFileSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_task_manager import ITaskManager


@dataclass(frozen=True)
class SharedVenueInputs:
    """What every venue's assembly shares: the stateless session factories,
    the secrets-file path and the registry that owns each venue's session
    state. The container is only asked for `IEventBus`/`ITaskManager`, and
    only when a user data stream is built."""

    container: IContainer
    futures_session_factory: FuturesSessionFactory
    spot_session_factory: SpotSessionFactory
    secrets_file_path: str
    session_states: VenueSessionStates


class _LockedCachedProperty[T](cached_property[T]):
    """`cached_property` that builds under the instance's `_lock`.

    @details Python 3.12 removed `cached_property`'s own lock, so two threads
    asking for an unbuilt part could each build one — a second metadata cache,
    or a second user data stream on one account (`EPIC-028A` review F1). The
    instance lock is re-entrant because a part builds the parts it depends on.
    """

    @overload
    def __get__(self, instance: None, owner: type[Any] | None = None) -> Self: ...
    @overload
    def __get__(self, instance: object, owner: type[Any] | None = None) -> T: ...
    def __get__(self, instance: object | None, owner: type[Any] | None = None) -> Any:
        if instance is None:
            return self
        with instance._lock:  # type: ignore[attr-defined]
            return super().__get__(instance, owner)


class VenueAssembly:
    """Builds and caches one venue's adapters and per-venue state."""

    def __init__(self, venue: TradingVenue, shared: SharedVenueInputs) -> None:
        self._venue = venue
        self._shared = shared
        self._lock = threading.RLock()

    @property
    def venue(self) -> TradingVenue:
        return self._venue

    @property
    def _is_spot(self) -> bool:
        return self._venue is TradingVenue.SPOT_TESTNET

    @_LockedCachedProperty
    def credentials_provider(self) -> IExchangeCredentialsProvider:
        return EnvFirstCredentialsProvider(
            SecretsFileSource(self._shared.secrets_file_path), self._venue
        )

    @_LockedCachedProperty
    def metadata_cache(self) -> ISymbolOrderMetadataCache:
        return InMemorySymbolOrderMetadataCache()

    @_LockedCachedProperty
    def metadata_provider(self) -> IMarketMetadataProvider:
        if self._is_spot:
            return SpotMetadataProvider(
                self._shared.spot_session_factory, self.metadata_cache
            )
        return FuturesMetadataProvider(
            self._shared.futures_session_factory, self.metadata_cache
        )

    @_LockedCachedProperty
    def client_factory(self) -> ITradingClientFactory:
        if self._is_spot:
            return SpotTradingClientFactory(
                self._shared.spot_session_factory,
                self.credentials_provider,
                self.metadata_provider,
            )
        return FuturesTradingClientFactory(
            self._shared.futures_session_factory,
            self.credentials_provider,
            self.metadata_provider,
        )

    @_LockedCachedProperty
    def account_reader(self) -> ITradingAccountReader:
        if self._is_spot:
            return SpotAccountReader(
                self._shared.spot_session_factory, self.credentials_provider
            )
        return FuturesAccountReader(
            self._shared.futures_session_factory, self.credentials_provider
        )

    @property
    def session_state(self) -> TradingSessionState:
        """Owned by `VenueSessionStates` (`EPIC-028B`), so the handlers that
        act on this venue and its user data stream share one object."""
        return self._shared.session_states.session_state(self._venue)

    @property
    def equity_recorder(self) -> EquityCurveRecorder:
        return self._shared.session_states.equity_recorder(self._venue)

    @_LockedCachedProperty
    def user_data_stream(self) -> IUserDataStream:
        event_bus = self._shared.container.resolve(IEventBus)
        task_manager = self._shared.container.resolve(ITaskManager)
        if self._is_spot:
            return SpotUserDataStream(
                event_bus,
                task_manager,
                self.credentials_provider,
                self.account_reader,
                self.equity_recorder,
            )
        return FuturesUserDataStream(
            event_bus,
            task_manager,
            self.credentials_provider,
            self.client_factory,
            self.session_state,
            self.equity_recorder,
        )

    @_LockedCachedProperty
    def context(self) -> VenueContext:
        return VenueContext(
            venue=self._venue,
            credentials_provider=self.credentials_provider,
            metadata_cache=self.metadata_cache,
            metadata_provider=self.metadata_provider,
            client_factory=self.client_factory,
            account_reader=self.account_reader,
            user_data_stream=self.user_data_stream,
        )
