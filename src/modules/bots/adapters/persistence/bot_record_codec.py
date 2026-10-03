"""`EPIC-029B` — one bot's file, version 1 (ADR D4).

```
{
  "schema_version": 1,
  "definition": {"bot_id", "name", "kind", "venue", "symbol", "config", "created_at"},
  "lifecycle":  {"state", "run_started_at", "recovering_from"},
  "runtime":    {...}   # the kind's, opaque here
}
```

Decoding is strict: a missing key, a wrong type or an unknown enum value raises
`BotRecordError` with the reason, and the store refuses the file by name. A
version this code does not know is refused before anything else is read, so a
newer app's file is never half-understood by an older one.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    JsonValue,
    StoredBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

SCHEMA_VERSION = 1


class BotRecordError(ValueError):
    """The record is not a version-1 bot file; the message says why."""


def encode(stored: StoredBot) -> dict[str, JsonValue]:
    bot = stored.bot
    definition = bot.definition
    lifecycle = bot.lifecycle
    return {
        "schema_version": SCHEMA_VERSION,
        "definition": {
            "bot_id": bot.bot_id.value,
            "name": definition.name,
            "kind": definition.kind,
            "venue": definition.venue.value,
            "symbol": definition.symbol,
            "config": dict(definition.config),
            "created_at": bot.created_at.isoformat(),
        },
        "lifecycle": {
            "state": lifecycle.state.value,
            "run_started_at": _iso_or_none(lifecycle.run_started_at),
            "recovering_from": (
                lifecycle.recovering_from.value if lifecycle.recovering_from else None
            ),
        },
        "runtime": dict(stored.runtime),
    }


def decode(record: JsonValue) -> StoredBot:
    """@raise BotRecordError The record is not a readable version-1 bot."""
    root = _object(record, "the file")
    version = root.get("schema_version")
    if version != SCHEMA_VERSION:
        raise BotRecordError(f"unknown schema_version {version!r}")
    definition = _object(root.get("definition"), "definition")
    lifecycle = _object(root.get("lifecycle"), "lifecycle")
    try:
        bot = Bot(
            BotId(_text(definition, "bot_id")),
            _definition(definition),
            _lifecycle(lifecycle),
            datetime.fromisoformat(_text(definition, "created_at")),
        )
    except ValueError as exc:
        raise BotRecordError(str(exc)) from exc
    return StoredBot(bot, _object(root.get("runtime", {}), "runtime"))


def _definition(data: Mapping[str, JsonValue]) -> BotDefinition:
    config = _object(data.get("config"), "definition.config")
    if not all(isinstance(value, str) for value in config.values()):
        raise BotRecordError("definition.config values must be strings")
    return BotDefinition(
        name=_text(data, "name"),
        kind=_text(data, "kind"),
        venue=TradingVenue(_text(data, "venue")),
        symbol=_text(data, "symbol"),
        config={key: str(value) for key, value in config.items()},
    )


def _lifecycle(data: Mapping[str, JsonValue]) -> BotLifecycle:
    run_started_at = _optional_text(data, "run_started_at")
    recovering_from = _optional_text(data, "recovering_from")
    return BotLifecycle(
        state=BotLifecycleState(_text(data, "state")),
        run_started_at=(
            datetime.fromisoformat(run_started_at) if run_started_at else None
        ),
        recovering_from=(
            BotLifecycleState(recovering_from) if recovering_from else None
        ),
    )


def _object(value: JsonValue, where: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise BotRecordError(f"{where} is not an object")
    return value


def _text(data: Mapping[str, JsonValue], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise BotRecordError(f"{key} is missing or not a string")
    return value


def _optional_text(data: Mapping[str, JsonValue], key: str) -> str | None:
    value = data.get(key)
    if value is not None and not isinstance(value, str):
        raise BotRecordError(f"{key} is not a string")
    return value


def _iso_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
