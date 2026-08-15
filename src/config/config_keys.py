from enum import Enum


class ConfigKeys(str, Enum):
    """
    @brief Enumeration for application configuration keys to avoid magic strings.
    """

    BINANCE_RATE_LIMIT_DELAY_MS = "binance.rate_limit_delay_ms"
    DATABASE_DIR = "database.dir"
    BINANCE_WS_URL = "BINANCE_WS_URL"
    BINANCE_REST_URL = "BINANCE_REST_URL"
    LOG_FORMAT = "LOG_FORMAT"
    LOG_LEVEL = "log.level"
    LOG_CONSOLE_ENABLED = "log.console.enabled"
    LOG_VIEWER_ENABLED = "log.viewer.enabled"
    LOG_VIEWER_HOST = "log.viewer.host"
    LOG_VIEWER_PORT = "log.viewer.port"
    LOG_VIEWER_MODULE = "log.viewer.module"

    # UI Appearance
    UI_FONT_FAMILY = "ui.font.family"
    UI_FONT_SIZE = "ui.font.size"
    UI_FONT_FALLBACKS = "ui.font.fallbacks"
    UI_THEME_ACCENT_COLOR = "ui.theme.accent_color"
    UI_THEME_REPLACE_COLOR = "ui.theme.replace_color"

    # Chart Configuration
    CHART_CARD_MAX_ZOOM_OUT_CANDLES = "CHART_CARD_MAX_ZOOM_OUT_CANDLES"

    # Backtest Configuration
    BACKTEST_LOG_MAX_ENTRIES = "backtest.log_max_entries"

    # Developer mode — enables extra UI instrumentation (e.g. click logging)
    DEV_MODE = "dev.mode"
