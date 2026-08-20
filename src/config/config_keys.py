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
    BACKTEST_CHART_OPENGL_ENABLED = "backtest.chart.opengl_enabled"
    BACKTEST_CHART_CACHED_INTERACTION_ENABLED = (
        "backtest.chart.cached_interaction_enabled"
    )
    #: Safety cap on how many candles the Backtest chart loads. It exists
    #: only to bound memory: per-frame pan cost is flat in history size
    #: (viewport windowing draws ~200 bars regardless), so this should stay
    #: large enough to cover a whole backtested range. A chart shorter than
    #: the run leaves trade markers sitting over empty space.
    BACKTEST_CHART_KLINES_FETCH_LIMIT = "backtest.chart.klines_fetch_limit"
    #: BOT-098F6E. One of "python" | "native" | "auto" (default: "auto").
    #: Also overridable via the SAGITTARIUS_BACKTEST_CHART_BACKEND env var (see
    #: BacktestChartHostFactory) — this codebase has no ConfigManager env
    #: layer wired into the real app, so a one-off override reads the
    #: environment directly, the same convention native_chart_runtime.py
    #: already uses for SAGITTARIUS_NATIVE_QML_IMPORT_PATH.
    BACKTEST_CHART_BACKEND = "backtest.chart.backend"

    # Market Data Hub / KLine Inspector
    KLINE_INSPECTOR_PAGE_SIZE = "kline_inspector.page_size"

    # Developer mode — enables extra UI instrumentation (e.g. click logging)
    DEV_MODE = "dev.mode"
