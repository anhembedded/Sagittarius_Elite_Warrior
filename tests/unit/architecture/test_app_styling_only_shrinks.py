"""
The app paints none of its own look (ADR D20–D22, HLD §11.4): a ban since
`EPIC-033M`.

**The target, reached.** No stylesheet, no palette, no third-party theme:
standard controls render in the platform's theme, and colour appears only
where it carries meaning, from the one meaning table. `EPIC-025` PR 0.2
deleted the global sheet (`test_no_global_stylesheet.py` keeps it deleted);
the phases since rebuilt every screen as plain QtWidgets panels, and
`EPIC-033M` deleted the kit, `Palette`, the theme bootstrap and the last QML.

**What this held.** The census was a ratchet from 2026-08 (52 `apply_role()`
calls, 151 `setStyleSheet()` calls, 33 files importing `Palette`, 229
`Theme.*` bindings in 35 `.qml` files), each number only allowed to fall.
Every number is zero now, so the baseline file is gone and each field is
held at zero: one `setStyleSheet()` call, one `Palette` import, one `.qml`
file fails the build.

Retire when: never while the app follows ADR D21; this is the ban.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.tools.measure_app_styling import measure

_MEASURED = measure()

#: Every field is a count of app-level styling, held at zero. Named here rather
#: than derived, so adding a field to the census without deciding fails a test.
_HELD_AT_ZERO = (
    "apply_role_calls",
    "apply_role_files",
    "set_style_sheet_calls",
    "set_style_sheet_files",
    "palette_files",
    "qml_theme_refs",
    "qml_files",
)


def test_every_census_field_is_held() -> None:
    assert set(_HELD_AT_ZERO) == set(vars(_MEASURED)), (
        "the census grew or lost a field; decide whether it is held at zero"
    )


@pytest.mark.parametrize("field", _HELD_AT_ZERO)
def test_the_app_styles_nothing_itself(field: str) -> None:
    measured = getattr(_MEASURED, field)
    assert measured == 0, (
        f"{field}: {measured}. New code is styling itself. The app applies no\n"
        "stylesheet or palette of its own (ADR D21): let the platform theme\n"
        "render the widget, and take colour that carries meaning from\n"
        "src/support/ui_kit/meaning_colours.py."
    )
