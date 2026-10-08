"""`EPIC-029F` — the figures the detail panel shows for one bot, as text.

Each number is written by the application's formatter (`EPIC-033N`), so a
price here reads as it does in the orders table beside it.

Pure, so each figure is tested without a widget. The earnings come from the run
itself (`EPIC-035M`): the **total** first, then grid profit as one part of it, the
unrealised at the price **the bot itself heard** (saved with its state, not a
chart's), and the HODL benchmark. A figure with no price behind it says so
rather than showing a stale or guessed one.
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
    state_text,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.kind_panels import (
    KIND_CAPITAL_KEYS,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    write_value,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind

#: A figure this bot does not have yet: no fill, no inventory, no run.
NO_VALUE = "—"


def _price(value: Decimal | None) -> str:
    return write_value(ColumnKind.PRICE, value)


def _quantity(value: Decimal) -> str:
    return write_value(ColumnKind.QUANTITY, value)


def _money(value: Decimal | None) -> str:
    return NO_VALUE if value is None else write_value(ColumnKind.MONEY, float(value))


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
    #: How long the run has gone, written by the formatter as a duration;
    #: `None` while the bot is not running.
    running_time: timedelta | None
    #: Realised plus unrealised, the first earnings figure (`EPIC-035M`).
    total_pnl: str = NO_VALUE
    #: What the same capital would have gained held since the run began.
    hodl: str = NO_VALUE


def bot_facts(bot: BotSnapshot, now: datetime) -> BotFacts:
    progress = bot.progress
    capital_key = KIND_CAPITAL_KEYS.get(bot.kind)
    capital = bot.config.get(capital_key, "") if capital_key else ""
    return BotFacts(
        state=_state_line(bot),
        venue=bot.venue.display_name,
        symbol=bot.symbol,
        capital=capital or NO_VALUE,
        grid_profit=_money(progress.realised_profit if progress else None),
        unrealised=_unrealised(bot),
        inventory=_inventory(bot),
        running_time=_running_time(bot, now),
        total_pnl=_total(bot),
        hodl=_money(progress.pnl.hodl if progress and progress.pnl else None),
    )


def _state_line(bot: BotSnapshot) -> str:
    progress = bot.progress
    if progress is None or not progress.reason_detail:
        return state_text(bot.state)
    return f"{state_text(bot.state)} — {progress.reason_detail}"


def _unrealised(bot: BotSnapshot) -> str:
    progress = bot.progress
    if progress is None or progress.inventory <= 0 or progress.average_cost is None:
        return NO_VALUE
    pnl = progress.pnl
    if pnl is None or pnl.unrealised is None or progress.mark_price is None:
        return "no price yet"
    return f"{_money(pnl.unrealised)} at {_price(progress.mark_price)}"


def _total(bot: BotSnapshot) -> str:
    progress = bot.progress
    if progress is None or progress.pnl is None:
        return NO_VALUE
    pnl = progress.pnl
    if pnl.total is None:
        return "no price yet"
    note = (
        f" ({pnl.unpriced_fees} fees could not be priced)"
        if pnl.unpriced_fees > 1
        else " (1 fee could not be priced)"
        if pnl.unpriced_fees
        else ""
    )
    return f"{_money(pnl.total)}{note}"


def _inventory(bot: BotSnapshot) -> str:
    progress = bot.progress
    if progress is None or progress.inventory <= 0:
        return NO_VALUE
    cost = progress.average_cost
    return f"{_quantity(progress.inventory)} at an average {_price(cost)}"


def _running_time(bot: BotSnapshot, now: datetime) -> timedelta | None:
    started = bot.run_started_at
    if started is None or bot.state not in _RUNNING_CLOCK:
        return None
    return max(now - started, timedelta(0))
