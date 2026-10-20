"""What can be alerted about. The catalog (`alert_catalog.py`) gives each kind
its group, default severity and label."""

from __future__ import annotations

from enum import Enum


class AlertKind(Enum):
    """The fixed catalog of the design (§3). A kind is one line here and one in
    `alert_catalog.KIND_PROFILES`; the completeness test fails for the second."""

    BOT_HALTED = "bot_halted"
    BOT_ERROR = "bot_error"
    STOP_LOSS_HIT = "stop_loss_hit"
    TAKE_PROFIT_HIT = "take_profit_hit"
    PRICE_FEED_STALE = "price_feed_stale"
    USER_STREAM_DOWN = "user_stream_down"
    KEY_REJECTED = "key_rejected"
    STORAGE_FAILURE = "storage_failure"
    STOP_FAILED = "stop_failed"
    #: `EPIC-026L`: the account-level loss cap tripped and every bot is stopping; the owner must
    #: acknowledge before any bot starts again.
    ACCOUNT_LOSS_CAP_TRIPPED = "account_loss_cap_tripped"
    #: A bot waiting in AWAITING_RECOVERY has waited longer than it should expect to (`EPIC-042`).
    BOT_RECOVERY_STALLED = "bot_recovery_stalled"
    #: A bot resumed itself after a transient halt (`EPIC-042`); one alert per recovery.
    BOT_AUTO_RECOVERED = "bot_auto_recovered"
    RATE_LIMITED = "rate_limited"
    #: A Futures bot's position is inside the warning distance to liquidation (`EPIC-036B1`);
    #: the critical distance halts the bot and arrives as the halt.
    LIQUIDATION_RISK = "liquidation_risk"
    RANGE_EXIT = "range_exit"
    APP_FAILURE = "app_failure"
    #: One order of a bot's ladder filled whole (`BOT-189`, `PRO-015`); INFO, so silent by default.
    ORDER_FILLED = "order_filled"
    #: The one line that says the fill messages queued behind a slow channel were dropped (`BOT-189`).
    FILLS_SKIPPED = "fills_skipped"
    HEARTBEAT = "heartbeat"
    DAILY_SUMMARY = "daily_summary"
    CHANNEL_FAILING = "channel_failing"
    #: The owner's Send test (`alert test`, the Options page's button): proves a
    #: channel reaches them, and is never a condition.
    TEST = "test"
