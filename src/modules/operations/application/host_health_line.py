"""The health line, made from the snapshot just published (`EPIC-038D`).

The line is not a second measurement. The host publishes the snapshot (the
contributors answer, the probes have run) and this reads the same sections back,
so `status`, `health.json` and the log agree about the same moment. Every field
that cannot be read - a section that did not answer, a value of the wrong kind, a
number nobody measured - is `None`, which the line spells `na`: unknown is never
written as zero.

Where each field comes from:

| Field | Section | Key |
| :--- | :--- | :--- |
| `bots` | `bots` | `states` (running, paused, halted, recovering, error, starting, stopping; zeros included) |
| `tick_age_s` | `market_data` | `tick_age_s` (the freshest open feed) |
| `stream_down_s` | `trading` | `stream_down_s` |
| `skew_ms` | `trading` | `skew_ms` (what the host's probe last measured) |
| `rss_mb` | - | the process, measured by the caller |
"""

from __future__ import annotations

from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_line import (
    BotCount,
    HealthLine,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.health_snapshot import (
    HealthSnapshot,
    is_unavailable,
)

#: The states the line counts, in the order it writes them. The first four are the
#: line's original contract; `error`, `starting` and `stopping` follow them (`BUG-209`:
#: a bot in ERROR was invisible to the one line an operator reads). Order is the
#: contract's - a state is appended, never moved. The lifecycle's others (STOPPED,
#: DRAFT) are in `states` for `status`.
_LINE_STATES = (
    "running",
    "paused",
    "halted",
    "recovering",
    "error",
    "starting",
    "stopping",
)


def health_line_of(snapshot: HealthSnapshot, rss_mb: int | None) -> HealthLine:
    bots = _section(snapshot, "bots")
    market = _section(snapshot, "market_data")
    trading = _section(snapshot, "trading")
    uptime = int((snapshot.written_at - snapshot.started_at).total_seconds())
    return HealthLine(
        state=snapshot.host_state,
        up_s=max(0, uptime),
        bots=_bot_counts(bots),
        tick_age_s=_non_negative(market.get("tick_age_s")),
        stream_down_s=_non_negative(trading.get("stream_down_s")),
        skew_ms=_whole_number(trading.get("skew_ms")),
        rss_mb=rss_mb,
    )


def _section(snapshot: HealthSnapshot, name: str) -> Mapping[str, JsonValue]:
    section = snapshot.sections.get(name, {})
    return {} if is_unavailable(section) else section


def _bot_counts(section: Mapping[str, JsonValue]) -> tuple[BotCount, ...]:
    states = section.get("states")
    if not isinstance(states, Mapping):
        return ()
    held = {str(state).lower(): count for state, count in states.items()}
    return tuple(
        BotCount(state, _whole_number(held.get(state)) or 0) for state in _LINE_STATES
    )


def _whole_number(value: JsonValue | None) -> int | None:
    """An integer the section holds, `None` for anything else (a bool is not a count)."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _non_negative(value: JsonValue | None) -> int | None:
    number = _whole_number(value)
    return number if number is not None and number >= 0 else None
