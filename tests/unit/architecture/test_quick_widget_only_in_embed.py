"""`BUG-115`/`BOT-133` guards — the two app-wide UI mechanisms are reached
through their one entry point, or the build fails naming that entry point.

1. A `QQuickWidget` is constructed, subclassed, or given a clear colour in
   exactly one place: `src/presentation/ui/qml/embed/`.
2. The theme is seeded through `theme_bootstrap.seed_app_theme()`, not by
   spelling out the engine's `configure_app_qml()`/`get_theme_bridge(palette)`
   pair again.

Why guards and not a rule in a document: both defects spread by copy-paste
from the previous file, written by someone who read that file as the pattern
to follow. `qml-rule.md` did not stop the tenth copy of the first, and
`EPIC-006F`'s comment actively misled the next reader about the second. A
rule cannot fail the build; this can. Each message names the API to use
instead, because a guard that only says "no" teaches nothing to whoever hits
it next.

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

_UI_ROOT = Path(__file__).resolve().parents[3] / "src" / "presentation" / "ui"
_EMBED_DIR = _UI_ROOT / "qml" / "embed"

#: The file that *is* the theme-seeding mechanism, so the only one allowed to
#: name the engine calls it wraps.
_THEME_MECHANISM = "theme_bootstrap.py"

#: Seeding the theme means calling one of these **with an argument**. A bare
#: `get_theme_bridge()` reads the already-seeded singleton and is fine
#: anywhere; it is the palette-carrying call that must live in one place.
_SEEDING_CALLS = frozenset({"configure_app_qml", "get_theme_bridge"})


def _ui_python_files() -> list[Path]:
    return sorted(
        path
        for path in _UI_ROOT.rglob("*.py")
        if _EMBED_DIR not in path.parents and "tests" not in path.parts
    )


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


def _scan(
    *, allowed_files: frozenset[str] = frozenset()
) -> tuple[list[str], list[str], list[str]]:
    """One parse per file; three finding lists: `QQuickWidget` constructed or
    subclassed, `setClearColor(...)` called, and palette-carrying theme
    seeding calls."""
    built: list[str] = []
    cleared: list[str] = []
    seeded: list[str] = []

    for path in _ui_python_files():
        if path.name in allowed_files:
            continue
        where = path.relative_to(_UI_ROOT)
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
                elif name in _SEEDING_CALLS and node.args:
                    seeded.append(f"{where}:{node.lineno}: {name}(...)")
    return built, cleared, seeded


def test_ui_tree_is_where_we_think_it_is():
    """A guard that passes because it found nothing to check is how this rots."""
    assert _ui_python_files(), f"no .py under {_UI_ROOT}"
    assert (_EMBED_DIR / "quick_surface.py").is_file()
    assert (_UI_ROOT / _THEME_MECHANISM).is_file()


def test_no_qquickwidget_is_built_or_subclassed_outside_embed():
    built, _, _ = _scan()
    assert not built, (
        "QQuickWidget constructed or subclassed outside qml/embed/ — embed the "
        "scene through `QuickSurface` instead, which clears it to the token of "
        "the `StyleRole` it sits on (BUG-115):\n" + "\n".join(built)
    )


def test_no_host_sets_a_clear_colour():
    _, cleared, _ = _scan()
    assert not cleared, (
        "setClearColor() outside qml/embed/ — the clear colour is the surface "
        "token `QuickSurface` resolves, never a per-host choice; a transparent "
        "one renders black on a real screen (BUG-115):\n" + "\n".join(cleared)
    )


def test_the_theme_is_seeded_through_the_one_function():
    """`theme_bootstrap.py` itself is where the engine calls legitimately
    live — that file *is* the mechanism. Everywhere else, naming them starts
    the seventh partial copy (`BOT-133`)."""
    _, _, seeded = _scan(allowed_files=frozenset({_THEME_MECHANISM}))
    assert not seeded, (
        "the theme is seeded in more than one place — call "
        "`theme_bootstrap.seed_app_theme()` instead (BOT-133):\n" + "\n".join(seeded)
    )
