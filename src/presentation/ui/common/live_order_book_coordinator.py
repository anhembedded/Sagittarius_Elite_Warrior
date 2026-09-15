"""Positions/Open Orders table bookkeeping, shared by every screen that
displays them (`TradingPresenter`, `DashboardPresenter`).

@details `EPIC-021H`/`BUG-086`/`BUG-084` built the four `OrderFeed` handlers
and the two render methods once, for `TradingPresenter`. `EPIC-023A` needed
the identical behaviour on Dev Board and copy-pasted all six methods plus
the two backing dicts — the exact class of defect `health_check_coordinator.
py`'s own docstring (`EPIC-019B`) already names ("both screens independently
... carried near-identical methods"). Pulled out here instead of left
duplicated a second time.

Mirrors `symbol_options_coordinator.py`'s/`health_check_coordinator.py`'s
shape: a plain class (not `QObject`), reporting through injected
`view`/`emit_log` rather than holding a Presenter reference. Unlike
`HealthCheckCoordinator`, this class does **not** own an `OrderFeed`
instance itself — `orderFilled` also drives a chart-marker side effect that
genuinely differs per screen (Trading's single active-symbol chart vs. Dev
Board's multi-symbol `active_charts`), so each Presenter keeps constructing
and owning its own `OrderFeed`, and forwards the four events into this
coordinator's plain methods instead of connecting Qt signals directly here.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import Protocol

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    is_terminal,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.order import Order
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.OpenOrdersTable.open_order_row import (
    OpenOrderRow,
    build_open_order_row,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.PositionsTable.positions_row import (
    PositionRow,
    build_position_row,
)


class OrderBookDisplay(Protocol):
    """What this Coordinator reads from and writes to — narrower than a
    full screen View on purpose, same reasoning `StrategyCardViewModel`
    (`strategy_arming_coordinator.py`) documents for its own Protocol."""

    def set_positions(self, rows: Sequence[PositionRow]) -> None: ...

    def set_open_orders(self, rows: Sequence[OpenOrderRow]) -> None: ...


class LiveOrderBookCoordinator:
    """@brief Keeps one screen's Positions/Open Orders tables in sync with
    `OrderFeed` events the owning Presenter forwards in."""

    def __init__(self, view: OrderBookDisplay, emit_log: Callable[[str], None]) -> None:
        self._view = view
        self._emit_log = emit_log
        self._positions: dict[str, LivePosition] = {}
        self._open_orders: dict[str, Order] = {}

    def replace_all(
        self, positions: Iterable[LivePosition], open_orders: Iterable[Order]
    ) -> None:
        """Full reconciliation — `EnableTradingCommand`/`EmergencyStopCommand`
        are the only callers with a fresh, authoritative snapshot from the
        exchange; every other update is the smaller incremental
        `on_*` methods below."""
        self._positions = {position.symbol: position for position in positions}
        self._open_orders = {order.client_order_id: order for order in open_orders}
        self._render_positions()
        self._render_open_orders()

    def on_order_filled(self, order: Order) -> None:
        if is_terminal(order.status):
            self._open_orders.pop(order.client_order_id, None)
        else:
            self._open_orders[order.client_order_id] = order
        self._render_open_orders()

    def on_position_changed(self, position: LivePosition) -> None:
        self._positions[position.symbol] = position
        self._render_positions()

    def on_position_closed(self, symbol: str) -> None:
        """`BUG-086` — removes a position the exchange reports as flat.
        `dict.pop(..., None)` rather than indexing: this fires for every
        symbol going flat, including one this table never held (no prior
        `on_position_changed` for it this session)."""
        self._positions.pop(symbol, None)
        self._render_positions()

    def on_order_cancelled(self, client_order_id: str) -> None:
        """`EPIC-024B` §0 — removes one order the exchange just confirmed
        cancelled. `dict.pop(..., None)` rather than indexing, same
        reasoning `on_position_closed` above documents: harmless if this
        table never held the order (e.g. it filled between the click and
        the cancel actually landing)."""
        self._open_orders.pop(client_order_id, None)
        self._render_open_orders()

    def on_order_blocked(self, symbol: str, reason: str) -> None:
        """`BUG-084` — the one place a blocked signal-driven order becomes
        visible on the screen itself, not just in a log file nobody is
        watching. Callers append this at `level="info"`: a blocked order is
        a one-time-meaningful event, not an application error."""
        self._emit_log(f"Live order blocked ({symbol}): {reason}")

    def _render_positions(self) -> None:
        self._view.set_positions(
            [build_position_row(position) for position in self._positions.values()]
        )

    def _render_open_orders(self) -> None:
        self._view.set_open_orders(
            [build_open_order_row(order) for order in self._open_orders.values()]
        )
