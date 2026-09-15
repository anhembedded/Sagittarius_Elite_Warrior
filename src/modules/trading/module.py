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

@par Why `register()` binds only three things, unlike `market_data`'s
PR 1.3a moved this context's code under `modules/trading/`; PR 1.3b published
its three ports and bound them here. What is still **not** here is every
adapter and handler registration, and the reason is a single shared object
rather than laziness.

`ExchangeSessionFactory` is built **once** and that one instance answers both
this context's `ITradingSessionFactory` and `market_data`'s
`IExchangeSessionFactory` (`EPIC-024A`: the handlers depend on the port so they
auto-wire to the shared instance rather than each getting a throwaway one). The
trading registrations are written against that instance — `FuturesAccountReader`,
`FuturesMetadataProvider`, `FuturesUserDataStream` and `FuturesTradingClient` all
take it. Moving them here means this module either resolves that instance from
the container or builds its own, and building its own is **two factories where
there was one**: a behaviour change, which ADR D12 keeps out of a move. The
allowlist has scheduled that split since PR 0.4a ("`EPIC-025B` splits it, one
factory per context") and it is PR 1.3b's, together with the three ports.

Until then `binance_bot_module.py` registers them, which costs no boundary
violation: the boundary scan skips that file by name
(`tests/unit/architecture/boundaries/scan.py`) because it *is* the composition
root the strangler is replacing. `composition/port_bindings.py` explains which
three could move early and why.

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
        """The three published ports, and only those.

        PR 1.3b. The adapter and handler registrations still live in
        `binance_bot_module.py` for the shared-`ExchangeSessionFactory` reason
        in this module's docstring; these three need nothing but
        `ICommandDispatcher` and the `TradingSessionState` singleton, so the
        published surface can be bound from inside the module while its
        internals wait for PR 1.3c.
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
