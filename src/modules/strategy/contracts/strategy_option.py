"""`StrategyOption` — one entry in a strategy picker, key plus label.

`IStrategyCatalog.options()`'s return type. The label is
`humanize_strategy_key()`'s output, computed once inside `strategy`: a
consumer needs the display string, not the function that makes one, the
same reason `strategy_display.py` centralised it in the first place
(`BOT-125` review) — a second copy across the module boundary would be the
identical drift, one hop further out.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StrategyOption:
    """One strategy a catalog offers, as a picker would show it."""

    key: str
    label: str
