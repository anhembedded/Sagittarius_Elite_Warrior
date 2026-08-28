"""`EPIC-015` §3.3 — no colour literal may appear in a `.qml` file.

Mirrors `kit/guards.py`, which already forbids hex literals outside
`style.py` on the widget side. The user's call was *"chưa cần style sớm"* —
no design work, no kit — and this guard is what keeps that from decaying into
each widget quietly growing its own private palette, which is exactly what
`EPIC-005` left behind (8 widgets, 8 hand-written `setStyleSheet` calls) and
what `EPIC-006B` was made a prerequisite to prevent.
"""

from __future__ import annotations

import re
from pathlib import Path

_QML_ROOT = Path(__file__).resolve().parents[5] / "src" / "presentation" / "ui" / "qml"

#: `#fff`, `#RRGGBB`, `#AARRGGBB` — the forms Qt accepts in a QML colour.
_HEX = re.compile(r'"#[0-9a-fA-F]{3,8}"')

#: Named colours Qt understands. `"transparent"` is a layout decision rather
#: than a palette one — it means "let whatever is behind show through" — so
#: it is allowed; every other name is a colour choice and must be a token.
_ALLOWED_NAMES = {'"transparent"'}
_NAMED = re.compile(r'color:\s*("(?!#)[a-zA-Z]+")')


def _qml_files() -> list[Path]:
    return sorted(_QML_ROOT.rglob("*.qml"))


def test_there_are_qml_files_to_check():
    """Guards that pass because they found nothing are how this rots."""
    assert _qml_files(), f"no .qml under {_QML_ROOT}"


def test_no_hex_colour_literal_in_any_qml_file():
    offenders = [
        f"{path.relative_to(_QML_ROOT)}: {match}"
        for path in _qml_files()
        for match in _HEX.findall(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        "Colour literals in .qml — use a `Theme.*` token instead "
        f"(EPIC-015 §3.3): {offenders}"
    )


def test_no_named_colour_except_transparent():
    offenders = [
        f"{path.relative_to(_QML_ROOT)}: {match}"
        for path in _qml_files()
        for match in _NAMED.findall(path.read_text(encoding="utf-8"))
        if match not in _ALLOWED_NAMES
    ]
    assert not offenders, (
        f"Named colours in .qml — use a `Theme.*` token instead: {offenders}"
    )
