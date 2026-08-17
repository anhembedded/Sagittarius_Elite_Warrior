from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_extension import IExtension

logger = logging.getLogger("App.AssetValidator")

_DEFAULT_ICONS_DIR = Path(__file__).parent / "icons"

REQUIRED_UI_ICONS: list[str] = [
    "bar-chart-2",
    "briefcase",
    "calendar",
    "chart-candlestick",
    "chevron-down",
    "circle-check-big",
    "clock",
    "copy",
    "database",
    "dollar-sign",
    "download",
    "eye",
    "eye-off",
    "info",
    "layout-dashboard",
    "play",
    "plus-circle",
    "rotate-ccw",
    "save",
    "search",
    "settings",
    "shield",
    "sliders",
    "square",
    "trash-2",
    "triangle-alert",
    "triangle-down",
    "triangle-up",
    "zap",
]


class AssetValidatorExtension(IExtension[Any]):
    """
    Fail-Fast UI Asset Validator Extension (BOT-071).
    Validates the presence of required UI SVG icon assets during application boot.
    In Dev mode (dev.mode=True), fails fast with CRITICAL FAULT if any asset is missing.
    In Production mode, logs a warning and allows fallback rendering without crashing.
    """

    def __init__(
        self,
        required_icons: list[str] | None = None,
        icons_dir: Path | None = None,
    ) -> None:
        self.required_icons = required_icons or list(REQUIRED_UI_ICONS)
        self.icons_dir = icons_dir or _DEFAULT_ICONS_DIR

    def register(self, context: Any) -> None:
        pass

    def boot(self, context: Any) -> None:
        missing_icons: list[str] = []
        for icon_name in self.required_icons:
            icon_file = self.icons_dir / f"{icon_name}.svg"
            if not icon_file.is_file():
                missing_icons.append(f"{icon_name} ({icon_file})")

        if not missing_icons:
            msg = "Pre-flight asset check passed. All required UI assets found."
            logger.info(msg)
            if hasattr(context, "logger") and context.logger:
                context.logger.info(msg)
            return

        is_dev_mode = False
        try:
            if hasattr(context, "container") and context.container:
                config = context.container.resolve(IConfig)
                is_dev_mode = bool(config.get("dev.mode", False))
        except (AttributeError, KeyError, TypeError, ValueError, LookupError):
            is_dev_mode = False

        if is_dev_mode:
            error_msg = (
                f"CRITICAL FAULT: Missing required UI icon assets: {', '.join(missing_icons)}\n"
                f"Expected directory: {self.icons_dir}\n"
                "Please restore the missing SVG files in src/presentation/ui/assets/icons/."
            )
            logger.error(error_msg)
            if hasattr(context, "logger") and context.logger:
                context.logger.error(error_msg)
            sys.exit(1)
        else:
            warning_msg = (
                f"WARNING: Missing UI icon assets in production: {', '.join(missing_icons)} "
                "(using blank fallback)."
            )
            logger.warning(warning_msg)
            if hasattr(context, "logger") and context.logger:
                context.logger.warning(warning_msg)

    def shutdown(self, context: Any) -> None:
        pass
