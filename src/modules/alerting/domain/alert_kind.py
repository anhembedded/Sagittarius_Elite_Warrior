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
    RATE_LIMITED = "rate_limited"
    RANGE_EXIT = "range_exit"
    APP_FAILURE = "app_failure"
    HEARTBEAT = "heartbeat"
    DAILY_SUMMARY = "daily_summary"
    CHANNEL_FAILING = "channel_failing"
