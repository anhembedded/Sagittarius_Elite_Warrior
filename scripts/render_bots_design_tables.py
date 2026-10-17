"""Regenerate the tables of `Docs/MODULES/bots/` that are the code's own data (`EPIC-041E`).

    python3 scripts/render_bots_design_tables.py            # print every table
    python3 scripts/render_bots_design_tables.py --write    # rewrite the documents
    python3 scripts/render_bots_design_tables.py --check    # exit 1 when one differs

Four tables, each between a pair of markers in its document:

- `lifecycle`, `grid-level` and `protective-stop` in `state-machines.md`: every row of
  `BOT_LIFECYCLE_TRANSITIONS`, `GRID_LEVEL_TRANSITIONS` and `PROTECTIVE_STOP_TRANSITIONS`,
  in the order the code declares them;
- `timing` in `10-quality.md`: the constants that decide when a bot waits,
  retries, pauses or halts, read from the code each time.

A table is generated because it is data the code already holds (decision D4 of
2026-10-14, kept by D3 of 2026-10-16); `tests/unit/scripts/
test_render_bots_design_tables.py` fails when a committed table differs from a
fresh render. The diagrams beside them are drawn by hand.
"""

from __future__ import annotations

import dataclasses
import importlib
import re
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BOT_LIFECYCLE_TRANSITIONS,
    RECOVERABLE_STATES,
    BotLifecycleState,
    BotLifecycleTarget,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_level_fsm_matrix import (
    GRID_LEVEL_TRANSITIONS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.protective_stop_fsm_matrix import (
    PROTECTIVE_STOP_TRANSITIONS,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)

DESIGN = Path(__file__).resolve().parents[1] / "Docs" / "MODULES" / "bots"
STATE_MACHINES = DESIGN / "state-machines.md"
QUALITY = DESIGN / "10-quality.md"

_PACKAGE = "Sagittarius_Elite_Warrior"
_SECONDS_PER_HOUR = 3600

#: What a target that is not a state means, in the table's own words.
_TARGET_NOTES: Mapping[BotLifecycleTarget, str] = {
    BotLifecycleTarget.REMOVED: "removed (the file is deleted)",
    BotLifecycleTarget.PRIOR: "the state before the restart ("
    + " or ".join(
        f"`{state.value}`" for state in BotLifecycleState if state in RECOVERABLE_STATES
    )
    + ")",
}


def render_transitions[S: Enum, E: Enum, T: Enum](
    transitions: Mapping[tuple[S, E], T],
) -> str:
    """One row per declared transition, in declaration order; a self-loop says so."""
    lines = ["| From | Event | To |", "| :--- | :--- | :--- |"]
    for (state, event), target in transitions.items():
        if isinstance(target, BotLifecycleTarget):
            to = _TARGET_NOTES[target]
        elif target is state:
            to = f"`{target.value}` (stays)"
        else:
            to = f"`{target.value}`"
        lines.append(f"| `{state.value}` | `{event.value}` | {to} |")
    return "\n".join(lines) + "\n"


@dataclass(frozen=True, slots=True)
class Constant:
    """One named value in the code: a repository path and a dotted name in it."""

    path: str
    name: str

    def value(self) -> object:
        module = importlib.import_module(
            f"{_PACKAGE}." + self.path.removesuffix(".py").replace("/", ".")
        )
        owner, _, attribute = self.name.rpartition(".")
        if not owner:
            return getattr(module, attribute)
        holder = getattr(module, owner)
        if dataclasses.is_dataclass(holder):
            for field in dataclasses.fields(holder):
                if field.name == attribute:
                    return field.default
        return getattr(holder, attribute)


@dataclass(frozen=True, slots=True)
class TimingRow:
    """One row of the timing table: what it decides, the constants, and how they read."""

    what: str
    constants: tuple[Constant, ...]
    written: Callable[[tuple[object, ...]], str]


def seconds(value: object) -> str:
    """A duration as a reader says it: `250 ms`, `60 s`, `1 h`, `8 h`."""
    total = value.total_seconds() if isinstance(value, timedelta) else float(str(value))
    if total < 1:
        return f"{total * 1000:g} ms"
    if total >= _SECONDS_PER_HOUR and total % _SECONDS_PER_HOUR == 0:
        return f"{total / _SECONDS_PER_HOUR:g} h"
    return f"{total:g} s"


def _each(values: tuple[object, ...]) -> str:
    return "; ".join(seconds(value) for value in values)


def _caps(values: tuple[object, ...]) -> str:
    caps = values[0]
    if not isinstance(caps, OwnerBudgetCaps):
        raise TypeError(f"expected OwnerBudgetCaps, got {type(caps).__name__}")
    return (
        f"{caps.max_open_orders}; {seconds(caps.min_order_spacing)}; "
        f"{caps.max_orders_per_minute}"
    )


def _sleep(values: tuple[object, ...]) -> str:
    heartbeat, gap, attempts, spacing = values
    return f"{seconds(heartbeat)}; {seconds(gap)}; {attempts} × {seconds(spacing)}"


def _retries(values: tuple[object, ...]) -> str:
    delays = values[0]
    if not isinstance(delays, tuple):
        raise TypeError(f"expected a tuple of delays, got {type(delays).__name__}")
    return ", ".join(f"{seconds(delay).removesuffix(' s')}" for delay in delays) + " s"


def _rate_limit(values: tuple[object, ...]) -> str:
    margin, longest, resumes = values
    return f"{seconds(margin)}; {seconds(longest)}; {resumes}"


def _recheck(values: tuple[object, ...]) -> str:
    delay, count = values
    return f"{seconds(delay)}; {count} × that"


def _gate(values: tuple[object, ...]) -> str:
    ratio, spot, futures, ttl = values
    return f"{float(str(ratio)) * 100:g} % of {spot} on Spot, of {futures} on Futures; {seconds(ttl)}"


_BOTS = "src/modules/bots"
_TRADING = "src/modules/trading"

#: The rows, in the order a reader meets them: price, streams, stop, limits, money.
TIMING: tuple[TimingRow, ...] = (
    TimingRow(
        "Price is stale after; grace at start",
        (
            Constant(
                f"{_BOTS}/domain/grid/price_freshness.py", "PRICE_STALE_AFTER_SECONDS"
            ),
            Constant(
                f"{_BOTS}/domain/grid/price_freshness.py", "PRICE_START_GRACE_SECONDS"
            ),
        ),
        _each,
    ),
    TimingRow(
        "A reference price older than this is refused",
        (
            Constant(
                f"{_BOTS}/domain/grid/reference_price.py",
                "REFERENCE_PRICE_MAX_AGE_SECONDS",
            ),
        ),
        _each,
    ),
    TimingRow(
        "Every bot's feed is checked every",
        (
            Constant(
                f"{_BOTS}/application/services/watches/bot_price_watch.py",
                "CHECK_EVERY_SECONDS",
            ),
        ),
        _each,
    ),
    TimingRow(
        "Order pacer default caps: open orders, spacing, orders per minute",
        (
            Constant(
                f"{_TRADING}/contracts/owner_budget.py", "DEFAULT_OWNER_BUDGET_CAPS"
            ),
        ),
        _caps,
    ),
    TimingRow(
        "User stream down for this long halts; reconciled every; checked every",
        tuple(
            Constant(
                f"{_BOTS}/application/services/watches/user_stream_watch.py",
                f"UserStreamLimits.{name}",
            )
            for name in ("down_limit", "reconcile_every", "check_every")
        ),
        _each,
    ),
    TimingRow(
        "Sleep: heartbeat; a gap over this is a sleep; fresh-price attempts and spacing",
        tuple(
            Constant(
                f"{_BOTS}/application/services/watches/sleep_watch.py",
                f"SleepLimits.{name}",
            )
            for name in (
                "check_every",
                "gap_over",
                "price_attempts",
                "price_retry_every",
            )
        ),
        _sleep,
    ),
    TimingRow(
        "Wait before each automatic retry of a stop",
        (
            Constant(
                f"{_BOTS}/application/kinds/grid/stop/grid_stop_retry.py",
                "STOP_RETRY_DELAYS",
            ),
        ),
        _retries,
    ),
    TimingRow(
        "Rate-limit pause: margin, longest wait, most automatic resumes",
        tuple(
            Constant(f"{_BOTS}/domain/grid/rate_limit_pause.py", name)
            for name in (
                "AUTO_RESUME_MARGIN",
                "MAX_AUTO_RESUME_WAIT",
                "MAX_AUTO_RESUMES",
            )
        ),
        _rate_limit,
    ),
    TimingRow(
        "A position divergence is re-read after (nothing is read when the book already "
        "agrees with the stream's last figure, `BUG-220`); a run of reports may keep that "
        "one re-read waiting at most",
        (
            Constant(
                f"{_BOTS}/domain/grid/grid_thresholds.py",
                "FuturesGridThresholds.position_recheck_delay",
            ),
            Constant(
                f"{_BOTS}/application/kinds/grid/watch/grid_risk_watch.py",
                "MAX_RECHECK_DELAYS",
            ),
        ),
        _recheck,
    ),
    TimingRow(
        "The request gate closes at this share of the minute's weight; "
        "a One-way position mode is kept",
        (
            Constant(
                f"{_TRADING}/adapters/binance/exchange_call_policy.py",
                "SOFT_WEIGHT_RATIO",
            ),
            Constant(
                f"{_TRADING}/adapters/binance/exchange_call_policy.py",
                "SPOT_WEIGHT_LIMIT",
            ),
            Constant(
                f"{_TRADING}/adapters/binance/venue_sessions.py", "FUTURES_WEIGHT_LIMIT"
            ),
            Constant(
                f"{_TRADING}/adapters/binance/position_mode_memory.py", "TTL_SECONDS"
            ),
        ),
        _gate,
    ),
    TimingRow(
        "Futures funding interval assumed",
        (Constant(f"{_BOTS}/domain/bot_kind_inputs.py", "FUNDING_INTERVAL"),),
        _each,
    ),
)


def _cited(constants: tuple[Constant, ...]) -> str:
    """The `Where` cell: one `path` → `name`, ... per file, in the guard's form."""
    by_path: dict[str, list[str]] = {}
    for constant in constants:
        by_path.setdefault(constant.path, []).append(f"`{constant.name}`")
    return " · ".join(
        f"`{path}` → {', '.join(names)}" for path, names in by_path.items()
    )


def render_timing(rows: tuple[TimingRow, ...] = TIMING) -> str:
    lines = ["| What | Value | Where |", "| :--- | :--- | :--- |"]
    for row in rows:
        value = row.written(tuple(constant.value() for constant in row.constants))
        lines.append(f"| {row.what} | {value} | {_cited(row.constants)} |")
    return "\n".join(lines) + "\n"


#: (document, block name) -> the block's current rendering.
def blocks() -> dict[tuple[Path, str], str]:
    return {
        (STATE_MACHINES, "lifecycle"): render_transitions(BOT_LIFECYCLE_TRANSITIONS),
        (STATE_MACHINES, "grid-level"): render_transitions(GRID_LEVEL_TRANSITIONS),
        (STATE_MACHINES, "protective-stop"): render_transitions(
            PROTECTIVE_STOP_TRANSITIONS
        ),
        (QUALITY, "timing"): render_timing(),
    }


def _markers(name: str) -> tuple[str, str]:
    return (
        f"<!-- generated by scripts/render_bots_design_tables.py: {name} -->\n",
        f"<!-- end generated: {name} -->",
    )


def committed_block(text: str, name: str) -> str | None:
    """The text between `name`'s markers, or None when the document has no such block."""
    begin, end = _markers(name)
    match = re.search(re.escape(begin) + r"(.*?)" + re.escape(end), text, re.DOTALL)
    return match.group(1) if match else None


def replace_block(text: str, name: str, rendered: str) -> str:
    begin, end = _markers(name)
    if committed_block(text, name) is None:
        raise ValueError(f"no `{name}` markers in the document")
    return re.sub(
        re.escape(begin) + r".*?" + re.escape(end),
        lambda _match: begin + rendered + end,
        text,
        count=1,
        flags=re.DOTALL,
    )


def main(argv: list[str]) -> int:
    rendered = blocks()
    if "--write" in argv:
        for (document, name), table in rendered.items():
            text = document.read_text(encoding="utf-8")
            document.write_text(replace_block(text, name, table), encoding="utf-8")
            sys.stdout.write(f"wrote {name} in {document.name}\n")
        return 0
    if "--check" in argv:
        stale = [
            f"{document.name}: {name}"
            for (document, name), table in rendered.items()
            if committed_block(document.read_text(encoding="utf-8"), name) != table
        ]
        for entry in stale:
            sys.stderr.write(f"stale table: {entry}\n")
        return 1 if stale else 0
    for (document, name), table in rendered.items():
        sys.stdout.write(f"## {document.name}: {name}\n\n{table}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
