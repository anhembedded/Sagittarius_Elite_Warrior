"""`trading` as one Engine extension — the second real module (HLD §3.2, §3.4).

This is the only file under `modules/trading/` that `shell/` may import
(`is_module_entry_point` in the boundary guard). `shell/modules.py` lists the
class; `shell/module_registration.py` instantiates it and hands it to
`app.use()`.

**The context's one question:** *what is this account's position in the market,
and how does an order get there?* Order shaping and submission, the live
trading session and its limits, positions and open orders as a read model, the
account's own connection state. Deciding *whether* to send an order — a signal,
a strategy, a backtest — belongs to another context and reaches this one
through `contracts/`.

@par Why `register()` binds only the published ports, unlike `market_data`'s
PR 1.3a moved this context's code under `modules/trading/`; PR 1.3b published
its first three ports and bound them here, PR 1.3c-3 added `IEquityCurve`.
What is still **not** here is every adapter and handler registration.

The reason used to be a single shared object: one `ExchangeSessionFactory`
answered both this context's `ITradingSessionFactory` and `market_data`'s
`IExchangeSessionFactory`, so moving the registrations here meant either
resolving that instance from the container or building a second one — a
behaviour change ADR D12 keeps out of a move.

**PR 1.3c-4 did the split**, which the allowlist had scheduled since PR 0.4a
("one factory per context"): `FuturesSessionFactory` is this module's adapter,
`MarketDataSessionFactory` is the other module's, and both mint their sessions
through `support/binance_gateway`, still the one place allowed to construct a
`python-binance` `Client`. So the blocker is gone; what remains is the move
itself, which is PR 1.4's along with the surfaces — the registrations also
name the credentials provider, the limits policy and the user-data stream's
hosted-service lifetime, and moving a dozen bindings is its own change rather
than a rider on the split that unblocked them.

Until then `binance_bot_module.py` registers them, which costs no boundary
violation: the boundary scan skips that file by name
(`tests/unit/architecture/boundaries/scan.py`) because it *is* the composition
root the strangler is replacing. `composition/port_bindings.py` explains which
ports could move early and why.

**Hooks not implemented, and why:**

- `contribute()` — Trading and the Dev Board are still legacy screens carried
  by `shell/legacy_screen_adapter.py`. PR 1.4 turns them into the surfaces
  `surfaces/trading/` and `surfaces/dev_board/`, which is where the contributed
  panels, dialogs and actions arrive.
- `subscribe()` — this context's Qt-side subscriptions still live in the two
  legacy Presenters and move with them in PR 1.4.

Both are defaults inherited from `BoundedContextModule`, so the absence is a
statement, not an omission.
"""

from __future__ import annotations

import logging
from typing import Any

from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.port_bindings import (
    bind_published_ports,
)

logger = logging.getLogger("App.TradingModule")


class TradingModule(BoundedContextModule):
    """Order submission, the live trading session, and the positions read model."""

    module_id = "trading"

    #: Empty, and checked: `test_module_declarations.py` reads the imports
    #: actually present under `modules/trading/` and fails on both surplus and
    #: shortfall. This context reads no other module's `contracts/` — it is the
    #: *supplier* in every relationship it has (`strategy` and `backtesting`
    #: read it, not the reverse), and what it does depend on is
    #: `support/binance_gateway`'s contracts, which is not a module.
    dependencies: list[str] = []  # noqa: RUF012 — the Engine reads a plain attribute

    def register(self, context: Any) -> None:
        """The published ports, and only those.

        PR 1.3b, plus `IEquityCurve` from PR 1.3c-3. The adapter and handler
        registrations still live in `binance_bot_module.py` — see this
        module's docstring for what unblocked that move and why it is still
        PR 1.4's. These need nothing but `ICommandDispatcher` and two
        singletons this module owns, so the published surface can be bound
        from inside the module while its internals wait.
        """
        bind_published_ports(context.container)

    def boot(self, context: Any) -> None:
        """Nothing to start. `IUserDataStream` is registered but deliberately
        never started by booting: only a successful `EnableTradingCommand`
        calls `.start()` on it, so opening the app opens no user-data socket
        (`EPIC-021H`). That stays true whoever registers it."""

    def shutdown(self, context: Any) -> None:
        """Nothing to close here yet.

        The websocket this context can open is closed by the same handler that
        opened it, and the REST clients hold no pool of their own. When PR 1.3c
        moves the bindings in, this gains the disposal `market_data`'s own
        `shutdown()` performs — and `BUG-122`'s lesson with it: ask the
        container whether a singleton was ever built (`Registration.
        instantiated`) instead of resolving it, or closing becomes the reason
        it gets created.
        """
