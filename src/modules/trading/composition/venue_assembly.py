"""`EPIC-028A` — the one place a venue's live-trading adapters are built.

@details Absorbs the `TradingVenue` branches `adapter_bindings.py` carried one
per port (`EPIC-027G`–`027L`). Each part is built on first use and cached, so
asking for one venue's metadata provider never builds its user data stream —
and never resolves `IEventBus`/`ITaskManager`, which a caller that only wants
rounding rules may not have bound (a Spot client factory resolves the bus: it
reports fills through it, `BOT-173`).

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

from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.cached_history_reader import (
    CachedAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_control import (
    FuturesAccountControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_reader import (
    FuturesAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_book_ticker_reader import (
    FuturesBookTickerReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_commission_rate_reader import (
    FuturesCommissionRateReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_history_reader import (
    FuturesHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_mark_price_reader import (
    FuturesMarkPriceReader,
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
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.listed_symbols import (
    ListedSymbols,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.api_restrictions_key_gate import (
    ApiRestrictionsKeyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.key_gated_credentials import (
    KeyGatedCredentials,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_account_reader import (
    SpotAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_book_ticker_reader import (
    SpotBookTickerReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_commission_rate_reader import (
    SpotCommissionRateReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_history_reader import (
    SpotHistoryReader,
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
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.venue_event_emitter import (
    VenueEventEmitter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.read_only_guard import (
    guarded_account_control,
    guarded_client_factory,
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
from Sagittarius_Elite_Warrior.src.modules.trading.composition.locked_cached_property import (
    LockedCachedProperty,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    IAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_book_ticker_reader import (
    IBookTickerReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_commission_rate_reader import (
    ICommissionRateReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_futures_account_control import (
    IFuturesAccountControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_key_permission_gate import (
    IKeyPermissionGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_mark_price_reader import (
    IMarkPriceReader,
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
    MainnetCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.secrets_file_source import (
    SecretsFileSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_secret_store import (
    ISecretStore,
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
    secrets_file_path: str
    session_states: VenueSessionStates
    #: Where a mainnet venue's key is kept (`EPIC-034` D10).
    secret_store: ISecretStore
    #: A copy of the app that may not trade gets read-only clients (`EPIC-035H`).
    instance: IInstanceAccess


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
        return self._venue.market_type is MarketType.SPOT

    @LockedCachedProperty
    def _futures_sessions(self) -> FuturesSessionFactory:
        """This venue's own session factory (`EPIC-034` D11): the venue is what
        tells it which exchange to open sessions on, so Futures Testnet and
        Futures Mainnet are this class with one argument different."""
        return FuturesSessionFactory(self._venue)

    @LockedCachedProperty
    def _spot_sessions(self) -> SpotSessionFactory:
        return SpotSessionFactory(self._venue)

    @LockedCachedProperty
    def credentials_provider(self) -> IExchangeCredentialsProvider:
        """The venue's stored key, as it is: what Options saves to and what the
        desk asks "is there a key" of. Adapters resolve `order_credentials`."""
        if self._venue.is_mainnet:
            # `EPIC-034` D10/D11 — a real-money secret lives in the keyring.
            return MainnetCredentialsProvider(self._shared.secret_store, self._venue)
        return EnvFirstCredentialsProvider(
            SecretsFileSource(self._shared.secrets_file_path), self._venue
        )

    @LockedCachedProperty
    def key_gate(self) -> IKeyPermissionGate | None:
        """A mainnet venue's refusal of a key that can move funds (`EPIC-034` D5);
        a testnet has none (no `apiRestrictions` there)."""
        if not self._venue.is_mainnet:
            return None
        stored = self.credentials_provider
        return ApiRestrictionsKeyGate(self._venue, lambda: stored.resolve().credentials)

    @LockedCachedProperty
    def order_credentials(self) -> IExchangeCredentialsProvider:
        """What every adapter of this venue resolves its key from: the stored
        key, and on a mainnet venue only while the key gate accepts it, so no
        read and no order goes out on a key that can withdraw."""
        gate = self.key_gate
        if gate is None:
            return self.credentials_provider
        return KeyGatedCredentials(self.credentials_provider, gate)

    @LockedCachedProperty
    def metadata_cache(self) -> ISymbolOrderMetadataCache:
        return InMemorySymbolOrderMetadataCache()

    @LockedCachedProperty
    def metadata_provider(self) -> IMarketMetadataProvider:
        if self._is_spot:
            return SpotMetadataProvider(self._spot_sessions, self.metadata_cache)
        return FuturesMetadataProvider(self._futures_sessions, self.metadata_cache)

    @LockedCachedProperty
    def client_factory(self) -> ITradingClientFactory:
        factory: ITradingClientFactory = (
            SpotTradingClientFactory(
                self._spot_sessions,
                self.order_credentials,
                self.metadata_provider,
                self.fill_events,
            )
            if self._is_spot
            else FuturesTradingClientFactory(
                self._futures_sessions, self.order_credentials, self.metadata_provider
            )
        )
        return guarded_client_factory(factory, self._shared.instance)

    @LockedCachedProperty
    def account_reader(self) -> ITradingAccountReader:
        if self._is_spot:
            return SpotAccountReader(
                self._spot_sessions, self.order_credentials, self._venue
            )
        return FuturesAccountReader(
            self._futures_sessions, self.order_credentials, venue=self._venue
        )

    @LockedCachedProperty
    def history_reader(self) -> IAccountHistoryReader:
        # `EPIC-028Q` — paging re-reads the whole span; the cache bounds the
        # request weight that costs.
        if self._is_spot:
            return CachedAccountHistoryReader(
                SpotHistoryReader(
                    self._spot_sessions,
                    self.order_credentials,
                    ListedSymbols(self.metadata_provider, self.metadata_cache),
                )
            )
        return CachedAccountHistoryReader(
            FuturesHistoryReader(self._futures_sessions, self.order_credentials)
        )

    @LockedCachedProperty
    def commission_reader(self) -> ICommissionRateReader:
        if self._is_spot:
            return SpotCommissionRateReader(self._spot_sessions, self.order_credentials)
        return FuturesCommissionRateReader(
            self._futures_sessions, self.order_credentials
        )

    @LockedCachedProperty
    def account_control(self) -> IFuturesAccountControl | None:
        """`EPIC-028F` — Spot has no leverage or margin mode, so it has no
        control; `DISABLED` keeps the Futures shape it has always had, and the
        handlers refuse it before reaching here."""
        if self._is_spot:
            return None
        return guarded_account_control(
            FuturesAccountControl(self._futures_sessions, self.order_credentials),
            self._shared.instance,
        )

    @LockedCachedProperty
    def book_ticker_reader(self) -> IBookTickerReader:
        if self._is_spot:
            return SpotBookTickerReader(self._spot_sessions)
        return FuturesBookTickerReader(self._futures_sessions)

    @LockedCachedProperty
    def mark_price_reader(self) -> IMarkPriceReader | None:
        """`EPIC-028O` — Spot has no mark price, so it has no reader, as it
        has no `account_control`."""
        if self._is_spot:
            return None
        return FuturesMarkPriceReader(self._futures_sessions)

    @property
    def session_state(self) -> TradingSessionState:
        """Owned by `VenueSessionStates` (`EPIC-028B`), so the handlers that
        act on this venue and its user data stream share one object."""
        return self._shared.session_states.session_state(self._venue)

    @property
    def equity_recorder(self) -> EquityCurveRecorder:
        return self._shared.session_states.equity_recorder(self._venue)

    @LockedCachedProperty
    def fill_events(self) -> VenueEventEmitter:
        """`BOT-173` — shared by the stream and the Spot client."""
        return VenueEventEmitter(
            self._shared.container.resolve(IEventBus),
            self._venue,
            self.session_state.owner_books,
        )

    @LockedCachedProperty
    def user_data_stream(self) -> IUserDataStream:
        task_manager = self._shared.container.resolve(ITaskManager)
        if self._is_spot:
            return SpotUserDataStream(
                self.fill_events,
                task_manager,
                self.order_credentials,
                self.account_reader,
                self.equity_recorder,
            )
        return FuturesUserDataStream(
            self.fill_events,
            task_manager,
            self.order_credentials,
            self.client_factory,
            self.session_state,
            self.equity_recorder,
        )

    @LockedCachedProperty
    def context(self) -> VenueContext:
        return VenueContext(
            venue=self._venue,
            credentials_provider=self.credentials_provider,
            key_gate=self.key_gate,
            metadata_cache=self.metadata_cache,
            metadata_provider=self.metadata_provider,
            client_factory=self.client_factory,
            account_reader=self.account_reader,
            user_data_stream=self.user_data_stream,
            history_reader=self.history_reader,
            commission_reader=self.commission_reader,
            account_control=self.account_control,
            book_ticker_reader=self.book_ticker_reader,
            mark_price_reader=self.mark_price_reader,
        )
