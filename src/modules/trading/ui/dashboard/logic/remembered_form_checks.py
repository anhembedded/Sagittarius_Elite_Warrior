"""`EPIC-010D` — whether a value remembered from the last session is worth
applying to the Dev Board's form.

Moved out of `DashboardPresenter` (the god-file ratchet, `EPIC-033D`):
`restore_state()` asks these about each remembered field and applies only
what passes, so a corrupted or hand-edited state file never reaches the form.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame

#: Dates are persisted as a DURATION, never as absolute timestamps (design
#: §9.1, risk R2): an absolute window remembered from a month ago would make
#: the next Load History silently fetch an enormous range. Recomputing
#: `now - N days` on restore preserves today's behaviour exactly.
MAX_LOOKBACK_DAYS = 3650
#: Longest symbol Binance lists is well under this; a generous ceiling that
#: still rejects a corrupted blob is the point, not a precise limit.
_MAX_SYMBOL_LENGTH = 20


def is_plausible_symbol(value: object) -> bool:
    """Whether a remembered symbol is worth applying (`EPIC-010D`).

    @details Shape, not membership. The task file's rule reads "only apply if
    it is still in the symbol options the app knows about", which is right for
    a closed dropdown — but this screen's combo is `setEditable(True)` and
    `_DEFAULT_SYMBOLS` holds a single entry, so membership would silently
    discard any symbol the user legitimately typed and hand them "ETHUSDT"
    back on every launch. That defeats the point of remembering it. The
    Database screen (`EPIC-010E`) has a genuinely closed list and gets the
    membership check there instead.
    """
    return (
        isinstance(value, str)
        and value.strip().isalnum()
        and len(value.strip()) <= _MAX_SYMBOL_LENGTH
    )


def is_known_interval(value: object) -> bool:
    """Whether a remembered interval is still a real `TimeFrame`."""
    if not isinstance(value, str):
        return False
    try:
        TimeFrame(value)
    except ValueError:
        return False
    return True


def is_key_list(value: object) -> bool:
    """A remembered list of script keys (`EPIC-010G`).

    @details Only shape is checked here — whether a key still names a
    registered script is `restore_selection()`'s job, which intersects
    against the rows that actually exist.
    """
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def is_sane_lookback(value: object) -> bool:
    """@details `isinstance(True, int)` is `True` in Python, so booleans are
    excluded explicitly — `{"lookback_days": true}` in a hand-edited file
    would otherwise be applied as one day."""
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 1 <= value <= MAX_LOOKBACK_DAYS
    )
