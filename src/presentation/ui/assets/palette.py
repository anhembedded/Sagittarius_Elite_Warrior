class Palette:
    """
    @brief Single source of truth for the app's black/gold palette
    ("Sagittarius Elite Warrior" theme, BOT-029 Phase 1).

    @details
    `IconTheme` (icon_loader.py) re-exports the icon-relevant subset of
    these for backward compatibility with existing QtWidgets code. QML
    screens (BOT-030) consume the same values via `ThemeBridge`
    (screens/_qml_shared/theme_bridge.py), a singleton registered into
    every QML engine — so QtWidgets and QML never hardcode the same hex
    value in two places independently.

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
