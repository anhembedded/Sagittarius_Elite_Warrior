"""The health line: one log record an operator greps and a monitor parses
(`EPIC-038G`, `DESIGN_2026-10-09_headless_operation.md` §6).

    [health] state=SERVING up=3600s bots=running:3,paused:1,halted:0 tick_age_s=2 stream_age_s=5 skew_ms=-120 rss_mb=310

**The contract** (a field is added at the end, never renamed or reordered; the
parser ignores keys it does not know, so an older monitor survives a newer host):

| Key | Value | Unknown |
| :--- | :--- | :--- |
| `state` | a `HostState` name | — |
| `up` | whole seconds since boot, with an `s` suffix | — |
| `bots` | `state:count` pairs, comma-separated, in the host's order; `none` when it holds no bot | — |
| `tick_age_s`, `stream_age_s` | whole seconds since the last tick / user-stream message | `na` |
| `skew_ms` | signed milliseconds, local clock minus the exchange's | `na` |
| `rss_mb` | resident memory in whole megabytes | `na` |

**Level.** Always INFO, through `log_health_line`, the only emitter. A stale feed
is a number on this line, not a WARNING: the escalation is made by the alert
source, and a health line that logged WARNING would trip the CI run-log scan
(`- (WARNING|ERROR|CRITICAL) -`, `ci-rule.md` §3) on every healthy-but-quiet run.
The record keeps the Engine's fixed field order, which that scan depends on
(`logging-rule.md` §8): this module only writes the message.

**Secrets.** The line holds counts, ages and a state name. It takes no free text,
so a credential cannot reach it; `HealthLine` refuses any bot state that is not
`[a-z_]+`.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)

HEALTH_TAG = "[health]"
_UNKNOWN = "na"
_NO_BOTS = "none"
_BOT_STATE = re.compile(r"[a-z_]+")
#: ASCII digits only (`\d` also matches Arabic-Indic ones) and at most 18, so
#: `int()` never meets a value Python refuses to convert.
_INTEGER = re.compile(r"-?[0-9]{1,18}")
#: A health record: the tag opens the message, and its first key is `state`.
#: A foreign record that merely mentions `[health]` does not match.
_HEALTH_RECORD = re.compile(r"(?:^|\bINFO - )\[health\] state=")


class HealthLineError(ValueError):
    """A health line that cannot be built, or text that is not one."""


@dataclass(frozen=True, slots=True)
class BotCount:
    """How many bots are in one state, as the host counts them."""

    state: str
    count: int

    def __post_init__(self) -> None:
        if not _BOT_STATE.fullmatch(self.state):
            raise HealthLineError(f"bot state {self.state!r} is not [a-z_]+")
        if self.count < 0:
            raise HealthLineError(f"bot count for {self.state!r} is negative")


@dataclass(frozen=True, slots=True)
class HealthLine:
    """The facts one health line carries; `None` is "could not be measured"."""

    state: HostState
    up_s: int
    bots: tuple[BotCount, ...]
    tick_age_s: int | None
    stream_age_s: int | None
    skew_ms: int | None
    rss_mb: int | None

    def __post_init__(self) -> None:
        non_negative = {
            "up_s": self.up_s,
            "tick_age_s": self.tick_age_s,
            "stream_age_s": self.stream_age_s,
            "rss_mb": self.rss_mb,
        }
        for name, value in non_negative.items():
            if value is not None and value < 0:
                raise HealthLineError(f"{name} is negative: {value}")
        states = [bot.state for bot in self.bots]
        if len(set(states)) != len(states):
            raise HealthLineError(f"a bot state is listed twice: {states}")


def format_health_line(health: HealthLine) -> str:
    """The one place the line's text is written."""
    bots = ",".join(f"{bot.state}:{bot.count}" for bot in health.bots) or _NO_BOTS
    fields = (
        ("state", health.state.value),
        ("up", f"{health.up_s}s"),
        ("bots", bots),
        ("tick_age_s", _number(health.tick_age_s)),
        ("stream_age_s", _number(health.stream_age_s)),
        ("skew_ms", _number(health.skew_ms)),
        ("rss_mb", _number(health.rss_mb)),
    )
    return " ".join([HEALTH_TAG, *(f"{key}={value}" for key, value in fields)])


def log_health_line(logger: logging.Logger, health: HealthLine) -> None:
    """Emit `health` at INFO. The level is fixed here so no caller can raise it."""
    logger.info(format_health_line(health))


def parse_health_line(text: str) -> HealthLine:
    """The `HealthLine` in `text`, which may be a whole log record.

    Raises `HealthLineError` when the tag is missing, a required key is absent
    or repeated, or a value is malformed. Keys it does not know are ignored.
    """
    start = text.find(HEALTH_TAG)
    if start < 0:
        raise HealthLineError(f"no {HEALTH_TAG} tag in {text!r}")
    values = _key_values(text[start + len(HEALTH_TAG) :].split())
    try:
        return HealthLine(
            state=_state(values["state"]),
            up_s=_seconds(values["up"]),
            bots=_bots(values["bots"]),
            tick_age_s=_optional_int(values["tick_age_s"]),
            stream_age_s=_optional_int(values["stream_age_s"]),
            skew_ms=_optional_int(values["skew_ms"]),
            rss_mb=_optional_int(values["rss_mb"]),
        )
    except KeyError as missing:
        raise HealthLineError(f"health line lacks {missing} in {text!r}") from missing


def health_lines_in(log_text: str) -> tuple[HealthLine, ...]:
    """Every health line in a log, in order; other records are skipped.

    A record that opens like a health line but is malformed still raises: that
    is a format bug, not noise."""
    return tuple(
        parse_health_line(line)
        for line in log_text.splitlines()
        if _HEALTH_RECORD.search(line)
    )


def _number(value: int | None) -> str:
    return _UNKNOWN if value is None else str(value)


def _key_values(tokens: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for token in tokens:
        key, separator, value = token.partition("=")
        if not separator:
            raise HealthLineError(f"{token!r} is not key=value")
        if key in values:
            raise HealthLineError(f"{key!r} appears twice")
        values[key] = value
    return values


def _state(raw: str) -> HostState:
    try:
        return HostState(raw)
    except ValueError as unknown:
        raise HealthLineError(f"unknown host state {raw!r}") from unknown


def _seconds(raw: str) -> int:
    if not raw.endswith("s"):
        raise HealthLineError(f"{raw!r} lacks the s suffix")
    return _integer(raw[:-1])


def _optional_int(raw: str) -> int | None:
    return None if raw == _UNKNOWN else _integer(raw)


def _integer(raw: str) -> int:
    if not _INTEGER.fullmatch(raw):
        raise HealthLineError(f"{raw!r} is not a whole number")
    return int(raw)


def _bots(raw: str) -> tuple[BotCount, ...]:
    if raw == _NO_BOTS:
        return ()
    counts: list[BotCount] = []
    for pair in raw.split(","):
        state, separator, count = pair.partition(":")
        if not separator:
            raise HealthLineError(f"{pair!r} is not state:count")
        counts.append(BotCount(state, _integer(count)))
    return tuple(counts)
