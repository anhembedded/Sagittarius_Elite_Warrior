"""`EPIC-047B` - what the file may hold: a closed list of fields, and never a secret."""

from __future__ import annotations

import dataclasses
import json
import typing
from datetime import UTC, datetime

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts import host_held_facts
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeFacts,
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    FuturesFacts,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.json_host_facts_codec import (
    JsonHostFactsCodec,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HOST_FACTS_SCHEMA,
    HostFactsHeader,
    HostFactsUnreadableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.earlier_runs_inventory import (
    EarlierRunsInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.host_facts.host_facts_world import (
    NOW,
    PLANTED_KEY_LIKE,
    document,
    facts,
)

codec = JsonHostFactsCodec()

#: Name parts a field of the file may not carry: the same reason `health.json`'s sections are refused
#: these (`FORBIDDEN_KEY_PARTS`), minus the money words, because an owner-only file of exchange facts
#: holds balances by design.
SECRET_NAME_PARTS = (
    "secret",
    "password",
    "passphrase",
    "api_key",
    "apikey",
    "private_key",
    "token",
    "credential",
    "listenkey",
    "listen_key",
)


#: Every dataclass the file can reach through its types, found by walking the annotations.
def _reachable_dataclasses() -> set[type]:
    found: set[type] = set()
    pending: list[object] = [
        host_held_facts.HostHeldFacts,
        FuturesFacts,
        ExchangeFacts,
        ExchangeUnavailable,
        OwnerBudgetCaps,
        FuturesSymbolSetting,
        LeverageBrackets,
        LeverageBracket,
        EarlierRunsInventory,
    ]
    while pending:
        candidate = pending.pop()
        if dataclasses.is_dataclass(candidate) and isinstance(candidate, type):
            if candidate in found:
                continue
            found.add(candidate)
            hints = typing.get_type_hints(candidate)
            pending.extend(hints.values())
        else:
            pending.extend(typing.get_args(candidate))
    return found


def test_the_file_is_one_json_object_with_the_schema_and_a_header() -> None:
    parsed = json.loads(codec.encode(document(revision=7)))

    assert parsed["schema"] == HOST_FACTS_SCHEMA
    assert parsed["revision"] == 7
    assert parsed["heartbeat_s"] == 15
    assert parsed["pid"] == 4242
    assert parsed["written_at"] == "2026-10-26T12:00:00Z"


def test_the_file_has_exactly_these_top_level_and_fact_fields() -> None:
    """The closed list: a new field in the file is a deliberate edit of this test."""
    parsed = json.loads(codec.encode(document()))

    assert sorted(parsed) == [
        "caps",
        "enabled_venues",
        "exchange_reads",
        "heartbeat_s",
        "leases",
        "pid",
        "revision",
        "schema",
        "venue_keys",
        "written_at",
    ]
    assert sorted(parsed["venue_keys"][0]) == ["key_saved", "venue"]
    assert sorted(parsed["leases"][0]) == ["holder", "symbol", "venue"]
    assert sorted(parsed["caps"]) == [
        "max_open_orders",
        "max_orders_per_minute",
        "min_order_spacing_ms",
    ]
    assert sorted(parsed["exchange_reads"][0]) == ["bot_id", "facts", "state"]


def test_a_venue_with_a_saved_key_is_told_only_that_a_key_is_saved() -> None:
    parsed = json.loads(codec.encode(document()))

    assert parsed["venue_keys"] == [{"venue": "spot_testnet", "key_saved": True}]


def test_no_field_the_file_can_reach_is_named_like_a_secret() -> None:
    """A guard on the types, not on one value: add `api_key` to any dataclass the file reaches
    and this fails before a value ever flows."""
    names = [
        (cls.__name__, field.name)
        for cls in _reachable_dataclasses()
        for field in dataclasses.fields(cls)
        if any(part in field.name.lower() for part in SECRET_NAME_PARTS)
    ]

    assert names == []


#: Every text field the file can reach, and why each is safe: a name or a code from our own
#: vocabulary or the exchange's symbol list, never words an exception composed. A new text field
#: is free text until someone decides otherwise here.
KNOWN_TEXT_FIELDS = {
    ("SymbolLease", "symbol"),
    ("SymbolLease", "holder"),
    ("BotExchangeRead", "bot_id"),
    ("ExchangeFacts", "venue_title"),
    ("ExchangeFacts", "symbol"),
    ("ExchangeFacts", "base_asset"),
    ("ExchangeFacts", "quote_asset"),
    ("FuturesFacts", "venue_title"),
    ("FuturesFacts", "symbol"),
    ("FuturesFacts", "quote_asset"),
    ("FuturesSymbolSetting", "symbol"),
    ("LeverageBrackets", "symbol"),
    # Replaced by `UNAVAILABLE_WORDS` whenever non-empty (the encoder, not the reader, enforces it).
    ("EarlierRunsInventory", "unavailable"),
    ("ExchangeUnavailable", "reason"),
}


def test_every_text_field_the_file_can_reach_is_known() -> None:
    texts = {
        (cls.__name__, field.name)
        for cls in _reachable_dataclasses()
        for field in dataclasses.fields(cls)
        if typing.get_type_hints(cls)[field.name] is str
    }

    assert texts == KNOWN_TEXT_FIELDS


def test_the_reachable_types_are_found_by_the_walk() -> None:
    """The guard above proves nothing if the walk finds nothing."""
    reached = {cls.__name__ for cls in _reachable_dataclasses()}

    assert {
        "HostHeldFacts",
        "VenueKeyState",
        "ExchangeFacts",
        "FuturesFacts",
    } <= reached


def test_a_secret_like_exchange_reason_never_reaches_the_bytes() -> None:
    held = facts(
        reason=f"the open orders were not read (apiKey={PLANTED_KEY_LIKE} rejected)",
    )

    raw = codec.encode(document(held=held))

    assert PLANTED_KEY_LIKE.encode() not in raw
    assert b"apiKey" not in raw


def test_a_secret_like_earlier_runs_reason_never_reaches_the_bytes() -> None:
    held = facts(earlier_runs_reason=f"history refused for {PLANTED_KEY_LIKE}")

    raw = codec.encode(document(held=held))

    assert PLANTED_KEY_LIKE.encode() not in raw


def test_the_same_document_encodes_to_the_same_bytes() -> None:
    assert codec.encode(document()) == codec.encode(document())


def test_the_header_reads_back_what_was_written() -> None:
    written = document(
        revision=12, written_at=datetime(2026, 10, 26, 8, 30, tzinfo=UTC)
    )

    header = codec.decode_header(codec.encode(written))

    assert header == HostFactsHeader(12, written.header.written_at, 15, 4242)


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"{not json",
        b'["a list"]',
        b'{"schema": "sew.host-facts/9", "revision": 1}',
        json.dumps({"schema": HOST_FACTS_SCHEMA}).encode(),
        json.dumps(
            {
                "schema": HOST_FACTS_SCHEMA,
                "revision": "one",
                "written_at": NOW.isoformat(),
                "heartbeat_s": 15,
                "pid": 1,
            }
        ).encode(),
    ],
)
def test_a_file_that_is_not_a_host_facts_file_is_unreadable(raw: bytes) -> None:
    with pytest.raises(HostFactsUnreadableError):
        codec.decode_header(raw)
