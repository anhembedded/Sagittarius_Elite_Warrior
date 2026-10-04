"""`EPIC-029F` — the figures the detail panel shows for one bot, as text.

Pure, so each figure is tested without a widget. Unrealised PnL needs a
price: the latest the screen has (the planner's read, then each live candle);
without one it says so rather than showing a stale or guessed figure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_table_models import (
    NO_VALUE,
    amount_text,
    signed_text,
    state_text,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.kind_panels import (
    KIND_CAPITAL_KEYS,
)

#: States in which the run's clock is still going.
_RUNNING_CLOCK = frozenset(
    {
        BotLifecycleState.STARTING,
        BotLifecycleState.RUNNING,
        BotLifecycleState.PAUSED,
        BotLifecycleState.RECOVERING,
        BotLifecycleState.HALTED,
    }
)


@dataclass(frozen=True, slots=True)
class BotFacts:
    state: str
    venue: str
    symbol: str
    capital: str
    grid_profit: str
    unrealised: str
    inventory: str
    running_time: str


def bot_facts(bot: BotSnapshot, last_price: Decimal | None, now: datetime) -> BotFacts:
    progress = bot.progress
    capital_key = KIND_CAPITAL_KEYS.get(bot.kind)
    capital = bot.config.get(capital_key, "") if capital_key else ""
    return BotFacts(
        state=_state_line(bot),
        venue=bot.venue.value,
        symbol=bot.symbol,
        capital=capital or NO_VALUE,
        grid_profit=signed_text(progress.realised_profit if progress else None),
        unrealised=_unrealised(bot, last_price),
        inventory=_inventory(bot),
        running_time=_running_time(bot, now),
    )


def _state_line(bot: BotSnapshot) -> str:
    progress = bot.progress
    if progress is None or not progress.reason_detail:
        return state_text(bot.state)
    return f"{state_text(bot.state)} — {progress.reason_detail}"


def _unrealised(bot: BotSnapshot, last_price: Decimal | None) -> str:
    progress = bot.progress
    if progress is None or progress.inventory <= 0 or progress.average_cost is None:
        return NO_VALUE
    if last_price is None:
        return "no price yet"
    pnl = progress.inventory * (last_price - progress.average_cost)
    return f"{signed_text(pnl)} at {amount_text(last_price)}"


def _inventory(bot: BotSnapshot) -> str:
    progress = bot.progress
    if progress is None or progress.inventory <= 0:
        return NO_VALUE
    cost = progress.average_cost
    return f"{amount_text(progress.inventory)} at an average {amount_text(cost)}"


def _running_time(bot: BotSnapshot, now: datetime) -> str:
    started = bot.run_started_at
    if started is None or bot.state not in _RUNNING_CLOCK:
        return NO_VALUE
    elapsed = max(now - started, timedelta(0))
    days, remainder = divmod(int(elapsed.total_seconds()), 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes = remainder // 60
    return (
        f"{days}d {hours:02d}h {minutes:02d}m" if days else f"{hours}h {minutes:02d}m"
    )
