"""`EPIC-021F`'s safety net, published because two callers already catch it.

The exception lived beside the payload mapper that raises it, which is where
it was written and where it reads most naturally. `EPIC-025` PR 1.3c-2 moves
it here for one measured reason: `order-dry-run` and `trade-once` both catch
it by name, and a legacy file importing a module's **adapter** is the boundary
rule's one prohibition. A consumer may name a module's `contracts/` and
nothing else.

It is published as an exception rather than folded into
`OrderRejectionReason`, which is the vocabulary of *exchange* refusals. This
is the opposite: the order never reached the exchange, because this app built
one that does not satisfy the symbol's own filters. A caller that shows the
user "the venue said no" for it would be reporting a defect in this
application as a decision by Binance.
"""

from __future__ import annotations


class InvalidOrderForSubmissionError(ValueError):
    """@brief Raised instead of silently rounding when `Order` does not
    already align to the symbol's `stepSize`/`tickSize`, or is missing a
    field its `order_type` requires.

    @details Never fixed up where it is raised: the caller is expected to
    have built the order through `OrderQuantityRoundingPolicy` in the first
    place, so rounding here would hide the upstream mistake and let domain
    and exchange disagree about the quantity actually sent. This is the
    safety net for the day something upstream forgets to round.
    """
