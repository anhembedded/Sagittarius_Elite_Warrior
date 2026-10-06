"""`BUG-115`/`BOT-133` guards, bans since `EPIC-033M`: the application builds
no `QQuickWidget` and seeds no QML theme, anywhere.

1. No `QQuickWidget` is constructed or subclassed, and no host sets a clear
   colour. Until `EPIC-033M` the one exception was `support/ui_kit/embed/`,
   the embedding contract `BUG-115` forced; the app embeds no QML scene any
   more and that package is deleted, so the exception went with it.
2. Nobody seeds the engine's QML theme (`configure_app_qml()` /
   `get_theme_bridge(palette)`). `theme_bootstrap.seed_app_theme()` was the
   one place allowed to; it is deleted with `Palette`, so the call is
   forbidden everywhere, `tests/` included.

The file keeps its name because the rules and the scanned-roots registry cite
it; what it says is in this docstring.

Why guards and not a rule in a document: both defects spread by copy-paste
from the previous file, written by someone who read that file as the pattern
to follow. `qml-rule.md` did not stop the tenth copy of the first, and
`EPIC-006F`'s comment actively misled the next reader about the second. A
rule cannot fail the build; this can. Each message names the API to use
instead, because a guard that only says "no" teaches nothing to whoever hits
it next.

@par The two rules have different scopes, and that is deliberate
Written 2026-09-10, this file scanned `src/presentation/ui` only — and a
retrospective review on 2026-09-15 (`Tasks/reports/EPIC-025_retrospective_review_2026-09-15.md`,
finding S1) proved the hole by planting a violation in `scripts/` and watching
all four tests stay green. `BOT-133`'s own commit message says the theme wiring
had *"six entry points each [with] a partial copy … Now one function, used by
the bootstrapper and all six scripts"* — so five of the six copies it removed
lived in the one directory the guard could not read. `ONBOARDING.md` trap 11
asks for `src/`, `scripts/` **and** `tests/`, and the scopes below now answer
it, each for its own reason:

- **Building a `QQuickWidget`** is forbidden in `src/presentation/ui` and in
  `scripts/`: both run as the real application in front of a user or a
  screenshot, which is where `BUG-115`'s black scene appears. It is *not*
  forbidden in `tests/`, and that is not laziness — a test that loads one
  `.qml` into a bare widget is testing **that file**, not the embedding
  contract, and the render-to-texture defect cannot occur headless at all
  (`BUG-115` §2.4 measured every `grab()` as correct while the screen was
  wrong). Forbidding it there would force those tests through an abstraction
  whose whole subject is something they do not exercise.
- **Seeding the theme** is forbidden everywhere, `tests/` included: nothing
  in the app has a QML theme to seed since `EPIC-033M`.

**These read the syntax tree, not the raw text.** An earlier draft used
regexes and went red on the *documentation* of these very APIs — `style.py`'s
docstring explains when an app must call `get_theme_bridge(palette)` itself,
and `app_bootstrapper.py` carries a comment about `configure_app_qml()`'s
history. Prose about a mechanism is not a use of it, and a guard that cannot
tell the two apart punishes exactly the comments that make the mechanism
findable.

Same family as `test_qml_style_discipline.py` (colour literals in `.qml`).
"""

from __future__ import annotations

import ast
from pathlib import Path

from .ui_trees import UI_TREES

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS_ROOT = _REPO_ROOT / "scripts"
_TESTS_ROOT = _REPO_ROOT / "tests"
#: Where a `QQuickWidget` may not be built: everything that runs as the real
#: application. See the module docstring for why `tests/` is absent.
#:
#: `support/ui_kit` joined the list when `EPIC-025` PR 1.6b moved the widget
#: kit there. Both rules below are about what the running application does,
#: and a file does not stop being the running application because it crossed
#: into `support/` — a `QQuickWidget` built in the kit, or a hand-seeded
#: theme there, is exactly the thing these two tests forbid.
#: `ui_trees.py` supplies the UI half — the third tree (`support/charting`)
#: arrived in PR 1.6f and `chart_toolbar.py` builds a `QQuickWidget`, so a
#: guard reading two trees would have stopped watching the only package
#: that does.
_WIDGET_ROOTS = (*UI_TREES, _SCRIPTS_ROOT)

#: Where the theme may not be seeded by hand — every root, because a test
#: process seeds it for the same reason the app does.
_SEEDING_ROOTS = (*UI_TREES, _SCRIPTS_ROOT, _TESTS_ROOT)

#: Seeding the theme means calling one of these **with an argument**. A bare
#: `get_theme_bridge()` reads the already-seeded singleton and is fine
#: anywhere; it is the palette-carrying call that must live in one place.
_SEEDING_CALLS = frozenset({"configure_app_qml", "get_theme_bridge"})


def _python_files(*roots: Path) -> list[Path]:
    seen: dict[Path, None] = {}
    for root in roots:
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            seen.setdefault(path, None)
    return list(seen)


def _widget_scan_files() -> list[Path]:
    """The UI trees and `scripts/`, minus the `tests/` packages that live inside `src/` (one `.qml` file per
    directory keeps its tests beside it), for the reason in the docstring."""
    return [path for path in _python_files(*_WIDGET_ROOTS) if "tests" not in path.parts]


def _seeding_scan_files() -> list[Path]:
    return _python_files(*_SEEDING_ROOTS)


def _where(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def _called_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _base_names(node: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.add(base.id)
        elif isinstance(base, ast.Attribute):
            names.add(base.attr)
    return names


def _scan_widgets() -> tuple[list[str], list[str]]:
    """`QQuickWidget` constructed or subclassed, and `setClearColor(...)`
    called, anywhere a real application run would reach."""
    built: list[str] = []
    cleared: list[str] = []

    for path in _widget_scan_files():
        where = _where(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and "QQuickWidget" in _base_names(node):
                built.append(f"{where}:{node.lineno}: class {node.name}(QQuickWidget)")
            elif isinstance(node, ast.Call):
                name = _called_name(node)
                if name == "QQuickWidget":
                    built.append(f"{where}:{node.lineno}: QQuickWidget(...)")
                elif name == "setClearColor":
                    cleared.append(f"{where}:{node.lineno}: setClearColor(...)")
    return built, cleared


def _scan_seeding() -> list[str]:
    """Palette-carrying `configure_app_qml`/`get_theme_bridge` calls."""
    seeded: list[str] = []
    for path in _seeding_scan_files():
        where = _where(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _called_name(node)
                if name in _SEEDING_CALLS and node.args:
                    seeded.append(f"{where}:{node.lineno}: {name}(...)")
    return seeded


def test_the_scanned_trees_are_where_this_guard_expects_them():
    """A guard that passes because it found nothing to check is how this rots.

    Each root is asserted separately: a single "some files were found" check
    stays green when one whole root stops being scanned, which is the exact
    failure this guard shipped with for five days.
    """
    for root in (*UI_TREES, _SCRIPTS_ROOT, _TESTS_ROOT):
        assert root.is_dir(), f"{root} is gone — retarget this guard"
        assert _python_files(root), f"no .py under {root}"

    # The scopes really do differ, and each really does reach its own root.
    scanned_for_widgets = {_where(p).split("/")[0] for p in _widget_scan_files()}
    assert {"src", "scripts"} <= scanned_for_widgets, scanned_for_widgets
    scanned_for_seeding = {_where(p).split("/")[0] for p in _seeding_scan_files()}
    assert {"src", "scripts", "tests"} <= scanned_for_seeding, scanned_for_seeding


def test_no_qquickwidget_is_built_or_subclassed():
    built, _ = _scan_widgets()
    assert not built, (
        "QQuickWidget constructed or subclassed — the app is QtWidgets only "
        "(ui-presentation-rule.md §1, EPIC-033M): build the screen from stock "
        "widgets instead:\n" + "\n".join(built)
    )


def test_no_host_sets_a_clear_colour():
    _, cleared = _scan_widgets()
    assert not cleared, (
        "setClearColor() — the app embeds no QML scene (EPIC-033M), so nothing "
        "has a clear colour to set:\n" + "\n".join(cleared)
    )


def test_nobody_seeds_the_qml_theme():
    """`EPIC-033M` deleted `theme_bootstrap.seed_app_theme()` with `Palette`:
    the app renders in the platform's theme and seeds nothing."""
    seeded = _scan_seeding()
    assert not seeded, (
        "the engine's QML theme is seeded — the app applies no palette of its "
        "own (ADR D21, EPIC-033M); remove the call:\n" + "\n".join(seeded)
    )
