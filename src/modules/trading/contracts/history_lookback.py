"""`EPIC-028E` — the one check behind `IAccountHistoryReader`'s lookback clause.

@details Both real readers and the verified fake call it, so a consumer test
against the fake is refused a `since` exactly where the exchange-backed
readers refuse it (the PR #297 re-review, finding 1).
"""

from __future__ import annotations

from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    MAX_HISTORY_LOOKBACK,
)


def require_within_lookback(since: datetime, now: datetime) -> None:
    """@throws ValueError `since` is further back from `now` than
    `MAX_HISTORY_LOOKBACK`."""
    if now - since > MAX_HISTORY_LOOKBACK:
        raise ValueError(
            f"since {since.isoformat()} is more than {MAX_HISTORY_LOOKBACK.days} "
            "days back; read a shorter span"
        )
