"""Read a plan file strictly (`EPIC-038I`).

Every problem is collected, with where it is (`bots[2].venue`), so an operator fixes the
file once and not once per run. A field the plan does not define is refused, never
ignored: the commonest mistake that matters is a `api_key` pasted into it. **A refusal
never repeats the value it refused** - that value may be the secret.

The kind catalog supplies the known kinds, so a new kind needs no change here. Whether a
kind's *parameter values* are acceptable is judged when the bot starts, by the kind
itself (`IBotKind.validate`), exactly as for a bot made on the screen.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_document import (
    SCHEMA,
    BotPlanDocument,
    PlannedBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    DesiredState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_TOP_FIELDS = frozenset({"schema", "bots"})
_BOT_FIELDS = ("name", "kind", "venue", "symbol", "params", "desired_state")

#: Names that say "credential". Used only to explain a refusal and to refuse a parameter
#: named like one; the refusal of an unknown field does not depend on it.
_SECRET_NAME = re.compile(
    r"secret|passw|token|api[_-]?key|credential|private|signature|account[_-]?id",
    re.IGNORECASE,
)
_NO_SECRETS = "a plan holds no key, secret or account identifier"


class InvalidBotPlanError(ValueError):
    """The file is not a plan this build can apply; `problems` says every reason."""

    def __init__(self, problems: tuple[str, ...]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


def parse_plan(text: str, kinds: IBotKindCatalog) -> BotPlanDocument:
    """@raise InvalidBotPlanError The text is not a plan; the error lists every problem."""
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidBotPlanError(
            (f"the file is not valid JSON ({exc.msg}, line {exc.lineno})",)
        ) from None
    if not isinstance(raw, dict):
        raise InvalidBotPlanError(("the file must hold one JSON object",))
    problems: list[str] = []
    _check_top(raw, problems)
    entries = raw.get("bots")
    bots: list[PlannedBot] = []
    if isinstance(entries, list):
        known_kinds = tuple(kind.kind_id for kind in kinds.kinds())
        for index, entry in enumerate(entries):
            bot = _parse_bot(entry, f"bots[{index}]", known_kinds, problems)
            if bot is not None:
                bots.append(bot)
        _check_identities(bots, problems)
    if problems:
        raise InvalidBotPlanError(tuple(problems))
    return BotPlanDocument(tuple(bots))


def _check_top(raw: dict[str, Any], problems: list[str]) -> None:
    for name in raw:
        if name not in _TOP_FIELDS:
            problems.append(_unknown_field("", name))
    if "schema" not in raw:
        problems.append(f"the file has no schema; expected {SCHEMA!r}")
    elif raw["schema"] != SCHEMA:
        problems.append(
            f"schema {raw['schema']!r} is not one this build reads; expected {SCHEMA!r}"
            if isinstance(raw["schema"], str)
            else f"schema must be the text {SCHEMA!r}"
        )
    if not isinstance(raw.get("bots"), list):
        problems.append("bots must be a list (an empty plan is [])")


def _unknown_field(where: str, name: str) -> str:
    prefix = f"{where}." if where else ""
    hint = f"; {_NO_SECRETS}" if _SECRET_NAME.search(name) else ""
    return f"{prefix}{name}: unknown field{hint}"


def _parse_bot(
    entry: object, where: str, known_kinds: tuple[str, ...], problems: list[str]
) -> PlannedBot | None:
    if not isinstance(entry, dict):
        problems.append(f"{where}: each bot must be a JSON object")
        return None
    before = len(problems)
    for name in entry:
        if name not in _BOT_FIELDS:
            problems.append(_unknown_field(where, str(name)))
    for name in _BOT_FIELDS:
        if name not in entry:
            problems.append(f"{where}.{name}: missing")
    text = {
        name: _text(entry, name, where, problems)
        for name in ("name", "kind", "venue", "symbol", "desired_state")
    }
    params = _params(entry.get("params"), f"{where}.params", problems)
    kind = text["kind"]
    if kind is not None and kind not in known_kinds:
        problems.append(
            f"{where}.kind: {kind!r} is not a kind of bot here; known: {', '.join(known_kinds)}"
        )
    venue = _venue(text["venue"], f"{where}.venue", problems)
    desired = _desired(text["desired_state"], f"{where}.desired_state", problems)
    name, symbol = text["name"], text["symbol"]
    if (
        len(problems) > before  # a problem was recorded above
        or name is None
        or symbol is None
        or kind is None
        or venue is None
        or desired is None
        or params is None
    ):
        return None
    return PlannedBot(
        name=name.strip(),
        kind=kind,
        venue=venue,
        symbol=symbol.strip().upper(),
        desired_state=desired,
        params=params,
    )


def _text(
    entry: Mapping[str, Any], name: str, where: str, problems: list[str]
) -> str | None:
    if name not in entry:
        return None
    value = entry[name]
    if not isinstance(value, str) or not value.strip():
        problems.append(f"{where}.{name}: must be non-empty text")
        return None
    return value


def _params(raw: object, where: str, problems: list[str]) -> dict[str, str] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        problems.append(f"{where}: must be an object of text values")
        return None
    params: dict[str, str] = {}
    ok = True
    for name, value in raw.items():
        if not isinstance(name, str) or not name.strip():
            problems.append(f"{where}: a parameter needs a name")
            ok = False
        elif _SECRET_NAME.search(name):
            problems.append(
                f"{where}.{name}: a parameter named like a secret is refused; {_NO_SECRETS}"
            )
            ok = False
        elif not isinstance(value, str):
            problems.append(
                f"{where}.{name}: must be text (write the number in quotes, so no float touches a price)"
            )
            ok = False
        else:
            params[name] = value
    return params if ok else None


def _venue(value: str | None, where: str, problems: list[str]) -> TradingVenue | None:
    if value is None:
        return None
    allowed = {
        venue.value: venue
        for venue in TradingVenue
        if venue is not TradingVenue.DISABLED
    }
    venue = allowed.get(value)
    if venue is None:
        problems.append(
            f"{where}: {value!r} is not a venue; one of: {', '.join(allowed)}"
        )
    return venue


def _desired(value: str | None, where: str, problems: list[str]) -> DesiredState | None:
    if value is None:
        return None
    try:
        return DesiredState(value)
    except ValueError:
        problems.append(f"{where}: must be running or stopped")
        return None


def _check_identities(bots: list[PlannedBot], problems: list[str]) -> None:
    seen: set[tuple[str, TradingVenue]] = set()
    for bot in bots:
        if bot.identity in seen:
            problems.append(
                f"bot {bot.name!r} on {bot.venue.value} is listed twice; "
                "a bot is identified by its name and venue"
            )
        seen.add(bot.identity)
