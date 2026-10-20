"""`EPIC-040D` — the words the Backtest workbench says, written once.

The state words are the Grid page's (`EPIC-029D`, pinned by `EPIC-040A`), so a person who ran a Grid
backtest before reads the same sentences; the new ones are the simulation's own."""

from __future__ import annotations

NO_BOT = "Select a bot to backtest its parameters."
NO_TERMS = "The market numbers for this symbol are still being read."
NO_BRACKETS = "The leverage brackets for this symbol are still being read."
BANNER = "Simulation only. Not checked against your account and never sent to the bot."
DONE = "Backtest done."
RUN_FAILED = "The run failed."
CANCELLED = "Backtest cancelled; the last result stays."
SYNC_STOPPED = "Sync stopped; what it already stored stays."
ANSWER_FIRST = "Answer the question above first."
PERIOD_ORDER = "The period must end after it starts."
DISCARD_QUESTION = (
    "Another bot is selected. Replace your edits with its saved plan, or keep them?"
)
#: What failed, by the action's label: the headline the user reads (`BOT-169`).
FAILED_HEADLINES = {
    "backtest": "The backtest could not run. Check the period and try again.",
    "sync": "The candle sync could not finish. Check the connection and try again.",
}


def running(symbol: str, interval: str) -> str:
    return f"Backtesting {symbol} on {interval}…"


def syncing(symbol: str, interval: str) -> str:
    return f"Syncing {symbol} {interval} candles and 1-second klines for the period…"


def partly_stored(missing: int) -> str:
    return (
        f"Backtest done on what is stored: {missing} candles of the period are not "
        "stored. Sync candles fetches them, then runs again."
    )


def refused_plan(reason: str) -> str:
    return f"The parameters are refused, so there is nothing to simulate: {reason}"


def fees_line(maker: str, taker: str) -> str:
    """Whose fees a run charges: the symbol's terms as the planner read them, the account's tier
    included, not rates of the sandbox's own."""
    return (
        f"A run charges your account's fees as read now: maker {maker}, taker {taker}."
    )
