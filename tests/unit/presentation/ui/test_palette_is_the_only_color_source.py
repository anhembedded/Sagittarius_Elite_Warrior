"""EPIC-005B — locks in `Palette` as the app's real single source of color, now that
`qss/style.qss` (claimed as "the one place still hardcoding hex" but actually dead since
the BOT-030 QML migration — nothing in `src/` loaded it) has been removed.

Without this, the next "add a QtWidgets screen" (EPIC-005D onward) could reintroduce
exactly the duplication this task just closed: a second hardcoded copy of an accent color
living outside `Palette`, discovered only by accident.
"""

import re
from pathlib import Path
from unittest.mock import MagicMock

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.presentation.ui.app_bootstrapper import _apply_theme
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette

REPO_ROOT = Path(__file__).resolve().parents[4]

#: Every literal hex value Palette itself defines — these are the only hex colors any
#: other file in the scanned scope is allowed to contain (see test below).
_PALETTE_HEX_VALUES = frozenset(
    value.lstrip("#").upper()
    for name, value in vars(Palette).items()
    if isinstance(value, str) and re.fullmatch(r"#[0-9A-Fa-f]{6,8}", value)
)

_HEX_LITERAL = re.compile(r"#(?:[0-9A-Fa-f]{8}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b")

#: Scope is `presentation/ui/` only, NOT all of `src/` — this is `Palette`'s own
#: domain (app chrome: window, sidebar, cards, status text). `src/domain/` (indicator
#: scripts, strategies) hardcodes hex for a different reason entirely: those are
#: *chart drawing* colors for indicator overlays, chosen independently of the app's
#: UI theme — a strategy's EMA line color duplicating Palette.ACCENT by coincidence is
#: not the bug this guards against, and scanning `domain/` was tried first and
#: produced exactly that noise (macd/ema/dev indicator scripts, ema_trend_pullback).
_SCAN_ROOT = REPO_ROOT / "src" / "presentation" / "ui"

#: `chart_card/` is its own package with a written reason to duplicate rather than
#: import Palette — see `chart_card/theme.py`'s own docstring: "this package doesn't
#: import the app's global Palette (kept portable/standalone)". A deliberate,
#: documented exception, not the accidental duplication this test hunts for.
_EXEMPT_DIRS = frozenset({"components/chart_card"})

#: This file is the one place allowed to *define* the values palette.py's own dict
#: methods return, and the test file itself quotes hexes in its docstring/asserts.
_EXEMPT_FILES = frozenset(
    {
        "src/presentation/ui/assets/palette.py",
        "tests/unit/presentation/ui/test_palette_is_the_only_color_source.py",
    }
)


def test_no_second_hardcoded_copy_of_a_palette_color_exists_in_presentation_ui():
    """The exact class of bug EPIC-005B found: `_apply_theme`'s old fallback
    `config.get(ConfigKeys.UI_THEME_ACCENT_COLOR, "#F3BA2F")` duplicated
    `Palette.ACCENT`'s value as an independent literal. Any `.py` file under
    `presentation/ui/` (outside the exemptions above) that contains a hex literal
    matching one of Palette's own values is either that same duplication again, or a
    color that should have been added to Palette in the first place."""
    offenders: list[str] = []

    for path in _SCAN_ROOT.rglob("*.py"):
        rel = path.relative_to(REPO_ROOT).as_posix()
        rel_to_ui = path.relative_to(_SCAN_ROOT).as_posix()
        if rel in _EXEMPT_FILES or "__pycache__" in rel:
            continue
        if any(rel_to_ui.startswith(d + "/") for d in _EXEMPT_DIRS):
            continue

        text = path.read_text(encoding="utf-8")
        for match in _HEX_LITERAL.finditer(text):
            hex_value = match.group(0).lstrip("#").upper()
            if len(hex_value) == 3:
                hex_value = "".join(c * 2 for c in hex_value)
            if hex_value in _PALETTE_HEX_VALUES:
                offenders.append(f"{rel}: {match.group(0)}")

    assert not offenders, (
        "Found a hardcoded hex literal outside Palette that duplicates one of "
        "Palette's own values -- import Palette instead of re-typing the hex:\n"
        + "\n".join(offenders)
    )


def test_apply_theme_falls_back_to_palette_accent_not_a_second_literal():
    """Behavioral proof, not just static: with no config override present,
    _apply_theme must ask qdarktheme for exactly Palette.ACCENT."""
    config = MagicMock()
    config.get.side_effect = lambda key, default=None, **kw: default

    app = MagicMock()
    _apply_theme(app, config)

    accent_call = next(
        call
        for call in config.get.call_args_list
        if call.args[0] == ConfigKeys.UI_THEME_ACCENT_COLOR
    )
    assert accent_call.args[1] == Palette.ACCENT
