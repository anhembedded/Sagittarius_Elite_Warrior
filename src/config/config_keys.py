from enum import Enum


class ConfigKeys(str, Enum):
    """
    @brief Enumeration for application configuration keys to avoid magic strings.
    """

    BINANCE_RATE_LIMIT_DELAY_MS = "binance.rate_limit_delay_ms"
    DATABASE_DIR = "database.dir"
    #: `EPIC-021A` — replaces the dead `BINANCE_REST_URL`/`BINANCE_WS_URL`
    #: (`BUG-081`: declared, read nowhere, editing them changed nothing).
    #: Endpoint resolution is a function of this venue, computed by
    #: `binance_endpoints.py`, not a second config key to keep in sync.
    #: Values are `MarketDataVenue` members.
    EXCHANGE_MARKET_DATA_VENUE = "exchange.market_data_venue"
    LOG_FORMAT = "LOG_FORMAT"
    LOG_LEVEL = "log.level"
    LOG_CONSOLE_ENABLED = "log.console.enabled"
    LOG_VIEWER_ENABLED = "log.viewer.enabled"
    LOG_VIEWER_HOST = "log.viewer.host"
    LOG_VIEWER_PORT = "log.viewer.port"
    LOG_VIEWER_MODULE = "log.viewer.module"

    # Interactive shell (`presentation/cli/interactive_shell.py`) — the
    # command routing table (`{cmd_name: {"help": ..., ...}}`) that drives
    # both `default()`'s dispatch and `do_help()`'s listing.
    CLI_COMMANDS = "CLI_COMMANDS"

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
    #: Which concrete View the Backtest screen is built with, chosen once at
    #: bootstrap (`EPIC-013F`). A View is never swapped while the app runs —
    #: the Presenter is not built to survive that — so this is read exactly
    #: once, when the router registers the screen. Values are the members of
    #: `screens.backtest.view_factory.BacktestViewKey`.
    BACKTEST_VIEW = "backtest.view"

    # Market Data Hub / KLine Inspector
    KLINE_INSPECTOR_PAGE_SIZE = "kline_inspector.page_size"

    # Developer mode — enables extra UI instrumentation (e.g. click logging)
    DEV_MODE = "dev.mode"
