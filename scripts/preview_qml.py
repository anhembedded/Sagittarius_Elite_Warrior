"""
Live preview for a single QML screen or UI component (BOT-031).

Automatically discovers all `preview.py` files under `src/presentation/ui/`
and invokes `build_preview() -> QWidget` without needing a full DI container
or Sagittarius Engine boot.

Usage:
    python scripts/preview_qml.py --list
    python scripts/preview_qml.py backtest
    python scripts/preview_qml.py dashboard
    python scripts/preview_qml.py data_management
    python scripts/preview_qml.py settings
    python scripts/preview_qml.py sidebar
    python scripts/preview_qml.py --dir src/presentation/ui/qml/Capital
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget

# Ensure repository root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from Sagittarius_Elite_Warrior.src.support.ui_kit.theme_bootstrap import (
    seed_app_theme,
)

#: Every tree that holds UI code today. `EPIC-025` is moving the UI out of
#: `src/presentation/ui/` package by package, and a preview that crosses over
#: must stay runnable: PR 1.6d moved `sidebar/` and the discovery — which read
#: the legacy tree only — stopped finding it, which is what
#: `test_discover_previews_finds_all_targets` said. `tests/unit/architecture/
#: ui_trees.py` is the canonical list other guards read for this same
#: question ("the fourth occasion" its own docstring names); this file keeps
#: its own copy rather than importing it, since `scripts/` importing from
#: `tests/` would be a new backward dependency direction, but the *set* is
#: meant to track that file's, not drift from it again — `EPIC-025` PR 4.4b
#: added `modules/market_data/ui` here after `data_management`'s move made
#: this file's own drift (missing `support/charting`, `modules/trading/ui`,
#: `modules/strategy/ui` already) visible for the first time. PR 4.4c added
#: `modules/trading/ui` for the same reason: `screens/trading`/`dashboard`
#: brought real `preview.py` files there (`trading/`, `dashboard/`), and
#: without this row `discover_previews()` silently dropped both — the
#: `order_book/preview.py` PR 4.1b already left there was the same drift,
#: just never a `test_discover_previews_finds_all_targets` failure because
#: nothing had asked for it by name yet. `modules/strategy/ui` still has no
#: `preview.py` of its own, so it stays off this list until it does — adding
#: an empty root now would be solving a case that does not exist yet
#: (`architecture-rule.md` §7.2.1). This list shrinks back to one entry when
#: Phase 4 deletes the legacy tree.
_UI_ROOTS = (
    _REPO_ROOT / "src" / "presentation" / "ui",
    _REPO_ROOT / "src" / "support" / "ui_kit",
    _REPO_ROOT / "src" / "modules" / "market_data" / "ui",
    _REPO_ROOT / "src" / "modules" / "trading" / "ui",
)


def _load_preview_module(preview_path: Path, module_name: str) -> object | None:
    """Imports one `preview.py` by path (not by package) and returns the
    loaded module, or `None` if it could not be imported.

    @details `importlib.util.spec_from_file_location` gives the module no
    parent package, so a `preview.py` reaching for a sibling with a relative
    import (`from .foo import Foo`) fails with `ImportError: attempted
    relative import with no known parent package` — every `preview.py` in
    this repo must import its own screen/widget with the full
    `Sagittarius_Elite_Warrior....` path, the same as every other module
    that already does (see `qml-rule.md` for the widget-directory layout
    this loads from under `--dir`).
    """
    spec = importlib.util.spec_from_file_location(module_name, preview_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def discover_previews() -> dict[str, Callable[[], QWidget]]:
    """
    Scans both UI trees recursively for `preview.py` files.
    Returns a mapping of {component_or_screen_name: build_preview_callable}.
    """
    previews: dict[str, Callable[[], QWidget]] = {}
    sources: dict[str, Path] = {}

    for root in _UI_ROOTS:
        if not root.exists():
            continue
        for preview_path in sorted(root.rglob("preview.py")):
            module = _load_preview_module(
                preview_path, f"_preview_{preview_path.parent.name}"
            )
            if module is None:
                continue
            build_fn = getattr(module, "build_preview", None)
            if not callable(build_fn):
                continue
            # Key is the parent directory name (e.g. 'sidebar', 'dashboard',
            # 'settings', 'backtest') — unless the module sets its own
            # `PREVIEW_KEY`, which every `modules/<name>/ui/preview.py` at a
            # module's own root must: that parent directory is named `ui` for
            # every module, so the fallback would collide the moment a second
            # module put a `preview.py` directly there (`EPIC-025` PR 4.4b —
            # `data_management` moved to `modules/market_data/ui/preview.py`,
            # whose parent is `ui`, not `data_management`).
            key = getattr(module, "PREVIEW_KEY", None) or preview_path.parent.name
            if key in sources:
                # Two roots make this reachable, and the docstring below has
                # always warned that a colliding basename "would silently
                # shadow or collide". Silently is the part worth removing: a
                # shadowed preview is a widget nobody can open any more, and
                # nothing else in the repository would say so. Measured when
                # the second root was added: zero collisions across the 14
                # `preview.py` files, so this raises only for something new.
                raise RuntimeError(
                    f"two preview.py files claim the key {key!r}: "
                    f"{sources[key]} and {preview_path}. Rename one directory, "
                    "or address it with --dir."
                )
            previews[key] = build_fn
            sources[key] = preview_path

    return previews


def _ensure_qt_theme_ready() -> None:
    """Seeds the app's theme so a `kit`-based widget (`Overlay`/`Panel`/
    `apply_role`) or a `.qml` reading `Theme.*` constructs without raising.

    @details One call, shared with the bootstrapper and every probe script —
    `src/presentation/ui/theme_bootstrap.py` explains why that is one
    function and not a snippet each entry point keeps its own copy of. The
    `"Basic"` Qt Quick Controls pin used to be repeated here too; it now
    lives in the engine's `create_quick_widget()`, which every embedded
    scene goes through (`BOT-132`).
    """
    seed_app_theme()


def _build_preview_for_dir(raw_dir: str) -> QWidget:
    """`--dir` addressing: load exactly `<raw_dir>/preview.py`, by path
    rather than by a name already known to `discover_previews()`.

    @details For a widget under active development that has no registered
    short name yet, or to disambiguate two directories that happen to share
    a basename — `discover_previews()` only keys by `parent.name`, so a
    second `Capital/` elsewhere would silently shadow or collide.
    """
    target_dir = Path(raw_dir).expanduser().resolve()
    preview_path = target_dir / "preview.py"
    if not preview_path.is_file():
        print(
            f"Error: no preview.py in '{target_dir}'.\n"
            "Every previewable UI package needs one exposing "
            "build_preview() -> QWidget (see qml-rule.md / ui-presentation-rule.md).",
            file=sys.stderr,
        )
        sys.exit(1)

    module = _load_preview_module(preview_path, f"_preview_dir_{target_dir.name}")
    build_fn = getattr(module, "build_preview", None) if module is not None else None
    if not callable(build_fn):
        print(
            f"Error: {preview_path} does not declare build_preview().",
            file=sys.stderr,
        )
        sys.exit(1)
    return build_fn()


def main() -> None:
    previews = discover_previews()

    parser = argparse.ArgumentParser(
        description="Live preview for QML screens and UI components (BOT-031)."
    )
    parser.add_argument(
        "screen",
        nargs="?",
        help=f"Target screen or component to preview (available: {', '.join(sorted(previews.keys()))})",
    )
    parser.add_argument(
        "--dir",
        metavar="PATH",
        help="Preview the preview.py found directly under this directory, "
        "addressed by path instead of by registered name.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all auto-discovered previewable screens and components.",
    )

    args = parser.parse_args()

    if args.list:
        print("Discovered previewable UI components and screens:")
        for key in sorted(previews.keys()):
            print(f"  - {key}")
        sys.exit(0)

    if not args.dir and not args.screen:
        parser.print_help()
        sys.exit(1)

    app = QApplication.instance() or QApplication(sys.argv)
    _ensure_qt_theme_ready()

    if args.dir:
        widget = _build_preview_for_dir(args.dir)
        window_title = f"QML Preview — {Path(args.dir).name}"
    else:
        if args.screen not in previews:
            print(
                f"Error: Unknown preview target '{args.screen}'. Available targets: {list(previews.keys())}",
                file=sys.stderr,
            )
            sys.exit(1)
        widget = previews[args.screen]()
        window_title = f"QML Preview — {args.screen}"

    widget.setWindowTitle(window_title)
    widget.show()

    errors = widget.errors() if hasattr(widget, "errors") else []
    if errors:
        print(f"QML errors in '{window_title}': {errors}", file=sys.stderr)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
