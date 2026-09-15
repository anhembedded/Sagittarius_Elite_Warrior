"""`OrderRequest` — what a caller asks `IOrderSubmission` for.

@par Why a published DTO rather than the command the handler takes
`IMarketDataSync`'s template (PR 0.5): the module publishes a frozen request
type and translates it into its own `PreviewOrderQuery` /
`ExecuteOrderCommand` internally. The commands stay internal on purpose —
publishing them is exactly the transitional dispatch surface `EPIC-025` is
retiring, where a consumer builds another context's command object and hands
it to the Engine's dispatcher.

The six fields are `PreviewOrderQuery`'s, unchanged: measured, every caller
sets all six or takes the `reduce_only` default, so there is nothing to trim
(HLD §2.4). What changes is the name — a published contract does not speak the
CQRS vocabulary of the module behind it.

@par Not `OrderIntent`
HLD §3.4 lists `OrderIntent` among trading's published DTOs, and this type is
deliberately **not** called that: `order_intent_for()` in
`domain/policies/signal_action_to_order_intent.py` already owns that name for
a different and much smaller thing — the `(side, reduce_only)` pair a
`SignalAction` maps to. Two types called `OrderIntent` in one module, one of
them published, is how a reader picks the wrong one. `market_data`'s
`contracts/symbol_market_metadata.py` holds a third. HLD §3.4 is corrected to
this name rather than the collision being shipped.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType


@dataclass(frozen=True, slots=True)
class OrderRequest:
    """One order a caller wants shaped, checked, and possibly sent."""

    symbol: str
    side: OrderSide
    order_type: OrderType
    #: Before rounding. The module rounds it to the symbol's `step_size` and
    #: reports both numbers in `OrderPreview`, so a caller never has to know
    #: the exchange's filters.
    quantity: Decimal
    #: The price the caller's decision was made against — used for the
    #: notional estimate, and as the limit price for a LIMIT order.
    reference_price: Decimal
    #: Closing an existing position rather than opening one. The exchange
    #: refuses a `reduce_only` order that would flip the side.
    reduce_only: bool = False
