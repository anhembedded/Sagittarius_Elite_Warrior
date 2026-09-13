"""
The app paints less of its own look after every phase, never more
(ADR D20–D22, HLD §11.4).

**The target.** No stylesheet, no palette, no third-party theme: standard
controls render in the platform's theme, and colour appears only where it
carries meaning, per widget. `EPIC-025` PR 0.2 reached the first half of that
by deleting the one global sheet (`qdarktheme`) — `test_no_global_stylesheet.py`
keeps it deleted.

**Why the rest is a ratchet and not a deletion.** What remains is per-widget
styling inside screens that have not been rebuilt yet: 52 `apply_role()` calls
through `kit/style.py`, 151 direct `setStyleSheet()` calls, 33 files importing
`Palette`, and 229 `Theme.*` bindings inside the 35 surviving `.qml` files. The
QML half cannot simply go: the Engine's `create_quick_widget()` raises without
`configure_app_qml()` (`BOT-132`), so the palette must keep feeding QML until
the last `.qml` is gone in Phase 4. Deleting `kit/style.py` in Phase 0 would
mean editing some sixty files and restyling every screen that Phases 1–4 are
going to rebuild anyway — spending Phase 4's work in Phase 0 and breaking the
Strangler Fig rule that the application keeps running at every step
(HLD §6.3). So each number below is recorded and may only fall.

**How it fails.** A number above its baseline fails: new code styled itself.
A number below its baseline fails too, with the instruction to lower the
baseline in the same commit — a ratchet that is never tightened stops being
one. Every number reaches zero in Phase 4, when `kit/` and `qml/` are deleted
together with `Palette` and this guard.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.tools.measure_app_styling import StylingCensus, measure

_BASELINE_FILE = Path(__file__).with_name("baseline_app_styling.json")
_MEASURED = measure()
_BASELINE = StylingCensus(**json.loads(_BASELINE_FILE.read_text(encoding="utf-8")))

#: Every field is a count of app-level styling, so every field ratchets the
#: same way. Named here rather than derived, so adding a field to the census
#: without deciding its direction fails this test.
_RATCHETED_FIELDS = (
    "apply_role_calls",
    "apply_role_files",
    "set_style_sheet_calls",
    "set_style_sheet_files",
    "palette_files",
    "qml_theme_refs",
    "qml_files",
)


def test_every_census_field_is_ratcheted() -> None:
    assert set(_RATCHETED_FIELDS) == set(vars(_BASELINE)), (
        "the census grew or lost a field; decide its direction and list it above"
    )


@pytest.mark.parametrize("field", _RATCHETED_FIELDS)
def test_app_level_styling_does_not_grow(field: str) -> None:
    measured = getattr(_MEASURED, field)
    baseline = getattr(_BASELINE, field)
    assert measured <= baseline, (
        f"{field}: {baseline} → {measured}. New code is styling itself. The app\n"
        "applies no stylesheet or palette of its own (ADR D21): let the platform\n"
        "theme render the widget, and use colour only where it carries meaning."
    )


@pytest.mark.parametrize("field", _RATCHETED_FIELDS)
def test_the_baseline_was_lowered_when_styling_was_removed(field: str) -> None:
    measured = getattr(_MEASURED, field)
    baseline = getattr(_BASELINE, field)
    assert measured >= baseline, (
        f"{field}: {baseline} → {measured}. Styling was removed — lower the number\n"
        f"in {_BASELINE_FILE.name} in the same commit, or the ratchet stops holding\n"
        "the ground you just gained."
    )
