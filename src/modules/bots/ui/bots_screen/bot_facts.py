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

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_earnings import (
    NO_VALUE,
    RunEarnings,
    cycles_text,
    grid_profit_text,
    total_pnl_text,
    unrealised_text,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    venue_profile_of,
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
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    sign_tone,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    signed_key,
    write_value,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind


def _price(value: Decimal | None) -> str:
    return write_value(ColumnKind.PRICE, value)


def _quantity(value: Decimal) -> str:
    return write_value(ColumnKind.QUANTITY, value)


def _write_money(value: Decimal) -> str:
    """A figure that says how the run is doing: an arrow, a sign, and the tone's colour beside it."""
    return write_value(ColumnKind.MONEY, float(value), signed_key("pnl"))


def _money(value: Decimal | None) -> str:
    return NO_VALUE if value is None else _write_money(value)


#: What a RECOVERING bot says first: it waits, and Resume is the action that continues it.
RECOVERING_WAITS_FOR_RESUME = (
    "waiting for you: press Resume to open the order session and continue"
)

#: `BUG-206` - a bot the owner had paused comes back to PAUSED, so one Resume only
#: reconciles it; saying "continue" there promised a run it does not give.
RECOVERING_FROM_PAUSED_WAITS_FOR_RESUME = (
    "waiting for you: it was Paused before the restart. Resume opens the order "
    "session and books what filled, then returns it to Paused; press Resume again to run"
)

#: States in which the run's clock is still going.
_RUNNING_CLOCK = frozenset(
    {
        BotLifecycleState.STARTING,
        BotLifecycleState.RUNNING,
        BotLifecycleState.PAUSED,
        BotLifecycleState.RECOVERING,
        BotLifecycleState.HALTED,
        BotLifecycleState.AWAITING_RECOVERY,
        BotLifecycleState.AWAITING_RANGE,
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
    #: `BUG-196` — base earlier runs left that this run does not trade.
    earlier_runs: str = NO_VALUE
    #: `EPIC-039J` — what trading cost, beside the profit and not inside it: the
    #: commissions the run's fills paid, and the funding the position settled (earned
    #: positive). Shown only on a venue with funding, so the Spot figures are unchanged.
    commissions: str = NO_VALUE
    funding: str = NO_VALUE
    shows_costs: bool = False
    #: `BOT-192` - completed buy/sell cycles, beside the profit they booked.
    cycles: str = NO_VALUE
    #: `BOT-209` - the state alone ("Halted"), and what the run said about it, kept apart so the
    #: state reads at a glance and the note stands in the status banner. `state` is both, as ever.
    state_word: str = ""
    note: str = ""
    #: `EPIC-043C` - what each earnings figure means, by its row key: a profit, a loss.
    tones: Mapping[str, Tone] = field(default_factory=dict)


def _tones(bot: BotSnapshot) -> dict[str, Tone]:
    earnings = RunEarnings.of(bot.progress)
    hodl = bot.progress.pnl.hodl if bot.progress and bot.progress.pnl else None
    return {
        "grid_profit": sign_tone(earnings.grid_profit if earnings else None),
        "total_pnl": sign_tone(earnings.total_pnl if earnings else None),
        "unrealised": sign_tone(earnings.unrealised if earnings else None),
        "hodl": sign_tone(hodl),
    }


def bot_facts(bot: BotSnapshot, now: datetime) -> BotFacts:
    progress = bot.progress
    capital_key = KIND_CAPITAL_KEYS.get(bot.kind)
    capital = bot.config.get(capital_key, "") if capital_key else ""
    return BotFacts(
        state=_state_line(bot),
        state_word=state_text(bot.state),
        note=_state_note(bot),
        venue=bot.venue.display_name,
        symbol=bot.symbol,
        capital=capital or NO_VALUE,
        grid_profit=grid_profit_text(RunEarnings.of(progress), _write_money),
        unrealised=_unrealised(bot),
        inventory=_inventory(bot),
        running_time=_running_time(bot, now),
        total_pnl=_total(bot),
        hodl=_money(progress.pnl.hodl if progress and progress.pnl else None),
        earlier_runs=_earlier_runs(bot),
        commissions=_cost(bot, "commissions"),
        funding=_cost(bot, "funding"),
        shows_costs=_has_funding(bot),
        cycles=cycles_text(RunEarnings.of(progress)),
        tones=_tones(bot),
    )


def _state_line(bot: BotSnapshot) -> str:
    detail = _state_note(bot)
    if not detail:
        return state_text(bot.state)
    return f"{state_text(bot.state)} — {detail}"


def _state_note(bot: BotSnapshot) -> str:
    """What the run said about the state: the reason it halted or failed, or what a recovering
    bot waits for."""
    progress = bot.progress
    detail = progress.reason_detail if progress is not None else ""
    if bot.state is BotLifecycleState.RECOVERING:
        # `BUG-204` - not "recovery finished": the bot is waiting for the owner.
        waits = (
            RECOVERING_FROM_PAUSED_WAITS_FOR_RESUME
            if bot.recovering_from is BotLifecycleState.PAUSED
            else RECOVERING_WAITS_FOR_RESUME
        )
        detail = f"{waits}. {detail}".rstrip()
    return detail


def _unrealised(bot: BotSnapshot) -> str:
    return unrealised_text(RunEarnings.of(bot.progress), _write_money, _price)


def _total(bot: BotSnapshot) -> str:
    return total_pnl_text(RunEarnings.of(bot.progress), _write_money)


def _has_funding(bot: BotSnapshot) -> bool:
    profile = venue_profile_of(bot.venue)
    return profile is not None and profile.has_funding


def _cost(bot: BotSnapshot, name: str) -> str:
    """A cost of the run as the formatter writes a quantity: a fee or a funding payment is
    often far below a cent, and money's two decimals would print it as nothing."""
    progress = bot.progress
    if progress is None or progress.pnl is None:
        return NO_VALUE
    return _quantity(getattr(progress.pnl, name))


def _inventory(bot: BotSnapshot) -> str:
    progress = bot.progress
    if progress is None or progress.inventory <= 0:
        return NO_VALUE
    cost = progress.average_cost
    return f"{_quantity(progress.inventory)} at an average {_price(cost)}"


def _earlier_runs(bot: BotSnapshot) -> str:
    progress = bot.progress
    if progress is None or progress.earlier_runs_base <= 0:
        return NO_VALUE
    cost = _money(progress.earlier_runs_cost)
    return (
        f"{_quantity(progress.earlier_runs_base)} (cost {cost}), not traded by this run"
    )


def _running_time(bot: BotSnapshot, now: datetime) -> timedelta | None:
    started = bot.run_started_at
    if started is None or bot.state not in _RUNNING_CLOCK:
        return None
    return max(now - started, timedelta(0))
