"""Which concrete class answers each of trading's ports.

`EPIC-025E` PR 4.4f-4 — the third of `binance_bot_module.py`'s remaining
bindings to move (after 4.4f-1's backtesting slice and 4.4f-2's strategy
slice; 4.4f-3 moved `market_data`'s own leftover venue/session-factory pair).
This is the largest slice: everything the legacy composition root still held
that is genuinely `trading`'s own — the session factory, the metadata cache,
the credentials provider, the account reader, the equity recorder, the
user-data stream, and the trading-limits policy. Same shape as
`market_data/composition/adapter_bindings.py`: one function, called from
`TradingModule.register()`.

**One binding did not fit here.** `ITradingClient` was registered
*conditionally* in the legacy root — only when `TradingVenue != DISABLED`
(EPIC-021F), because resolving it while trading is off must fail loudly
(`DependencyResolutionError`, an unbound type) rather than hand back a
client nobody asked to enable (`tests/sanity/test_composition_root.py`'s
`_NOT_DISPATCHED` entry for `SubmitOrderCommand` depends on this). Deciding
that conditional needs `TradingVenue`'s actual resolved value, and
`register()` may not `resolve()` (`Docs/SDD/04_boot_and_configuration.md`'s
register/boot table — the `RegisteringContainer` this module's `register()`
sees raises on any `resolve()` call, config included, which the legacy
`BaseModule.register(app)` never had to honour). `TradingModule.boot()` runs
after every module has registered, `resolve()` is allowed there, and it is
where this module's own `PositionRefreshService` scheduling already lived —
so the conditional bind moved there too, alongside it. `TradingVenue` itself
stays a plain lazy singleton here, matching every other binding in this file;
only the *conditional bind of a second type* needed `boot()`.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.futures_symbol_metadata_cache import (
    InMemoryFuturesSymbolMetadataCache,
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
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_user_data_stream import (
    FuturesUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_futures_symbol_metadata_cache import (
    IFuturesSymbolMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_user_data_stream import (
    IUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    TradingLimits,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitPolicy,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    EnvFirstCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.secrets_file_source import (
    SecretsFileSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    resolve_trading_venue,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionFactory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_task_manager import ITaskManager
from sagittarius_engine.utils.path_utils import PathUtils


def bind_adapters(container: IContainer) -> None:
    """Bind this context's ports to the adapters that implement them."""
    # EPIC-024A: ExecuteOrderCommandHandler/EnableTradingCommandHandler/
    # EmergencyStopCommandHandler depend on this port, not the concrete
    # factory, so they auto-wire to this same shared instance rather than
    # the container silently constructing each of them a throwaway one.
    session_factory = FuturesSessionFactory()
    container.singleton(ITradingSessionFactory, session_factory)

    # EPIC-021C: `FuturesMetadataProvider` takes the concrete factory, not
    # `ITradingSessionFactory` — `create_futures_metadata_client()` is
    # deliberately not on that port (see the factory's own docstring), and
    # both are `trading`'s own adapters, so there is no boundary between
    # them to put one across.
    container.singleton(IFuturesSymbolMetadataCache, InMemoryFuturesSymbolMetadataCache)
    container.singleton(
        IMarketMetadataProvider,
        lambda c: FuturesMetadataProvider(
            session_factory, c.resolve(IFuturesSymbolMetadataCache)
        ),
    )

    # EPIC-021B: `secrets.local.json` lives next to `user_config.json`
    # (gitignored, unlike it) — same relative-path idiom `main.py` uses for
    # the config files themselves. `EPIC-025E` PR 4.4f-4 moved this call out
    # of `binance_bot_module.py`: `__file__` now points three directories
    # deeper (`modules/trading/composition/`), so the walk-up needs three
    # `..` segments to land back on `src/config/secrets.local.json` — the
    # same file `scripts/epic021b_credentials_probe.py` and
    # `tests/testnet/conftest.py` already resolve from their own locations.
    secrets_file_path = PathUtils.get_relative_path(
        __file__, "..", "..", "..", "config", "secrets.local.json"
    )
    credentials_provider = EnvFirstCredentialsProvider(
        SecretsFileSource(secrets_file_path)
    )
    container.singleton(IExchangeCredentialsProvider, credentials_provider)

    # EPIC-021D: read-only, does not require TradingVenue to be "enabled"
    # anywhere — see FuturesAccountReader's own docstring for why this check
    # works off credentials alone.
    container.singleton(
        ITradingAccountReader,
        FuturesAccountReader(session_factory, credentials_provider),
    )

    # EPIC-021H: read-only like ITradingAccountReader — registered
    # unconditionally (not gated on TradingVenue, unlike ITradingClient in
    # `TradingModule.boot()`) so EnableTradingCommandHandler stays
    # constructible regardless of trading being enabled. Nothing calls
    # `.start()` on it except that handler's own successful-enable path —
    # the app never opens this stream merely by booting.
    # `EPIC-021M` — registered here, not lazily inside the lambda below, so
    # the Trading screen's equity chart can resolve the *same* instance
    # regardless of whether the stream has started yet (both sides
    # read/write through one shared singleton).
    container.singleton(EquityCurveRecorder, EquityCurveRecorder())

    container.singleton(
        IUserDataStream,
        lambda c: FuturesUserDataStream(
            c.resolve(IEventBus),
            c.resolve(ITaskManager),
            session_factory,
            credentials_provider,
            c.resolve(IMarketMetadataProvider),
            c.resolve(TradingSessionState),
            c.resolve(EquityCurveRecorder),
        ),
    )

    # EPIC-021A/EPIC-021F: a lazy singleton, matching every other binding in
    # this file — `register()` may not `resolve(IConfig)`, so the factory
    # below runs on first resolve rather than now. Unlike the legacy root,
    # this alone does *not* decide whether `ITradingClient` gets bound (see
    # this file's own module docstring); `TradingModule.boot()` resolves
    # this same singleton to make that call.
    container.singleton(
        TradingVenue, lambda c: resolve_trading_venue(c.resolve(IConfig))
    )

    # EPIC-021G: the four trading limits, all on by default — see
    # TradingLimitPolicy's own docstring for why there is no "disable this
    # one" toggle, only these numeric thresholds. Lazy for the same reason
    # as `TradingVenue` above.
    container.singleton(TradingLimitPolicy, _build_trading_limit_policy)


def _build_trading_limit_policy(container: IContainer) -> TradingLimitPolicy:
    config = container.resolve(IConfig)
    trading_limits = TradingLimits(
        max_orders_per_session=int(
            config.get(ConfigKeys.TRADING_MAX_ORDERS_PER_SESSION.value, 20)
        ),
        max_notional_per_order=Decimal(
            str(config.get(ConfigKeys.TRADING_MAX_NOTIONAL_PER_ORDER_USDT.value, 500))
        ),
        max_positions_per_symbol=int(
            config.get(ConfigKeys.TRADING_MAX_POSITIONS_PER_SYMBOL.value, 1)
        ),
        min_order_interval=timedelta(
            seconds=int(
                config.get(ConfigKeys.TRADING_MIN_ORDER_INTERVAL_SECONDS.value, 60)
            )
        ),
    )
    return TradingLimitPolicy(trading_limits)
