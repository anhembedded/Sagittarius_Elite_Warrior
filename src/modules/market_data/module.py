"""`market_data` as one Engine extension — the first real module (HLD §3.2).

This is the only file under `modules/market_data/` that `shell/` may import
(`is_module_entry_point` in the boundary guard), and the only place the module's
internals are named from outside its own packages. `shell/modules.py` lists the
class; `shell/module_registration.py` instantiates it, spies on its `register()`
and hands it to `app.use()`.

**The context's one question:** *what has the market done, and what of it do we
have stored?* Fetching candles from Binance, storing them per symbol and
timeframe, reporting gaps and repairing them, opening the live kline stream, and
knowing which symbols exist. Anything that decides what to *do* with a price —
a strategy, an order, a backtest run — belongs to another context and reaches
this one through `contracts/`.

**Why this file is almost empty.** The four binding tables live in
`composition/`, one file each, because they change for different reasons
(`architecture-rule.md` §5 rule 5): the adapters when storage or the exchange
changes, the commands and queries when this module gains a use case, and
`port_bindings.py` when the module's **published** API changes — the only one
of the four whose audience is another bounded context. What is left here is the
module's *identity* — the id, the declared dependencies, and which hooks it
uses — which is exactly what a reader opens this file to find.

**Hooks not implemented, and why:**

- `contribute()` — Data Management is still a legacy screen carried by
  `shell/legacy_screen_adapter.py`. PR 0.4b rebuilt it on QtWidgets (its last
  `.qml` is gone) but left it in the legacy tree: a module's `ui/` may import
  `support/ui_kit` and `support/charting` whole, and neither exists before
  Phase 4, so moving the screen now would need 35 imports pointing from this
  module back at `presentation.ui.*`. `EPIC-025A` §1.8 measures it;
  `EPIC-025E` step 6 carries the move.
- `subscribe()` — the market-tick handler still lives in the legacy tree
  (`application/event_handlers/market_data/`) and moves in Phase 1.

Both are defaults inherited from `BoundedContextModule`, so the absence is a
statement, not an omission.
"""

from __future__ import annotations

import logging
from typing import Any

from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.live_stream_adapter import (
    LiveStreamEngineAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.database_manager import (
    DatabaseManager,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.composition.adapter_bindings import (
    bind_adapters,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.composition.command_bindings import (
    bind_commands,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.composition.port_bindings import (
    bind_published_ports,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.composition.query_bindings import (
    bind_queries,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    IExchangeClient,
)

logger = logging.getLogger("App.MarketDataModule")


class MarketDataModule(BoundedContextModule):
    """Market history, the symbol catalog and the live kline stream."""

    module_id = "market_data"

    #: Empty, and checked: `test_module_declarations.py` reads the imports
    #: actually present under `modules/market_data/` and fails on both surplus
    #: and shortfall. This context depends on `core/` (the Published Language)
    #: and on `support/binance_gateway`'s contracts — neither is a module, so
    #: neither appears here. It is the *first* context precisely because it
    #: needs no other one.
    dependencies: list[str] = []  # noqa: RUF012 — the Engine reads a plain attribute

    def register(self, context: Any) -> None:
        container = context.container
        bind_adapters(container)
        bind_commands(container)
        bind_queries(container)
        bind_published_ports(container)

    def boot(self, context: Any) -> None:
        """Hand the live-stream adapter to the Engine's lifecycle.

        `LiveStreamEngineAdapter` is a hosted service, not a thread this module
        starts itself: registering it here is what gives it the `EngineContext`
        and gets it stopped on shutdown, while the pure `ILiveStreamService`
        behind it stays free of any Engine type. Registering is not opening —
        the websocket connects only when `StartLiveStreamCommand` asks, so
        booting the app costs no request weight for a screen nobody opened.
        """
        context.hosted_services.register(
            context.container.resolve(LiveStreamEngineAdapter)
        )

    def shutdown(self, context: Any) -> None:
        """Close what holds an OS resource: the SQLite engines and the client.

        `dispose_all()` is not optional bookkeeping — an undisposed SQLAlchemy
        engine keeps its connection pool open, which is what
        `ResourceWarning`s in the gate's log come from, and the gate greps for
        exactly that string.

        The exchange client is closed inside `try`/`except` because a shutdown
        path that raises turns a clean exit into a stack trace the user cannot
        act on, and by then there is nothing left to salvage anyway — so the
        failure is logged at debug and swallowed.

        Known wart, carried over unchanged from `binance_bot_module.py` so this
        move stays a move: the `resolve()` is unconditional, and
        `IExchangeClient` is bound lazily, so a session that never asked for
        market data **constructs** a client here — a network call (`BUG-045`) —
        purely in order to close it. Fixing it needs a way to ask the container
        whether a singleton was ever instantiated, which it does not currently
        offer; `EPIC-025A` §1.5 records it.
        """
        context.container.resolve(DatabaseManager).dispose_all()
        try:
            exchange_client = context.container.resolve(IExchangeClient)
            if hasattr(exchange_client, "close"):
                exchange_client.close()
        except Exception as exc:  # noqa: BLE001 — see the docstring
            logger.debug("Exchange client shutdown error: %s", exc)
