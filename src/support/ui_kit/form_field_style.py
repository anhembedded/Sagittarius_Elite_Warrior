"""The QSS one text/number input field is painted with.

@details Extracted by `EPIC-022C`. It used to be `_FIELD_STYLE`, a private
constant inside `screens/backtest/backtest_modals/_layout.py`, read both by
that module's own `_field_row()` and by the parameter-field widget next to
it. When that widget moved out to `components/strategy_params/` (so the
Trading screen could use the same "Thông số Chiến lược" form), the constant
had to stop being private to a screen package or the moved widget would
have kept importing backwards into the screen it just left.

@par Why this is not `StyleRole.FIELD`
`kit/style.py` already has a `FIELD` role that paints almost this — same
shape, but reading `stateIdleBg`/`border` where this reads
`bgCardHeader`/`stateNavBorder`. Those are genuinely different tokens with
different values, so switching would move real pixels, not just rename an
import. Converging the two is a real improvement and a deliberate non-goal
here:
`EPIC-022C` moves code without changing a single rendered pixel, and a
"while I was in there" restyle is exactly the kind of change that makes a
refactor's "the old tests still pass untouched" evidence stop meaning
anything. The convergence belongs in its own commit, reviewed as the
visual change it is.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.ui_kit.assets import Palette

FIELD_STYLE = (
    f"background-color: {Palette.BG_CARD_HEADER}; "
    f"border: 1px solid {Palette.STATE_NAV_BORDER}; border-radius: 4px; "
    f"color: {Palette.TEXT_PRIMARY}; padding: 0 6px;"
)
