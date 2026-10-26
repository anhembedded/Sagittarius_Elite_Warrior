"""The host-facts file as JSON, written by hand (`EPIC-047B`).

The file is a stored-file contract, so it is encoded by hand and read tolerantly (`EPIC-047A`'s
note on stored files); the encoding sits behind `IHostFactsCodec`, and `EPIC-047A`'s reflective
codec can replace it without changing what the file holds.

@par A closed list, by construction
The top-level fields are written by name below. Beneath an exchange snapshot the walk follows the
dataclass's own fields (`ExchangeFacts`, `FuturesFacts` and what they hold), so the file can hold
a field only if a contract type has it, and `test_json_host_facts_codec` fails on a field named
like a secret and on any text field it has not been told about. Two fields are free text an
exchange failure fills, and an exception's words may carry a key or a URL: they are never written;
`UNAVAILABLE_WORDS` stands in, and the reason stays in the host's log.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeLoaded,
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    FuturesLoaded,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_held_facts import (
    UNPUBLISHED_TEXT_FIELDS,
    BotExchangeRead,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HOST_FACTS_SCHEMA,
    HostFactsDocument,
    HostFactsHeader,
    HostFactsUnreadableError,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_facts_codec import (
    IHostFactsCodec,
)

#: What the file says whenever the exchange could not answer, whatever the reason was.
UNAVAILABLE_WORDS = "the host could not read the exchange's facts; its log says why"


class JsonHostFactsCodec(IHostFactsCodec):
    def encode(self, document: HostFactsDocument) -> bytes:
        header, held = document.header, document.facts
        body: dict[str, JsonValue] = {
            "schema": HOST_FACTS_SCHEMA,
            "revision": header.revision,
            "written_at": _moment(header.written_at),
            "heartbeat_s": header.heartbeat_s,
            "pid": header.pid,
            "enabled_venues": [venue.value for venue in held.enabled_venues],
            "venue_keys": [
                {"venue": key.venue.value, "key_saved": key.key_saved}
                for key in held.venue_keys
            ],
            "leases": [
                {
                    "venue": lease.venue.value,
                    "symbol": lease.symbol,
                    "holder": lease.holder,
                }
                for lease in held.leases
            ],
            "caps": {
                "max_open_orders": held.caps.max_open_orders,
                "min_order_spacing_ms": round(
                    held.caps.min_order_spacing.total_seconds() * 1000
                ),
                "max_orders_per_minute": held.caps.max_orders_per_minute,
            },
            "exchange_reads": [_exchange_read(read) for read in held.exchange_reads],
        }
        return json.dumps(body, indent=2, sort_keys=True).encode("utf-8")

    def decode_header(self, raw: bytes) -> HostFactsHeader:
        try:
            parsed = json.loads(raw)
        except ValueError as failure:
            raise HostFactsUnreadableError("the file is not JSON") from failure
        if not isinstance(parsed, dict):
            raise HostFactsUnreadableError("the file is not a JSON object")
        if parsed.get("schema") != HOST_FACTS_SCHEMA:
            raise HostFactsUnreadableError(
                f"the file's schema is {parsed.get('schema')!r}, not {HOST_FACTS_SCHEMA!r}"
            )
        try:
            return HostFactsHeader(
                revision=_whole_number(parsed["revision"]),
                written_at=_aware_moment(parsed["written_at"]),
                heartbeat_s=_whole_number(parsed["heartbeat_s"]),
                pid=_whole_number(parsed["pid"]),
            )
        except (KeyError, TypeError, ValueError) as failure:
            raise HostFactsUnreadableError(
                f"the file's header is malformed ({type(failure).__name__})"
            ) from failure


def _exchange_read(read: BotExchangeRead) -> dict[str, JsonValue]:
    snapshot = read.snapshot
    if isinstance(snapshot, ExchangeLoaded):
        return {"bot_id": read.bot_id, "state": "spot", "facts": _wire(snapshot.facts)}
    if isinstance(snapshot, FuturesLoaded):
        return {
            "bot_id": read.bot_id,
            "state": "futures",
            "facts": _wire(snapshot.facts),
        }
    if isinstance(snapshot, ExchangeUnavailable):
        return {
            "bot_id": read.bot_id,
            "state": "unavailable",
            "facts": {"reason": UNAVAILABLE_WORDS},
        }
    raise TypeError(f"a {type(snapshot).__name__} is not a snapshot the file holds")


def _wire(value: object) -> JsonValue:
    """A contract value as JSON, following the dataclass's own fields."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        hidden = UNPUBLISHED_TEXT_FIELDS.get(type(value))
        return {
            field.name: (
                UNAVAILABLE_WORDS
                if field.name == hidden and getattr(value, field.name)
                else _wire(getattr(value, field.name))
            )
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Enum):
        return cast("JsonValue", value.value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return _moment(value)
    if isinstance(value, tuple | list):
        return [_wire(item) for item in value]
    if value is None or isinstance(value, bool | int | str):
        return value
    raise TypeError(f"the host-facts file has no rule for a {type(value).__name__}")


def _moment(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _aware_moment(raw: object) -> datetime:
    moment = datetime.fromisoformat(str(raw))
    if moment.tzinfo is None:
        raise ValueError("the moment has no time zone")
    return moment


def _whole_number(raw: object) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise TypeError("not a whole number")
    return raw
