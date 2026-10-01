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

**`EPIC-028A` — venues are a set now.** Every per-venue adapter is built by
`VenueAssembly` (one per enabled venue) and reached through `IVenueContexts`.

**`EPIC-028B` — no single-venue door is left.** The per-venue ports
(credentials, metadata cache and provider, client factory, account reader,
user-data stream) are bound nowhere on their own: a caller names the venue
it acts on and reads that venue's `VenueContext`. Only `TradingVenue`, the
*primary* venue, is still bound, for the screens that show one venue until
the two desks exist (`EPIC-028K`/`L`/`M`). `ITradingClient` was bound
conditionally in `TradingModule.boot()` before this; each handler now
creates it from the venue's own `client_factory`.
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
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_session_states import (
    VenueSessionStates,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_assembly import (
    SharedVenueInputs,
    VenueAssembly,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_contexts import (
    VenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    DEFAULT_TRADING_LIMITS,
    TradingLimits,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitPolicy,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    resolve_trading_venues,
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
                session_states=c.resolve(VenueSessionStates),
            ),
        ),
    )
    container.singleton(IVenueContexts, lambda c: c.resolve(VenueContexts))

    # The primary venue — the first enabled one, `DISABLED` when none is.
    # With only the legacy scalar `exchange.trading_venue` configured this is
    # exactly that value, as before `EPIC-028A`.
    container.singleton(TradingVenue, lambda c: c.resolve(VenueContexts).primary_venue)

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


def _build_trading_limit_policy(container: IContainer) -> TradingLimitPolicy:
    config = container.resolve(IConfig)
    defaults = DEFAULT_TRADING_LIMITS
    trading_limits = TradingLimits(
        max_orders_per_session=int(
            config.get(
                ConfigKeys.TRADING_MAX_ORDERS_PER_SESSION.value,
                defaults.max_orders_per_session,
            )
        ),
        max_notional_per_order=Decimal(
            str(
                config.get(
                    ConfigKeys.TRADING_MAX_NOTIONAL_PER_ORDER_USDT.value,
                    defaults.max_notional_per_order,
                )
            )
        ),
        max_positions_per_symbol=int(
            config.get(
                ConfigKeys.TRADING_MAX_POSITIONS_PER_SYMBOL.value,
                defaults.max_positions_per_symbol,
            )
        ),
        min_order_interval=timedelta(
            seconds=int(
                config.get(
                    ConfigKeys.TRADING_MIN_ORDER_INTERVAL_SECONDS.value,
                    int(defaults.min_order_interval.total_seconds()),
                )
            )
        ),
    )
    return TradingLimitPolicy(trading_limits)
