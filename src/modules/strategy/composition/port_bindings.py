"""This module's published ports, bound to their implementations.

Mirrors `modules/trading/composition/port_bindings.py`: the module's own
`register()` binds **only what it publishes**, and the rest of the strategy
bindings stay in `binance_bot_module.py` — the composition root the strangler is
replacing, which the boundary scan skips by name and which shrinks one phase at
a time.

Why a lambda rather than construction here. `LiveStrategySession` is already a
singleton registered by that strangler root, built from a factory that needs
`IEventPublisher`, `IOrderSubmission`, `ITradingAccountReader` and
`IMarketMetadataProvider`. Building a *second* session here would mean two
armed states — one the tick path drives, one the screens read — which is the
class of bug `ExchangeSessionFactory` took four pull requests to get out of
(PR 1.3c-4). Resolving the existing one inside a factory lambda keeps one
instance, and the lambda runs at first `resolve()`, never during `register()`,
which SDD §4 forbids from resolving anything.

The bindings move here properly in PR 2.1d, with `ISizingPolicy` — that pull
request already has to touch the factory's arguments.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_session import (
    LiveStrategySession,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_armed_strategy import (
    IArmedStrategy,
)
from sagittarius_engine.interfaces.i_container import IContainer


def bind_published_ports(container: IContainer) -> None:
    """`IArmedStrategy`, onto the one live session that already exists."""
    container.singleton(IArmedStrategy, _the_live_session)


def _the_live_session(container: IContainer) -> IArmedStrategy:
    return container.resolve(LiveStrategySession)
