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

from sagittarius_engine.extensions.pyside_mvc import configure_app_qml

from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)

_UI_ROOT = _REPO_ROOT / "src" / "presentation" / "ui"


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
        module_name = f"_preview_{key}"
        spec = importlib.util.spec_from_file_location(module_name, preview_path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        build_fn = getattr(module, "build_preview", None)
        if callable(build_fn):
            previews[key] = build_fn

    return previews


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

    if not args.screen:
        parser.print_help()
        sys.exit(1)

    if args.screen not in previews:
        print(
            f"Error: Unknown preview target '{args.screen}'. Available targets: {list(previews.keys())}",
            file=sys.stderr,
        )
        sys.exit(1)

    app = QApplication.instance() or QApplication(sys.argv)
    configure_app_qml(Palette.as_ui_dict(), get_icon_loader(), Palette.as_icon_dict())

    widget = previews[args.screen]()
    widget.setWindowTitle(f"QML Preview — {args.screen}")
    widget.show()

    errors = widget.errors() if hasattr(widget, "errors") else []
    if errors:
        print(f"QML errors in '{args.screen}': {errors}", file=sys.stderr)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
