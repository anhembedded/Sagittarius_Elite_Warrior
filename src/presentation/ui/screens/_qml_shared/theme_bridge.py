from PySide6.QtCore import Property, QObject

from Binace_Bot.src.presentation.ui.assets import Palette

_THEME_CONTEXT_NAME = "Theme"


class ThemeBridge(QObject):
    """
    @brief Exposes the app palette (assets/palette.py) to QML as bindable
    properties, so `.qml` files reference `Theme.accent` instead of
    hardcoding hex values per screen.

    @details
    Read-only and constant — the app has no runtime theme switching, so
    these deliberately have no NOTIFY signal (QML binds them once, which
    is correct and avoids implying a capability that doesn't exist).
    """

    @Property(str, constant=True)
    def bg(self) -> str:
        return Palette.BG

    @Property(str, constant=True)
    def bgSidebar(self) -> str:
        return Palette.BG_SIDEBAR

    @Property(str, constant=True)
    def bgCard(self) -> str:
        return Palette.BG_CARD

    @Property(str, constant=True)
    def bgCardHeader(self) -> str:
        return Palette.BG_CARD_HEADER

    @Property(str, constant=True)
    def border(self) -> str:
        return Palette.BORDER

    @Property(str, constant=True)
    def textPrimary(self) -> str:
        return Palette.TEXT_PRIMARY

    @Property(str, constant=True)
    def accent(self) -> str:
        return Palette.ACCENT

    @Property(str, constant=True)
    def success(self) -> str:
        return Palette.SUCCESS

    @Property(str, constant=True)
    def danger(self) -> str:
        return Palette.DANGER

    @Property(str, constant=True)
    def muted(self) -> str:
        return Palette.MUTED


_shared_theme_bridge: ThemeBridge | None = None


def get_theme_bridge() -> ThemeBridge:
    """
    @brief Returns the shared ThemeBridge instance (lazy singleton), mirroring
    the existing `get_icon_loader()` convention in assets/icon_loader.py.
    @details One instance app-wide: it holds no per-screen state, and every
    QML context property must point at an object Python keeps alive — a
    module-level singleton makes that ownership unambiguous.
    """
    global _shared_theme_bridge
    if _shared_theme_bridge is None:
        _shared_theme_bridge = ThemeBridge()
    return _shared_theme_bridge


def register_theme(quick_widget) -> None:
    """
    @brief Registers the shared ThemeBridge as the `Theme` context property
    on a QQuickWidget's root context.
    @details Called by QmlHostView before loading any QML source, so every
    screen gets `Theme.*` without repeating the wiring.
    """
    quick_widget.rootContext().setContextProperty(
        _THEME_CONTEXT_NAME, get_theme_bridge()
    )
