"""Positions/Open Orders table bookkeeping, shared by every screen that
displays them (`DashboardPresenter`, the desks' `AccountTabsPresenter`).

@details `EPIC-021H`/`BUG-086`/`BUG-084` built the four `OrderFeed` handlers
and the two render methods once, for the Trading screen (retired in
`EPIC-028M`). `EPIC-023A` needed
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

from collections.abc import Callable, Iterable, Mapping, Sequence
from decimal import Decimal
from typing import Protocol

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    is_terminal,
    is_valid_transition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.holding_row import (
    HoldingRow,
    build_holding_row,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.open_order_row import (
    OpenOrderRow,
    build_open_order_row,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    PositionRow,
    build_position_row,
)


class OrderBookDisplay(Protocol):
    """What this Coordinator reads from and writes to — narrower than a
    full screen View on purpose, same reasoning `StrategyCardViewModel`
    (`strategy_arming_coordinator.py`) documents for its own Protocol."""

    def set_positions(self, rows: Sequence[PositionRow]) -> None: ...

    def set_open_orders(self, rows: Sequence[OpenOrderRow]) -> None: ...

    def set_holdings(self, rows: Sequence[HoldingRow]) -> None: ...


#: `EPIC-027N` AC5/`EPIC-027O` — Phase 1 Spot trades USDT-quoted pairs only;
#: the same literal `arm_strategy/handler.py`/`emergency_stop/handler.py`/
#: `live_trading_coordinator.py` already carry, not a new one.
_QUOTE_ASSET = "USDT"


class LiveOrderBookCoordinator:
    """@brief Keeps one screen's Positions/Open Orders/Holdings tables in
    sync with `OrderFeed` events the owning Presenter forwards in."""

    def __init__(self, view: OrderBookDisplay, emit_log: Callable[[str], None]) -> None:
        self._view = view
        self._emit_log = emit_log
        self._positions: dict[str, LivePosition] = {}
        self._open_orders: dict[str, Order] = {}
        #: Orders seen ended (terminal or cancelled) this session. Client
        #: order ids are never reused, so one seen ended stays ended.
        self._ended: set[str] = set()
        self._holdings: dict[str, SpotHolding] = {}

    def replace_all(
        self, positions: Iterable[LivePosition], open_orders: Iterable[Order]
    ) -> None:
        """Full reconciliation — `EnableTradingCommand`/`EmergencyStopCommand`
        and a desk opening (`AccountTabsPresenter`'s read of the account,
        `EPIC-028J`) are the callers with a fresh, authoritative snapshot
        from the exchange; every other update is the smaller incremental
        `on_*` methods below."""
        self._positions = {position.symbol: position for position in positions}
        self._open_orders = {order.client_order_id: order for order in open_orders}
        self._render_positions()
        self._render_open_orders()

    def on_order_filled(self, order: Order) -> None:
        """One order's latest known state, from a fill or from the desk's own
        acceptance (`EPIC-028K`).

        @details The two arrive from different threads, in either order: the
        venue's stream reports a fill, the REST answer reports the order as
        accepted (`NEW`, which both trading adapters return unchanged). A
        status is applied only when it moves forward
        (`order_status.is_valid_transition`), and an order seen ended is
        never listed again, so a late `NEW` neither re-lists a filled order
        nor hides a partial fill (the PR 308 review)."""
        order_id = order.client_order_id
        if order_id in self._ended:
            return
        known = self._open_orders.get(order_id)
        if (
            known is not None
            and known.status is not order.status
            and not is_valid_transition(known.status, order.status)
        ):
            return
        if is_terminal(order.status):
            self._ended.add(order_id)
            self._open_orders.pop(order_id, None)
        else:
            self._open_orders[order_id] = order
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
        self._ended.add(client_order_id)
        self._open_orders.pop(client_order_id, None)
        self._render_open_orders()

    def on_order_blocked(self, symbol: str, reason: str) -> None:
        """`BUG-084` — the one place a blocked signal-driven order becomes
        visible on the screen itself, not just in a log file nobody is
        watching. Callers append this at `level="info"`: a blocked order is
        a one-time-meaningful event, not an application error."""
        self._emit_log(f"Live order blocked ({symbol}): {reason}")

    def replace_holdings(
        self, holdings: Iterable[SpotHolding], prices: Mapping[str, Decimal]
    ) -> None:
        """`EPIC-027O` — whole-set reconciliation, the only kind Holdings
        ever gets: every `HoldingsChangedEvent` already carries the complete
        account snapshot (that event's own docstring explains why there is
        no incremental `on_holding_*` pair to mirror `on_position_changed`/
        `on_position_closed`). `prices` is asset → last-known USDT price,
        whatever the caller currently has (`build_holding_row` renders a
        missing one as "—" rather than guessing)."""
        self._holdings = {holding.asset: holding for holding in holdings}
        self._render_holdings(prices)

    def has_holding(self, symbol: str) -> bool:
        """Whether the account holds a non-dust amount of `symbol`'s base
        asset — what the manual order card's SELL button reads before
        letting the user submit. USDT-quoted only (ADR D9): strips the same
        fixed quote suffix `LiveTradingCoordinator._sellable_spot_quantity`
        does."""
        asset = symbol.removesuffix(_QUOTE_ASSET)
        holding = self._holdings.get(asset)
        return holding is not None and not holding.is_dust

    def _render_positions(self) -> None:
        self._view.set_positions(
            [build_position_row(position) for position in self._positions.values()]
        )

    def _render_open_orders(self) -> None:
        self._view.set_open_orders(
            [build_open_order_row(order) for order in self._open_orders.values()]
        )

    def _render_holdings(self, prices: Mapping[str, Decimal]) -> None:
        self._view.set_holdings(
            [build_holding_row(holding, prices) for holding in self._holdings.values()]
        )
