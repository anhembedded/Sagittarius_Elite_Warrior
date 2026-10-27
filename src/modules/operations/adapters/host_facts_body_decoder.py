"""Read the facts of `state/host-facts.json` back into the contract types (`EPIC-047C`).

The mirror of `JsonHostFactsCodec`'s walk: the top-level groups are read by name, and beneath an
exchange snapshot a dataclass is read field by field from its own type hints, so a field the
writer can reach is a field the reader can read. It reads **tolerantly**, as a stored file must
(`EPIC-047A`'s note): a key the type does not know is ignored, a missing key takes the field's
default, and a missing key with no default, a wrong type or an unknown enum member is
`HostFactsUnreadableError` naming the path, never a silently defaulted number.
"""

from __future__ import annotations

import dataclasses
import types
import typing
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum

from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeFacts,
    ExchangeLoaded,
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    FuturesFacts,
    FuturesLoaded,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_held_facts import (
    BotExchangeRead,
    HostHeldFacts,
    SymbolLease,
    VenueKeyState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HostFactsUnreadableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def read_held_facts(body: dict[str, JsonValue]) -> HostHeldFacts:
    """@raise HostFactsUnreadableError A group is missing or malformed."""
    try:
        return HostHeldFacts(
            enabled_venues=tuple(
                TradingVenue(word) for word in _words(body, "enabled_venues")
            ),
            venue_keys=tuple(
                VenueKeyState(
                    TradingVenue(_text(item, "venue")),
                    _flag(item, "key_saved"),
                )
                for item in _objects(body, "venue_keys")
            ),
            leases=tuple(
                SymbolLease(
                    TradingVenue(_text(item, "venue")),
                    _text(item, "symbol"),
                    _text(item, "holder", allow_empty=True),
                )
                for item in _objects(body, "leases")
            ),
            caps=_caps(_object(body, "caps")),
            exchange_reads=tuple(
                _exchange_read(item) for item in _objects(body, "exchange_reads")
            ),
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        InvalidOperation,
    ) as failure:
        raise HostFactsUnreadableError(
            f"the file's facts are malformed ({type(failure).__name__}: {failure})"
        ) from failure


def _caps(caps: dict[str, JsonValue]) -> OwnerBudgetCaps:
    return OwnerBudgetCaps(
        max_open_orders=_whole(caps, "max_open_orders"),
        min_order_spacing=timedelta(milliseconds=_whole(caps, "min_order_spacing_ms")),
        max_orders_per_minute=_whole(caps, "max_orders_per_minute"),
    )


def _exchange_read(item: dict[str, JsonValue]) -> BotExchangeRead:
    bot_id, state = _text(item, "bot_id"), _text(item, "state")
    facts = _object(item, "facts")
    if state == "spot":
        return BotExchangeRead(bot_id, ExchangeLoaded(_record(ExchangeFacts, facts)))
    if state == "futures":
        return BotExchangeRead(bot_id, FuturesLoaded(_record(FuturesFacts, facts)))
    if state == "unavailable":
        return BotExchangeRead(
            bot_id, ExchangeUnavailable(_text(facts, "reason", allow_empty=True))
        )
    raise ValueError(f"an exchange read in state {state!r}")


def _record[T](cls: type[T], doc: JsonValue) -> T:
    if not isinstance(doc, dict):
        raise TypeError(f"{cls.__name__} is an object")
    hints = typing.get_type_hints(cls)
    values: dict[str, object] = {}
    for field in dataclasses.fields(cls):  # type: ignore[arg-type]
        if field.name in doc:
            values[field.name] = _value(hints[field.name], doc[field.name], field.name)
        elif field.default is dataclasses.MISSING and (
            field.default_factory is dataclasses.MISSING
        ):
            raise KeyError(f"{cls.__name__}.{field.name} is missing")
    return cls(**values)


def _value(hint: object, raw: JsonValue, name: str) -> object:
    origin = typing.get_origin(hint)
    if origin is typing.Union or origin is types.UnionType:
        members = typing.get_args(hint)
        if raw is None and type(None) in members:
            return None
        (inner,) = (m for m in members if m is not type(None))
        return _value(inner, raw, name)
    if origin is tuple:
        if not isinstance(raw, list):
            raise TypeError(f"{name} is a list")
        (item_hint, _) = typing.get_args(hint)
        return tuple(_value(item_hint, item, name) for item in raw)
    if isinstance(hint, type):
        return _scalar(hint, raw, name)
    raise TypeError(f"{name}: the file has no rule for {hint!r}")


def _scalar(hint: type, raw: JsonValue, name: str) -> object:
    if dataclasses.is_dataclass(hint):
        return _record(hint, raw)
    if issubclass(hint, Enum):
        return hint(raw)
    reader = _READERS.get(hint)
    if reader is None:
        raise TypeError(f"{name}: the file has no rule for {hint.__name__}")
    return reader(raw, name)


def _read_flag(raw: JsonValue, name: str) -> bool:
    if type(raw) is not bool:
        raise TypeError(f"{name} is true or false")
    return raw


def _read_whole(raw: JsonValue, name: str) -> int:
    if type(raw) is not int:
        raise TypeError(f"{name} is a whole number")
    return raw


def _read_text(raw: JsonValue, name: str) -> str:
    if type(raw) is not str:
        raise TypeError(f"{name} is text")
    return raw


def _read_decimal(raw: JsonValue, name: str) -> Decimal:
    if type(raw) is not str:
        raise TypeError(f"{name} is a decimal in text")
    value = Decimal(raw)
    if not value.is_finite():
        raise ValueError(f"{name} is not a finite decimal")
    return value


def _read_moment(raw: JsonValue, name: str) -> datetime:
    if type(raw) is not str:
        raise TypeError(f"{name} is a moment in text")
    moment = datetime.fromisoformat(raw)
    if moment.tzinfo is None:
        raise ValueError(f"{name} has no time zone")
    return moment.astimezone(UTC)


_READERS: dict[type, Callable[[JsonValue, str], object]] = {
    bool: _read_flag,
    int: _read_whole,
    str: _read_text,
    Decimal: _read_decimal,
    datetime: _read_moment,
}


def _object(parent: dict[str, JsonValue], key: str) -> dict[str, JsonValue]:
    found = parent[key]
    if not isinstance(found, dict):
        raise TypeError(f"{key} is an object")
    return found


def _list(parent: dict[str, JsonValue], key: str) -> list[JsonValue]:
    found = parent[key]
    if not isinstance(found, list):
        raise TypeError(f"{key} is a list")
    return found


def _objects(parent: dict[str, JsonValue], key: str) -> list[dict[str, JsonValue]]:
    items = _list(parent, key)
    if not all(isinstance(item, dict) for item in items):
        raise TypeError(f"{key} holds objects")
    return typing.cast("list[dict[str, JsonValue]]", items)


def _words(parent: dict[str, JsonValue], key: str) -> list[str]:
    items = _list(parent, key)
    if not all(type(item) is str for item in items):
        raise TypeError(f"{key} holds words")
    return typing.cast("list[str]", items)


def _text(holder: dict[str, JsonValue], key: str, *, allow_empty: bool = False) -> str:
    found = holder[key]
    if type(found) is not str or (not found and not allow_empty):
        raise TypeError(f"{key} is text")
    return found


def _flag(holder: dict[str, JsonValue], key: str) -> bool:
    found = holder[key]
    if type(found) is not bool:
        raise TypeError(f"{key} is true or false")
    return found


def _whole(holder: dict[str, JsonValue], key: str) -> int:
    found = holder[key]
    if type(found) is not int:
        raise TypeError(f"{key} is a whole number")
    return found
