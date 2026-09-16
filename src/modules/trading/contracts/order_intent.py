"""`OrderIntent` — the `(side, reduce_only)` pair an order needs, and nothing else.

## Why this is two fields and not four

Binance Futures One-way mode has no "SHORT" order side. `OrderSide.SELL` both
**closes a LONG** and **opens a SHORT**, and the only thing that tells them
apart is `reduce_only`. So neither an order side nor a position side alone can
express what a caller decided — the pair can, and every path that decides "buy
or sell, opening or closing" produces exactly this pair:

  · a strategy's `SignalAction`, through `order_intent_for()`;
  · a human's Long/Short click plus the account's real position, through
    `manual_order_intent_for()`.

Get the flag backwards and a SHORT signal sends an order the exchange reads as
*close my long*: on a flat or long account it does the wrong thing outright, on
a short account it closes the position the signal meant to open. That is why the
two mappings above are tables rather than `if` statements, and why this type is
a frozen dataclass rather than a tuple.

## Why `contracts/`, and why it is called `OrderIntent`

It lived in `domain/policies/signal_action_to_order_intent.py`, beside the
strategy mapping that produces one — which put a type this module **publishes**
inside a policy file whose other half belongs to another bounded context, and
cost `OrderRequest` its name: HLD §3.4 lists `OrderIntent` among trading's
published DTOs, and `order_request.py`'s docstring records renaming itself to
avoid a collision with the `OrderIntent` in `domain/policies/`.

Both consumers of an intent are already outside this module — `trade_once_cmd`
and `LiveTradingCoordinator` read the pair `order_intent_for()` returns, and the
Dev Board reads the one `manual_order_intent_for()` returns — so by HLD §2.4's
own admission rule the type crosses the boundary and belongs here. With the
strategy mapping leaving for `modules/strategy` in Phase 2, `OrderIntent` is the
only type of that name in this module, and `OrderRequest` (a whole order: symbol,
quantity, type, price) keeps its name for the reason that actually justifies it —
a published contract does not speak the CQRS vocabulary of the module behind it.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide


@dataclass(frozen=True)
class OrderIntent:
    """What to send: which side, and whether it may only reduce a position."""

    side: OrderSide
    reduce_only: bool
