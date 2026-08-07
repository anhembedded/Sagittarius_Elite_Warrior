"""
Guards the Card layering rule from .agents/rules/ui-architecture.md (rule 1):
every widget that inherits from BaseCard must live under
src/presentation/ui/components/ and be named `*_card.py`.

Pure static analysis (ast) — no PySide6 import, no qapp fixture needed.
"""

import ast
from pathlib import Path

_UI_ROOT = Path(__file__).resolve().parents[4] / "src" / "presentation" / "ui"
_COMPONENTS_DIR = _UI_ROOT / "components"


def _iter_python_files(root: Path):
    for path in root.rglob("*.py"):
        if "__pycache__" not in path.parts:
            yield path


def _defines_card_class(source: str) -> bool:
    """True if `source` defines a class whose bases include BaseCard."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            base_name = (
                base.id if isinstance(base, ast.Name) else getattr(base, "attr", None)
            )
            if base_name == "BaseCard":
                return True
    return False


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
