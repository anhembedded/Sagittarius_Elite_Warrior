"""
Guards the Presenter/View naming and placement convention every MVP screen
follows (e.g. DashboardPresenter/DashboardView, DataManagementPresenter/
DataManagementView): both live under presentation/ui/screens/<screen_name>/,
in files named `*_presenter.py` / `*_view.py`.

Pure static analysis (ast) — no PySide6 import, no qapp fixture needed.
"""

import ast
from pathlib import Path

_UI_ROOT = Path(__file__).resolve().parents[4] / "src" / "presentation" / "ui"
_SCREENS_DIR = _UI_ROOT / "screens"


def _iter_python_files(root: Path):
    for path in root.rglob("*.py"):
        if "__pycache__" not in path.parts:
            yield path


def _class_defs(path: Path) -> list[ast.ClassDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]


def _base_name(base: ast.expr) -> str | None:
    if isinstance(base, ast.Name):
        return base.id
    return getattr(base, "attr", None)


def _defines_presenter_class(path: Path) -> bool:
    for cls in _class_defs(path):
        if any(_base_name(base) == "BasePresenter" for base in cls.bases):
            return True
    return False


def _defines_view_class(path: Path) -> bool:
    return any(cls.name.endswith("View") for cls in _class_defs(path))


def test_presenter_classes_live_under_screens_and_are_named_correctly():
    offenders = []
    for path in _iter_python_files(_UI_ROOT):
        if not _defines_presenter_class(path):
            continue
        if _SCREENS_DIR not in path.parents or not path.stem.endswith("_presenter"):
            offenders.append(path)

    assert offenders == [], (
        f"BasePresenter subclasses must live under {_SCREENS_DIR} in a "
        f"'*_presenter.py' file: {[str(p) for p in offenders]}"
    )


def test_view_classes_live_under_screens_and_are_named_correctly():
    offenders = []
    for path in _iter_python_files(_UI_ROOT):
        if not _defines_view_class(path):
            continue
        if _SCREENS_DIR not in path.parents or not path.stem.endswith("_view"):
            offenders.append(path)

    assert offenders == [], (
        f"*View classes must live under {_SCREENS_DIR} in a '*_view.py' file: "
        f"{[str(p) for p in offenders]}"
    )
