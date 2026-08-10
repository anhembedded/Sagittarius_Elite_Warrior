class Palette:
    """
    @brief Single source of truth for the app's black/gold palette
    ("Sagittarius Elite Warrior" theme, BOT-029 Phase 1).

    @details
    `IconTheme` (icon_loader.py) re-exports the icon-relevant subset of
    these for backward compatibility with existing QtWidgets code. QML
    screens (BOT-030) consume the same values via the engine's shared
    theme bridge (sagittarius_engine.extensions.pyside_mvc.QmlShared,
    configured once with this app's own palette dict via
    `configure_app_qml()` in app_bootstrapper.py) — so QtWidgets and QML
    never hardcode the same hex value in two places independently.

    `qss/style.qss` still hardcodes its own literal hex values (QSS is a
    static text file, not generated from Python) — keeping it in sync with
    this class when the palette changes is a manual step, same as today.
    """

    BG = "#0a0a0c"
    BG_SIDEBAR = "#0d0e11"
    BG_CARD = "#111318"
    BG_CARD_HEADER = "#15171d"
    BORDER = "#23262e"
    TEXT_PRIMARY = "#e8e9ec"

    ACCENT = "#F3BA2F"  # Binance yellow
    SUCCESS = "#0ECB81"  # green
    DANGER = "#F6465D"  # red
    MUTED = "#848E9C"  # gray

    @classmethod
    def as_ui_dict(cls) -> dict[str, str]:
        """Maps QML property name -> color, for `configure_app_qml()`'s
        `ui_palette` (exposed to QML as `Theme.<name>`)."""
        return {
            "bg": cls.BG,
            "bgSidebar": cls.BG_SIDEBAR,
            "bgCard": cls.BG_CARD,
            "bgCardHeader": cls.BG_CARD_HEADER,
            "border": cls.BORDER,
            "textPrimary": cls.TEXT_PRIMARY,
            "accent": cls.ACCENT,
            "success": cls.SUCCESS,
            "danger": cls.DANGER,
            "muted": cls.MUTED,
        }

    @classmethod
    def as_icon_dict(cls) -> dict[str, str]:
        """Maps icon-color token -> color, for `configure_app_qml()`'s
        `icon_palette` (used in `image://icons/<name>/<token>` URLs).
        Historically a separate, smaller vocabulary than `as_ui_dict()` —
        kept distinct rather than unified, matching the icon URLs already
        in QML (e.g. "image://icons/play/success") that only ever
        reference this subset."""
        return {
            "accent": cls.ACCENT,
            "success": cls.SUCCESS,
            "danger": cls.DANGER,
            "muted": cls.MUTED,
            "text": cls.TEXT_PRIMARY,
        }
