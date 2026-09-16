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
deliberately **not** called that. The reason was a collision when this file was
written (PR 1.3b): `order_intent_for()` in `domain/policies/` owned the name for
a different and much smaller thing, the `(side, reduce_only)` pair a
`SignalAction` maps to. PR 2.1a published that pair as
`contracts/order_intent.py`, so the collision is gone and the names are now
distinct on their own merits — an `OrderIntent` is *which side, and may it only
reduce*; an `OrderRequest` is a whole order, with symbol, quantity, type and
price. This one keeps its name for the reason that always justified it: a
published contract does not speak the CQRS vocabulary of the module behind it.
`market_data`'s `contracts/symbol_market_metadata.py` holds a third
`OrderIntent`, in a different module's contracts, and stays.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType

#: Who an order belongs to when the caller does not say: a human at a form.
#:
#: The default is the **unprivileged** one on purpose (`EPIC-025` PR 2.1f). An
#: `owner_id` matching a symbol's lease holder is what gets an order past
#: `ExecuteOrderSafetyGate.SYMBOL_LEASED`, so a caller that forgets to identify
#: itself is refused on a leased symbol rather than waved through — the failure
#: direction that cannot lose money.
MANUAL_OWNER = "manual"


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
    #: Who is asking (`EPIC-025` PR 2.1f). Only the symbol lease reads it: an
    #: order on a symbol `ITradingSession.claim_symbol()` gave to somebody else
    #: is refused, and an order from that somebody else goes through. Defaults
    #: to `MANUAL_OWNER` — see its own note for why the default is the one with
    #: the fewest privileges.
    owner_id: str = MANUAL_OWNER
