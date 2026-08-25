"""
Guards the Card layering rule from .agents/rules/ui-architecture.md (rule 1):
every widget that inherits a Card base must live under
src/presentation/ui/components/ and be named `*_card.py`.

Pure static analysis (ast) — no PySide6 import, no qapp fixture needed.

## This guard was one rename away from silently doing nothing

It matched the literal base-class name `"BaseCard"`. `EPIC-007E` deleted
`BaseCard` and moved `ChartCard` onto the engine's `Card`, at which point
`_defines_card_class` would have returned `False` for every file in the
tree, `offenders` and `badly_named` would both have been empty, and both
tests would have passed — while guarding nothing at all.

It would not have failed. It would have gone quiet. That is the worse
outcome, and it is why `test_the_guard_still_finds_something` exists below:
a guard whose subject has disappeared must say so.

`_CARD_BASES` is a set now for the same reason. When a card base is renamed
or a second one appears, the fix is a name in that set, and the
completeness test is what forces someone to notice they need to make it.
"""

import ast
from pathlib import Path

_UI_ROOT = Path(__file__).resolve().parents[4] / "src" / "presentation" / "ui"
_COMPONENTS_DIR = _UI_ROOT / "components"

#: Every base class that makes its subclass "a Card" for the purposes of the
#: layering rule. `Card` is the engine's (`pyside_mvc.widgets.surface.Card`);
#: `BaseCard` was this app's own duplicate of it, deleted in `EPIC-007E` and
#: kept here only so an old branch reintroducing it is still caught.
_CARD_BASES = frozenset({"Card", "BaseCard"})


def _iter_python_files(root: Path):
    for path in root.rglob("*.py"):
        if "__pycache__" not in path.parts:
            yield path


def _card_classes(source: str) -> list[str]:
    """Names of classes in `source` whose bases include a Card base."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            base_name = (
                base.id if isinstance(base, ast.Name) else getattr(base, "attr", None)
            )
            if base_name in _CARD_BASES:
                found.append(node.name)
                break
    return found


def _defines_card_class(source: str) -> bool:
    return bool(_card_classes(source))


def test_card_classes_live_under_components_dir():
    """
    A Card (subclasses BaseCard) must be defined inside components/, never
    alongside a screen. This guards against the exact mistake made once
    already: SyncControlCard/DatabaseStatusCard were briefly placed under
    screens/data_management/ before being moved here.
    """
    offenders = [
        path
        for path in _iter_python_files(_UI_ROOT)
        if _COMPONENTS_DIR not in path.parents
        and _defines_card_class(path.read_text(encoding="utf-8"))
    ]

    assert offenders == [], (
        f"Card classes (subclassing BaseCard) found outside {_COMPONENTS_DIR}: "
        f"{[str(p) for p in offenders]}"
    )


def test_card_files_are_named_with_card_suffix():
    """
    Every file under components/ that defines a Card class must be named
    `*_card.py` (matching base_card.py, control_card.py, chart_card.py, ...)
    so the filename itself signals "this is a Card". Non-Card helpers that
    happen to live in components/ (e.g. sidebar.py, or chart_card/'s internal
    renderers) are exempt — the rule only binds actual Card classes.
    """
    badly_named = [
        path
        for path in _iter_python_files(_COMPONENTS_DIR)
        if _defines_card_class(path.read_text(encoding="utf-8"))
        and not path.stem.endswith("_card")
    ]

    assert badly_named == [], (
        f"Card files must be named '*_card.py': {[str(p) for p in badly_named]}"
    )


def test_the_guard_still_finds_something():
    """The two tests above are satisfied by an empty result set, so they pass
    whether the rule holds or the guard has lost its subject. This one tells
    those apart.

    If it fails, do not delete it — find out what the Card base is called now
    and add that name to `_CARD_BASES`. The layering rule is unenforced until
    you do."""
    cards = {
        path.name: names
        for path in _iter_python_files(_UI_ROOT)
        if (names := _card_classes(path.read_text(encoding="utf-8")))
    }

    assert cards, (
        "no class in the UI tree inherits any name in _CARD_BASES "
        f"({sorted(_CARD_BASES)}). Either every Card is gone, or a base was "
        "renamed and this guard is now inspecting nothing."
    )
