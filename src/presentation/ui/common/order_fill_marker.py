"""`EPIC-021K` §2.3 — `OrderFilledEvent` -> `MarkerPoint`, the live-fill
counterpart to `screens/backtest/logic/chart_canvas_view.py`'s
`trade_flag_markers()` (BOT-009/BOT-056/BOT-096/BOT-111).

@details Simpler than the backtest version on purpose: a `Trade` knows its
own entry/exit and side unambiguously (it is the *result* of a closed
round-trip), but one live `OrderFilledEvent` only ever reports one fill —
this app cannot tell from the event alone whether it opened or added to a
position (unless `reduce_only` says it closed one). So this marker is
side-aware (`OrderSide.BUY`/`SELL`, same green-up/red-down convention as
every other chart marker in this app) and reduce-only-aware (labelled
"(Đóng)" — a closing fill is a materially different kind of event from an
opening one, worth telling apart at a glance), but does not attempt the
richer LONG/SHORT/TP vocabulary `trade_flag_markers()` has from a
`Trade`'s complete picture.
"""

from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.domain.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.marker_layer import (
    MarkerPoint,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)

_BUY_LABEL = "MUA"
_SELL_LABEL = "BÁN"
_CLOSE_SUFFIX = " (Đóng)"


def order_filled_marker(event: OrderFilledEvent) -> MarkerPoint:
    """@brief One `OrderFilledEvent` as one chart marker.

    @details X is `order.order_time` — the exchange's own fill time
    (`EPIC-021I`'s `Order.order_time`, populated by
    `parse_order_trade_update()` from the stream's `"T"` field for every
    real fill) — falling back to "now" only for the theoretical case that
    field is absent, the same fallback `map_futures_position_payload_to_live_position`
    already uses for `LivePosition.updated_at`.
    """
    order = event.order
    is_buy = order.side is OrderSide.BUY
    label = _BUY_LABEL if is_buy else _SELL_LABEL
    if order.reduce_only:
        label += _CLOSE_SUFFIX
    color = BULL_COLOR if is_buy else BEAR_COLOR
    direction = "up" if is_buy else "down"
    fill_time = order.order_time or datetime.now(UTC)
    return (fill_time.timestamp(), float(event.fill_price), label, color, direction)
