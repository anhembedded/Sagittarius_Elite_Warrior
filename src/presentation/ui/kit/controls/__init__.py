"""
@brief Token-styled leaf controls — each a direct, single-inheritance
subclass of its own distinct Qt base (`QPushButton`/`QCheckBox`/
`QLineEdit`/`QDateTimeEdit`/`QLabel`/`QProgressBar`).

@details
No shared base across all of them: there is no real "Control" abstraction
they have in common beyond "calls `apply_role()` once", and inventing one
would either force a second QObject lineage onto a class that already has
one (forbidden, see `widgets.style`) or add a non-Qt mixin for no behaviour
composition does not already give for free.

`StyledLabel` is the one exception, and only because it arrived with two
real subclasses at once (`SectionLabel`, `Badge`) that share a genuine
behaviour, not merely a base — see its own docstring.

Was a single `controls.py` until EPIC-007C; split one-file-per-class when
this package grew past four members, per EPIC-007 §3.4.
"""

from __future__ import annotations

from .badge import Badge
from .date_time_field import DateTimeField
from .section_label import SectionLabel
from .styled_button import StyledButton
from .styled_check_box import StyledCheckBox
from .styled_field import StyledField
from .styled_label import StyledLabel
from .styled_progress_bar import StyledProgressBar

__all__ = [
    "Badge",
    "DateTimeField",
    "SectionLabel",
    "StyledButton",
    "StyledCheckBox",
    "StyledField",
    "StyledLabel",
    "StyledProgressBar",
]
