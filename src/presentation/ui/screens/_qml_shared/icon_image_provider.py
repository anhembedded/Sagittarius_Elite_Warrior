from PySide6.QtCore import QSize
from PySide6.QtGui import QPixmap
from PySide6.QtQuick import QQuickImageProvider

from Binace_Bot.src.presentation.ui.assets import Palette, get_icon_loader

ICON_PROVIDER_ID = "icons"

_DEFAULT_SIZE = 20
_HEX_LENGTH = 6

# Named palette keys usable in a QML icon URL, e.g. image://icons/play/success.
# Keeps QML referencing the shared palette by meaning rather than by literal
# hex, so a palette change propagates without editing every .qml file.
_PALETTE_KEYS = {
    "accent": Palette.ACCENT,
    "success": Palette.SUCCESS,
    "danger": Palette.DANGER,
    "muted": Palette.MUTED,
    "text": Palette.TEXT_PRIMARY,
}


class IconImageProvider(QQuickImageProvider):
    """
    @brief Serves recolored Lucide icons to QML via `image://icons/<name>/<color>`.

    @details
    QML has no equivalent of QIcon, and the bundled Lucide SVGs use a
    `currentColor` placeholder that a plain `Image { source: "...svg" }`
    would never resolve. This adapter delegates to the existing
    `IconLoader` (assets/icon_loader.py) so recoloring, caching and the
    blank-icon fallback all stay in one place rather than being
    reimplemented for QML.

    `<color>` is either a named palette key (see `_PALETTE_KEYS`) or a raw
    6-digit hex without the leading '#' (which QML URLs cannot carry).
    Unknown values fall back to the muted default, matching IconLoader's
    own never-raise contract — a bad icon must not take down a screen.
    """

    def __init__(self) -> None:
        super().__init__(QQuickImageProvider.ImageType.Pixmap)
        self._icon_loader = get_icon_loader()

    def requestPixmap(
        self, image_id: str, size: QSize, requested_size: QSize
    ) -> QPixmap:
        """
        @param image_id The URL path after `image://icons/`, i.e. "name" or
        "name/color".
        @param size Out-parameter Qt fills with the produced size.
        @param requested_size QML's `sourceSize`, or an invalid size when the
        caller didn't constrain it.
        """
        name, color = self._parse_id(image_id)
        edge = self._resolve_edge(requested_size)

        pixmap = self._icon_loader.get_icon(name, color=color, size=edge).pixmap(
            edge, edge
        )
        size.setWidth(pixmap.width())
        size.setHeight(pixmap.height())
        return pixmap

    @staticmethod
    def _parse_id(image_id: str) -> tuple[str, str]:
        name, _, color_token = image_id.partition("/")
        return name, IconImageProvider._resolve_color(color_token)

    @staticmethod
    def _resolve_color(token: str) -> str:
        if not token:
            return Palette.MUTED
        named = _PALETTE_KEYS.get(token.lower())
        if named is not None:
            return named
        if len(token) == _HEX_LENGTH:
            try:
                int(token, 16)
            except ValueError:
                return Palette.MUTED
            return f"#{token}"
        return Palette.MUTED

    @staticmethod
    def _resolve_edge(requested_size: QSize) -> int:
        """Icons are square: takes the larger requested dimension, or the
        default when QML didn't specify a sourceSize."""
        edge = max(requested_size.width(), requested_size.height())
        return edge if edge > 0 else _DEFAULT_SIZE
