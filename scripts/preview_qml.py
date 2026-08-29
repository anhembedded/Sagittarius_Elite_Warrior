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

from sagittarius_engine.extensions.pyside_mvc import configure_app_qml, get_theme_bridge

from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)

_UI_ROOT = _REPO_ROOT / "src" / "presentation" / "ui"


def _load_build_preview(
    preview_path: Path, module_name: str
) -> Callable[[], QWidget] | None:
    """Imports one `preview.py` by path (not by package) and returns its
    `build_preview`, or `None` if the file has no such callable.

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
    build_fn = getattr(module, "build_preview", None)
    return build_fn if callable(build_fn) else None


def discover_previews() -> dict[str, Callable[[], QWidget]]:
    """
    Scans `src/presentation/ui/` recursively for `preview.py` files.
    Returns a mapping of {component_or_screen_name: build_preview_callable}.
    """
    previews: dict[str, Callable[[], QWidget]] = {}
    if not _UI_ROOT.exists():
        return previews

    for preview_path in sorted(_UI_ROOT.rglob("preview.py")):
        # Key is the parent directory name (e.g. 'sidebar', 'dashboard', 'settings', 'backtest')
        key = preview_path.parent.name
        build_fn = _load_build_preview(preview_path, f"_preview_{key}")
        if build_fn is not None:
            previews[key] = build_fn

    return previews


def _ensure_qt_theme_ready() -> None:
    """Boots just enough of the app's theming for a `kit`-based widget
    (`Overlay`/`Panel`/`apply_role`, or a `.qml` reading `Theme.*`) to
    construct without raising.

    @details `configure_app_qml()` alone is NOT enough — `get_theme_bridge()`
    is a separate singleton `app_bootstrapper.py` seeds in its own call, and
    any widget touching `apply_role()` before that seed raises `ValueError:
    get_theme_bridge() has no palette yet`. This was a real, pre-existing
    gap in this script (reproduces today on `--list`-discovered `settings`,
    unrelated to `--dir`) — fixed here once for every target, not
    special-cased for QML-widget previews.
    """
    # `as_ui_dict()` returns `dict[str, str | float]` since `EPIC-007F` gave
    # this app its own size tokens; the engine still annotates the parameter
    # `dict[str, str]`. Runtime is fine — it feeds a `QQmlPropertyMap`, which
    # takes any value, and production does exactly this on every launch
    # (`app_bootstrapper.py`, unchecked only because `presentation/` is
    # excluded from the mypy gate). The narrow annotation is the engine's to
    # widen; ignored here rather than converting the sizes to strings, which
    # would change what the UI actually renders.
    configure_app_qml(
        Palette.as_ui_dict(),  # type: ignore[arg-type]
        get_icon_loader(),
        Palette.as_icon_dict(),
    )
    get_theme_bridge(Palette.as_ui_dict())  # type: ignore[arg-type]


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

    build_fn = _load_build_preview(preview_path, f"_preview_dir_{target_dir.name}")
    if build_fn is None:
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
