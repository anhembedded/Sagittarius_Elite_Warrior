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

**`EPIC-028A` — venues are a set now.** Every per-venue adapter is built by
`VenueAssembly` (one per enabled venue) and reached through `IVenueContexts`.
The single-venue ports below still resolve, to the *primary* venue's own
instances, so every existing caller keeps working unchanged until
`EPIC-028B` makes each command name its venue and deletes them.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_session_factory import (
    FuturesSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_session_factory import (
    SpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_assembly import (
    SharedVenueInputs,
    VenueAssembly,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_contexts import (
    VenueContexts,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    TradingLimits,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitPolicy,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    resolve_trading_venues,
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
from sagittarius_engine.utils.path_utils import PathUtils


def bind_adapters(container: IContainer) -> None:
    """Bind this context's ports to the adapters that implement them."""
    # EPIC-024A: ExecuteOrderCommandHandler/EnableTradingCommandHandler/
    # EmergencyStopCommandHandler depend on this port, not the concrete
    # factory, so they auto-wire to this same shared instance rather than
    # the container silently constructing each of them a throwaway one.
    session_factory = FuturesSessionFactory()
    container.singleton(ITradingSessionFactory, session_factory)

    # EPIC-021B: `secrets.local.json` lives next to `user_config.json`
    # (gitignored, unlike it). `__file__` is three directories deep
    # (`modules/trading/composition/`), so three `..` segments land back on
    # `src/config/secrets.local.json` — the same file
    # `scripts/epic021b_credentials_probe.py` and `tests/testnet/conftest.py`
    # resolve from their own locations.
    secrets_file_path = PathUtils.get_relative_path(
        __file__, "..", "..", "..", "config", "secrets.local.json"
    )

    # EPIC-028A: lazy, like every binding here — `register()` may not
    # `resolve(IConfig)` (this file's own module docstring).
    container.singleton(
        VenueContexts,
        lambda c: _build_venue_contexts(
            c,
            SharedVenueInputs(
                container=c,
                futures_session_factory=session_factory,
                spot_session_factory=SpotSessionFactory(),
                secrets_file_path=secrets_file_path,
            ),
        ),
    )
    container.singleton(IVenueContexts, lambda c: c.resolve(VenueContexts))

    # The primary venue — the first enabled one, `DISABLED` when none is.
    # With only the legacy scalar `exchange.trading_venue` configured this is
    # exactly that value, as before `EPIC-028A`.
    container.singleton(TradingVenue, lambda c: c.resolve(VenueContexts).primary_venue)

    # Single-venue doors, all onto the primary venue's own instances (see this
    # file's module docstring). Deleted by `EPIC-028B`.
    container.singleton(
        IExchangeCredentialsProvider, lambda c: _primary(c).credentials_provider
    )
    container.singleton(ISymbolOrderMetadataCache, lambda c: _primary(c).metadata_cache)
    container.singleton(
        IMarketMetadataProvider, lambda c: _primary(c).metadata_provider
    )
    container.singleton(ITradingClientFactory, lambda c: _primary(c).client_factory)
    container.singleton(ITradingAccountReader, lambda c: _primary(c).account_reader)
    container.singleton(EquityCurveRecorder, lambda c: _primary(c).equity_recorder)
    container.singleton(IUserDataStream, lambda c: _primary(c).user_data_stream)

    # EPIC-021G: the four trading limits, all on by default — see
    # TradingLimitPolicy's own docstring for why there is no "disable this
    # one" toggle, only these numeric thresholds. Stateless thresholds, so one
    # policy serves every venue; the per-venue counters it reads live in each
    # venue's own `TradingSessionState`.
    container.singleton(TradingLimitPolicy, _build_trading_limit_policy)


def _build_venue_contexts(
    container: IContainer, shared: SharedVenueInputs
) -> VenueContexts:
    """Every venue's assembly gets the same `shared` inputs, so the
    stateless session factories are built once per process, not per venue."""
    return VenueContexts(
        resolve_trading_venues(container.resolve(IConfig)),
        lambda venue: VenueAssembly(venue, shared),
    )


def _primary(container: IContainer) -> VenueAssembly:
    return container.resolve(VenueContexts).primary_assembly()


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
