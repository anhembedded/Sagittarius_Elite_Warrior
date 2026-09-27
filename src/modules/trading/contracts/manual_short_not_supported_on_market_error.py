"""`EPIC-027K` post-review fix (PR #284) — Spot has no leveraged position to
open a short in, but before this fix `manual_order_intent_for()` translated a
Short click into a plain `OrderSide.SELL`/`reduce_only=False` regardless of
market, indistinguishable from a deliberate reduce of a real holding. Once
`TradingVenue.supports_order_submission` covers Spot too, nothing upstream
still refused that translation, so a user holding real Spot inventory who
clicked "Short" (meaning: open a short position) would have that inventory
sold live, live, under an action the UI frames as opening a position that
does not exist on this venue — `domain-truth-rule.md` F3: an unsupported
capability must be refused, not silently reinterpreted as something else.
"""

from __future__ import annotations


class ManualShortNotSupportedOnMarketError(ValueError):
    """@brief Raised by `manual_order_intent_for()` instead of building an
    `OrderIntent` when a Short click targets a market with no short/leveraged
    position capability (`MarketType.SPOT`).

    @details Never translated into a plain Sell of the held asset: the user
    asked to open a short, not to liquidate a holding, and those are
    different, un-mergeable intents — reporting the refusal is the honest
    answer, not guessing which one they meant.
    """
