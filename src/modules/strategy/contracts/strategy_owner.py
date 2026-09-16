"""Who `strategy` is, to `trading`'s symbol lease (`EPIC-025` PR 2.1f).

@details `ITradingSession.claim_symbol(symbol, owner_id)` takes an opaque owner
string and `ExecuteOrderCommandHandler` compares it against the `owner_id` on
an `OrderRequest`. `trading` deliberately does not know what any particular
string means — that is what keeps the lease a mechanism rather than a list of
the contexts that exist, and it is why `modules/trading` still imports nothing
from here (`EPIC-025C` §2's first done-when).

Published rather than kept private because three files in two sub-packages use
it — `arm_strategy` claims with it, `disarm_strategy` releases with it, and
`LiveTradingCoordinator` stamps it on every `OrderRequest` so the strategy's own
order is not refused by its own lease — and because a reader looking at a lease
holder of `"strategy"` in a log line should be able to find the definition.

A plain `str`, not an enum: the set of owners is open. A second strategy
instance (ADR §7 item 15) would be a *different* owner with the same kind of
value, and an enum would make that a change to this file rather than a value
the caller passes.
"""

from __future__ import annotations

#: The owner id every arming of a live strategy claims its symbol under.
STRATEGY_OWNER = "strategy"
