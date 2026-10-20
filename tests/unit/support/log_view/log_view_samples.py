"""Real shapes of log lines, copied from `Docs/OPERATIONS/LOGGING.md` §4, §6 and the call sites."""

from __future__ import annotations

EXIT_SLICE = (
    "2026-10-20 02:00:01,123 - App.Bots.GridExit - INFO - "
    "Bot uie03d: exit slice 2 of 5 -> SELL BTCUSDT"
)
HEALTH = (
    "2026-10-20 02:00:02,000 - App.Operations.Health - INFO - "
    "[health] state=SERVING up=3600s "
    "bots=running:3,paused:1,halted:0,recovering:0,error:0,starting:0,stopping:0,"
    "awaiting_recovery:0 tick_age_s=2 stream_down_s=5 skew_ms=-120 rss_mb=310"
)
BOOT_RECOVERY = (
    "2026-10-20 02:00:03,500 - App.Bots.Recovery - WARNING - "
    "Bot uie03d: [boot-recovery] not read: no snapshot"
)
TRAILING_TAG = (
    "2026-10-20 02:00:03,900 - App.Bots.Parking - WARNING - "
    "Bot uie03d: halted (stop loss); closing the position [halt-closes-position]"
)
REDUCE_ONLY = (
    "2026-10-20 02:00:04,000 - App.Trading.Orders - WARNING - "
    "[reduce-only-refused] Reduce-only order refused on futures_testnet: "
    "BTCUSDT SELL MARKET qty=0.001 price=None trigger=None reduceOnly=True "
    "closePosition=False positionSide=BOTH; account position mode=one-way; "
    "position on the symbol (exchange)=0.0; owner book position=no owner; "
    "exchange said: ReduceOnly Order is rejected"
)
UNTAGGED = "2026-10-20 02:00:05,000 - App.Shell.Host - INFO - Waiting for the exchange"
ERROR_HEAD = (
    "2026-10-20 02:00:06,500 - App.Shell - ERROR - [cli-exit] unexpected failure"
)
TRACEBACK = (
    "Traceback (most recent call last):",
    '  File "x.py", line 1, in <module>',
    "ValueError: boom",
)
DEBUG_LINE = "2026-10-20 01:00:00,001 - App.Chart - DEBUG - [chart-env] ChartCard(a): x"
NOT_A_RECORD = "-- Journal begins at Mon 2026-10-19 --"
