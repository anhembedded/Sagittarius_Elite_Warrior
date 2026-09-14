"""
Nothing applies a stylesheet to the whole application, and no third-party
theme is installed (ADR D21, HLD §11.4).

`qdarktheme` used to paint every widget from `app_bootstrapper._apply_theme`.
`EPIC-025` PR 0.2 removed it: standard controls now render in the platform's
theme, which is what the user asked for (*"chỉ cần dùng default theme của OS"*)
and what makes a rebuilt panel look native without a single line of styling.

Two things this guard forbids, forever:

1. importing a theme distribution (`qdarktheme`, `qt_material`, `breeze_resources`,
   `qtmodern`) anywhere in `src/` or `scripts/`;
2. calling `setStyleSheet` on a `QApplication` — the global sheet. A widget
   styling **itself** is still allowed while the old screens live, and shrinks
   under `test_app_styling_only_shrinks.py`.

A designed theme is a later decision the user deferred explicitly (*"sau này
design màu theme tính sau"*). When it arrives it comes as a `QPalette` the shell
installs, not as a stylesheet — so this guard stays true.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCANNED_ROOTS = (_REPO_ROOT / "src", _REPO_ROOT / "scripts")

#: Distributions whose whole purpose is to restyle every widget at once.
_THEME_PACKAGES = frozenset(
    {"qdarktheme", "qt_material", "qtmodern", "breeze_resources"}
)

#: Receivers whose `setStyleSheet` reaches every widget in the process.
_APPLICATION_RECEIVERS = frozenset({"app", "application", "qapp", "q_app"})


def _python_files() -> list[Path]:
    return sorted(
        path
        for root in _SCANNED_ROOTS
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _imported_theme_packages(tree: ast.AST) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(
                alias.name.split(".")[0]
                for alias in node.names
                if alias.name.split(".")[0] in _THEME_PACKAGES
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root in _THEME_PACKAGES:
                found.add(root)
    return found


def _application_wide_style_calls(tree: ast.AST) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "setStyleSheet":
            continue
        if _is_the_whole_application(func.value):
            lines.append(node.lineno)
    return lines


def _is_the_whole_application(receiver: ast.expr) -> bool:
    """`app`/`qapp` by name, or `QApplication.instance()` / `QApplication(...)`."""
    if isinstance(receiver, ast.Name):
        return receiver.id.lower() in _APPLICATION_RECEIVERS
    return isinstance(receiver, ast.Call) and _is_qapplication_lookup(receiver)


def _is_qapplication_lookup(call: ast.Call) -> bool:
    """`QApplication.instance().setStyleSheet(...)` and friends."""
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr == "instance"
    return isinstance(func, ast.Name) and func.id in {"QApplication", "QGuiApplication"}


def test_scanned_roots_are_there() -> None:
    for root in _SCANNED_ROOTS:
        assert root.is_dir(), f"missing scan root {root}"
    assert len(_python_files()) > 100


def test_no_theme_distribution_is_imported() -> None:
    offenders = [
        f"  {path.relative_to(_REPO_ROOT).as_posix()}: {sorted(packages)}"
        for path in _python_files()
        if (
            packages := _imported_theme_packages(
                ast.parse(path.read_text(encoding="utf-8"))
            )
        )
    ]
    assert offenders == [], (
        "a third-party theme is being imported. The app renders in the OS theme\n"
        "(ADR D21); a future designed theme arrives as a QPalette, not a sheet.\n"
        + "\n".join(offenders)
    )


def test_no_stylesheet_is_applied_to_the_whole_application() -> None:
    offenders = [
        f"  {path.relative_to(_REPO_ROOT).as_posix()}:{line}"
        for path in _python_files()
        for line in _application_wide_style_calls(
            ast.parse(path.read_text(encoding="utf-8"))
        )
    ]
    assert offenders == [], (
        "setStyleSheet on the application paints every widget in the process —\n"
        "exactly what ADR D21 removed. Style the one widget that needs it.\n"
        + "\n".join(offenders)
    )


def test_the_guard_sees_both_violations() -> None:
    source = (
        "import qdarktheme\n"
        "app.setStyleSheet(qdarktheme.load_stylesheet('dark'))\n"
        "QApplication.instance().setStyleSheet('')\n"
        "widget.setStyleSheet('color: red')\n"
    )
    tree = ast.parse(source)
    assert _imported_theme_packages(tree) == {"qdarktheme"}
    assert _application_wide_style_calls(tree) == [2, 3]
