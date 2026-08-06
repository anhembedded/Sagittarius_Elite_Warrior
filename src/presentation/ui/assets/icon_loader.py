import logging
from base64 import b64encode
from pathlib import Path
from typing import Dict, Optional, Tuple

from PySide6.QtCore import QBuffer, QIODeviceBase, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

logger = logging.getLogger("App.IconLoader")

_ICONS_DIR = Path(__file__).parent / "icons"
_DEFAULT_SIZE = 20


class IconTheme:
    """
    @brief Fixed palette icons are recolored against — matches the Binance-style dark
    theme already used across the UI (chart_card bull/bear colors, accent color).
    """

    ACCENT = "#F3BA2F"  # Binance yellow
    SUCCESS = "#0ECB81"  # green
    DANGER = "#F6465D"  # red
    MUTED = "#848E9C"  # gray (default icon color)


class IconLoader:
    """
    @brief Loads Lucide SVG icons (assets/icons/*.svg), recolors them by substituting
    the SVG's `currentColor` placeholder, and caches the rendered QIcon per
    (name, color, size) so repeated requests don't re-parse and re-paint the same SVG.
    @details Single Responsibility: icon loading/caching/recoloring only — no knowledge
    of which widget uses which icon. Never raises: a missing or malformed SVG resolves
    to a blank transparent icon instead of crashing the UI.
    """

    def __init__(self, icons_dir: Path = _ICONS_DIR) -> None:
        self._icons_dir = icons_dir
        self._cache: Dict[Tuple[str, str, int], QIcon] = {}

    def get_icon(
        self, name: str, color: str = IconTheme.MUTED, size: int = _DEFAULT_SIZE
    ) -> QIcon:
        """
        @param name Icon file stem, e.g. "play" for icons/play.svg.
        @param color Hex color substituted for the SVG's stroke="currentColor".
        @param size Rendered pixmap size in pixels (icons are square).
        """
        cache_key = (name, color, size)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        icon = self._render(name, color, size)
        self._cache[cache_key] = icon
        return icon

    def _render(self, name: str, color: str, size: int) -> QIcon:
        svg_path = self._icons_dir / f"{name}.svg"
        try:
            svg_data = svg_path.read_text(encoding="utf-8")
        except OSError:
            logger.warning(
                f"Icon not found: {name!r} ({svg_path}) — using blank fallback."
            )
            return self._blank_icon(size)

        colored_svg = svg_data.replace("currentColor", color)
        renderer = QSvgRenderer(colored_svg.encode("utf-8"))
        if not renderer.isValid():
            logger.warning(f"Icon failed to parse: {name!r} — using blank fallback.")
            return self._blank_icon(size)

        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)

    def get_icon_data_uri(
        self, name: str, color: str = IconTheme.MUTED, size: int = _DEFAULT_SIZE
    ) -> str:
        """
        @brief Returns a `data:image/png;base64,...` URI for embedding an icon inline in
        rich text (e.g. an `<img>` tag in a QTextEdit log line) — QTextEdit has no notion
        of a QIcon, only image sources it can resolve.
        """
        pixmap = self.get_icon(name, color, size).pixmap(size, size)
        buffer = QBuffer()
        buffer.open(QIODeviceBase.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, "PNG")
        encoded = b64encode(bytes(buffer.data())).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    @staticmethod
    def _blank_icon(size: int) -> QIcon:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        return QIcon(pixmap)

    def clear_cache(self) -> None:
        self._cache.clear()


_default_loader: Optional[IconLoader] = None


def get_icon_loader() -> IconLoader:
    """Returns the shared app-wide IconLoader instance (lazy singleton)."""
    global _default_loader
    if _default_loader is None:
        _default_loader = IconLoader()
    return _default_loader
