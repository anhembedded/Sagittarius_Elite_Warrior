"""What each reason a bot records means for the owner's alerts (`EPIC-036B2`).

`BotAlertSource` turns a bot's entry into a state into one alert. The state alone says little: a
bot is HALTED for forty different reasons, and three of them are conditions the owner treats
differently (the exchange asked the app to slow down, rejected the key, or the bot's own state
file cannot be saved). This table is the one place that says, for **every** reason code of the
bots' grid (`GridReason.value`), how it reaches the owner:

  - `OWN_KIND` - the entry into one of its `states` raises `kind` instead of the generic
    `BOT_HALTED` / `BOT_ERROR` (`KEY_REJECTED`, `STORAGE_FAILURE`);
  - `STALLED` - the entry is the generic halt or the silent wait, and `kind` is raised in place of
    `BOT_RECOVERY_STALLED` when the wait outlasts the bot's own grace (`PRICE_FEED_STALE`: the
    bot's price feed was quiet past its limit; `RATE_LIMITED`: the bot waits out the exchange's
    pause, `EPIC-042F`). A rate limit that is a plain `HALTED` (a pause too long to wait, or a used-up
    budget) is the generic CRITICAL halt: a person must act, and the bot's detail says so;
  - `EXIT` - told by the stop path, not by the entry (`EXIT_ON_STOP`, the protective-stop event);
  - `GENERIC` - the state's generic kind: a halt is `BOT_HALTED`, an error `BOT_ERROR`;
  - `SILENT` - not a halt or a failure: a note the bot writes beside a state the owner caused or
    a state that raises nothing, so it never alerts on its own.

A reason code the table does not list (a kind of bot the module has not met) is `GENERIC`, so a new
bot kind needs no change here (`test_a_new_bot_kind_needs_no_change_in_alerting`).
`test_every_bot_reason_code_is_routed_on_purpose` fails when `GridReason` gains a code that is not a
row, so a new reason cannot silently produce the wrong alert or none.

**No text from outside.** An `OWN_KIND` or `STALLED` alert says its fixed sentence and the reason
code; it copies neither the bot's `reason_detail` nor the exchange's words. Those carry the
failure text of a request or of the disk (`key_rejected_detail`, `storage_failure`), and an alert
leaves the machine: nothing a failing call wrote can reach a channel through these kinds.

@par Extension cases
  · another reason that is its own condition - one row with `ReasonRoute.own(...)` and its kind in
    `alert_catalog.KIND_PROFILES`;
  · another reason that is only a note - one name in `_SILENT_REASONS`;
  · a reason whose wait should be told as its own kind - one `ReasonRoute.stalled(...)` row.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind


class Disposition(Enum):
    OWN_KIND = "own_kind"
    STALLED = "stalled"
    EXIT = "exit"
    GENERIC = "generic"
    SILENT = "silent"


@dataclass(frozen=True, slots=True)
class ReasonRoute:
    """How one reason code reaches the owner. Built through the constructors, so a route is valid
    on creation: an own-kind route names its kind, its states and its sentence."""

    disposition: Disposition
    kind: AlertKind | None = None
    #: `OWN_KIND` only: the lifecycle states (as `BotStatusEntry.state` spells them) whose entry,
    #: with this reason, raises `kind`.
    states: frozenset[str] = frozenset()
    #: What the owner reads, in place of the bot's detail.
    text: str = ""

    def __post_init__(self) -> None:
        carries_kind = self.disposition in (
            Disposition.OWN_KIND,
            Disposition.STALLED,
            Disposition.EXIT,
        )
        if carries_kind != (self.kind is not None):
            raise ValueError(
                f"A {self.disposition.name} route and its kind go together"
            )
        if self.disposition is Disposition.OWN_KIND and not (self.states and self.text):
            raise ValueError("An own-kind route needs its states and its sentence")
        if self.disposition is Disposition.STALLED and not self.text:
            raise ValueError("A stalled route needs its sentence")

    @classmethod
    def own(cls, kind: AlertKind, states: frozenset[str], text: str) -> ReasonRoute:
        return cls(Disposition.OWN_KIND, kind, states, text)

    @classmethod
    def stalled(cls, kind: AlertKind, text: str) -> ReasonRoute:
        return cls(Disposition.STALLED, kind, text=text)

    @classmethod
    def exit(cls, kind: AlertKind) -> ReasonRoute:
        return cls(Disposition.EXIT, kind)


GENERIC = ReasonRoute(Disposition.GENERIC)
SILENT = ReasonRoute(Disposition.SILENT)

#: A halt or an error whose cause the owner reads in the bot's own `Reason:` line.
_GENERIC_REASONS = (
    "start_refused",
    # The price entered a waiting bot's range and the plan was refused (`EPIC-044`, ADR 044 D5).
    "entry_refused",
    "level_keeps_ending",
    "order_rejected",
    "order_refused",
    "order_failed",
    "task_failed",
    "history_unavailable",
    "exit_slice_failed",
    "inventory_mismatch",
    "holding_below_inventory",
    "duplicate_level_order",
    "order_quantity_mismatch",
    "unknown_tagged_order",
    "lease_held",
    "switch_off",
    "start_cut_by_switch_off",
    # The venue's own USER_STREAM_DOWN (`StreamAlertSource`) is the message the owner reads about
    # the stream; each bot's halt for it stays its own CRITICAL fact.
    "user_stream_down",
    "proposal_price_moved",
    "symbol_not_trading",
    "symbol_delisted",
    "exchange_terms_changed",
    "settings_drift",
    # The critical distance halts the bot and the halt is the alert (`EPIC-036B1`, D2).
    "liquidation_risk",
    "foreign_fill",
    "position_unobservable",
    "position_mismatch",
    "protective_stop_failed",
    # A restart that found the bot starting: it is HALTED for the owner to resume.
    "start_interrupted",
)

#: Notes the bot writes beside a state the owner caused or one that raises nothing.
_SILENT_REASONS = (
    "user_stop",  # the owner pressed Stop
    "recovery_read",  # a restored bot's boot report, replaced by the full reconcile
    "restored_paused",  # a bot the owner paused came back paused
    "start_interrupted_cleared",  # the debt of an interrupted start was paid
    "counter_order_rejected",  # one rung stays empty and the ladder goes on; no state change
)

_HALT_OR_ERROR = frozenset({"HALTED", "ERROR"})

REASON_ROUTES: Mapping[str, ReasonRoute] = MappingProxyType(
    {
        **dict.fromkeys(_GENERIC_REASONS, GENERIC),
        **dict.fromkeys(_SILENT_REASONS, SILENT),
        "rate_limited": ReasonRoute.stalled(
            AlertKind.RATE_LIMITED,
            "The exchange asked the app to slow down and the bot is waiting out the pause with "
            "its ladder still resting on the exchange (no cancel is sent into a pause); it "
            "resumes by itself when the pause ends. Its stop loss and take profit are watched "
            "only while ticks arrive.",
        ),
        "key_rejected": ReasonRoute.own(
            AlertKind.KEY_REJECTED,
            _HALT_OR_ERROR,
            "The exchange rejected the API key (it was revoked, or the app's IP is off its "
            "list). The bot places nothing new. Orders it placed earlier may still rest on the "
            "exchange and this app cannot cancel them until a working key is added.",
        ),
        "storage_failure": ReasonRoute.own(
            AlertKind.STORAGE_FAILURE,
            frozenset({"PAUSED"}),
            "The bot's state file could not be saved three times in a row, so the bot paused: "
            "its orders rest on the exchange and nothing new is placed. Check the disk, then "
            "press Resume.",
        ),
        "price_feed_stale": ReasonRoute.stalled(
            AlertKind.PRICE_FEED_STALE,
            "The bot's price feed has been quiet past the bot's limit, so it cannot watch its "
            "stop loss or take profit: it stopped placing orders and took its ladder off the "
            "exchange. It resumes by itself when ticks return.",
        ),
        "stop_loss": ReasonRoute.exit(AlertKind.STOP_LOSS_HIT),
        "take_profit": ReasonRoute.exit(AlertKind.TAKE_PROFIT_HIT),
        "protective_stop_triggered": ReasonRoute.exit(AlertKind.STOP_LOSS_HIT),
        "range_exit": ReasonRoute.exit(AlertKind.RANGE_EXIT),
    }
)


def own_route_on_entry(state: str, reason: str) -> ReasonRoute | None:
    """The route that replaces the generic alert for the entry into `state` with `reason`, if the
    reason has one for this state."""
    route = REASON_ROUTES.get(reason)
    if (
        route is not None
        and route.disposition is Disposition.OWN_KIND
        and state in route.states
    ):
        return route
    return None


def stalled_route(reason: str) -> ReasonRoute | None:
    """The route that replaces `BOT_RECOVERY_STALLED` for a wait on `reason`, if it has one."""
    route = REASON_ROUTES.get(reason)
    if route is not None and route.disposition is Disposition.STALLED:
        return route
    return None
