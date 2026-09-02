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
    #: `EPIC-021F` — separate from `EXCHANGE_MARKET_DATA_VENUE` on purpose
    #: (ADR §2): where chart data comes from and where an order would be
    #: sent are independent choices. Defaults to `TradingVenue.DISABLED` —
    #: trading is opt-in, never on by config omission. Values are
    #: `TradingVenue` members.
    EXCHANGE_TRADING_VENUE = "exchange.trading_venue"
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

    # `EPIC-021G` — live trading. `TRADING_ENABLED`'s saved value is
    # intentionally NEVER read into `TradingSessionState` at boot (see that
    # class's own docstring) — it exists here only so the safe default is
    # documented in `app_config.json`, the same reason
    # `EXCHANGE_TRADING_VENUE` got one (`EPIC-021F`).
    TRADING_ENABLED = "trading.enabled"
    #: Blocks a live order once this many have been sent this session —
    #: the one limit that stops a runaway signal loop outright.
    TRADING_MAX_ORDERS_PER_SESSION = "trading.max_orders_per_session"
    #: Blocks a single order whose notional exceeds this many USDT.
    TRADING_MAX_NOTIONAL_PER_ORDER_USDT = "trading.max_notional_per_order_usdt"
    #: Blocks a new order on a symbol that already has this many open
    #: positions — 1 enforces the One-way-mode assumption (ADR §6).
    TRADING_MAX_POSITIONS_PER_SYMBOL = "trading.max_positions_per_symbol"
    #: Blocks a second order on the same symbol sent sooner than this many
    #: seconds after the previous one — the same class of problem
    #: `_MIN_ZONE_BARS` (`BUG-077`) already exists to prevent.
    TRADING_MIN_ORDER_INTERVAL_SECONDS = "trading.min_order_interval_seconds"
    #: The one symbol `MarketTickEventHandler`'s live strategy path reacts
    #: to — every tick for any other symbol is ignored (`EPIC-021G` §6.x:
    #: mixing candles from two symbols through one `StrategyEngine`'s
    #: indicators would corrupt their state). Multi-symbol live trading is
    #: `EPIC-021I`'s screen, not this task's scope.
    TRADING_LIVE_SYMBOL = "trading.live_symbol"
    #: Which `StrategyRegistry` key the live tick path evaluates. Empty
    #: string (the default) means "no live strategy configured" —
    #: `MarketTickEventHandler` then stays the inert logger it always was.
    TRADING_LIVE_STRATEGY_KEY = "trading.live_strategy_key"
