"""`EPIC-047C` - the bridge reads the whole host-facts file back: equal to what the host wrote."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
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
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.json_host_facts_codec import (
    UNAVAILABLE_WORDS,
    JsonHostFactsCodec,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HostFactsDocument,
    HostFactsHeader,
    HostFactsUnreadableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.futures_world import (
    AVAILABLE_MARGIN,
    BRACKETS,
    SYMBOL,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.host_facts.host_facts_world import (
    NOW,
    document,
    facts,
    spot_facts,
)

codec = JsonHostFactsCodec()


def _futures() -> FuturesFacts:
    return FuturesFacts(
        venue_title="Futures Testnet",
        symbol=SYMBOL,
        quote_asset="USDT",
        read_at=datetime(2026, 10, 13, 9, tzinfo=UTC),
        available_margin=AVAILABLE_MARGIN,
        position=Decimal("0.010"),
        position_mode=PositionMode.ONE_WAY,
        symbol_setting=FuturesSymbolSetting(
            SYMBOL, 3, MarginType.ISOLATED, Decimal(1_000_000)
        ),
        brackets=BRACKETS,
        own_open_orders=1,
        foreign_open_orders=0,
        can_trade=None,
    )


def _full() -> HostFactsDocument:
    held = HostHeldFacts(
        enabled_venues=(TradingVenue.SPOT_TESTNET, TradingVenue.FUTURES_TESTNET),
        venue_keys=(
            VenueKeyState(TradingVenue.SPOT_TESTNET, key_saved=True),
            VenueKeyState(TradingVenue.FUTURES_TESTNET, key_saved=False),
        ),
        leases=(
            SymbolLease(TradingVenue.SPOT_TESTNET, "BTCUSDT", "grid:aaaaaa"),
            SymbolLease(TradingVenue.FUTURES_TESTNET, "BTCUSDT", ""),
        ),
        caps=facts().caps,
        exchange_reads=(
            BotExchangeRead("aaaaaa", ExchangeLoaded(spot_facts())),
            BotExchangeRead("bbbbbb", FuturesLoaded(_futures())),
            BotExchangeRead("cccccc", ExchangeUnavailable("x")),
        ),
    )
    return document(7, held)


def test_what_the_host_wrote_is_what_the_bridge_reads() -> None:
    written = _full()

    read = codec.decode(codec.encode(written))

    # An exchange failure's own words are never written (they may carry a key or a URL), so the
    # reader gets the sentence that stands in for them.
    expected = replace(
        written,
        facts=replace(
            written.facts,
            exchange_reads=(
                *written.facts.exchange_reads[:2],
                BotExchangeRead("cccccc", ExchangeUnavailable(UNAVAILABLE_WORDS)),
            ),
        ),
    )
    assert read == expected


def test_a_decimal_keeps_every_digit_it_was_written_with() -> None:
    read = codec.decode(codec.encode(_full()))

    futures = read.facts.exchange_reads[1].snapshot
    assert isinstance(futures, FuturesLoaded)
    assert str(futures.facts.position) == "0.010"


def test_the_header_of_the_whole_file_is_the_headers() -> None:
    raw = codec.encode(_full())

    assert codec.decode(raw).header == codec.decode_header(raw)
    assert codec.decode(raw).header == HostFactsHeader(7, NOW, 15, pid=4242)


def test_a_key_the_reader_does_not_know_is_ignored_in_the_top_level_and_in_a_record() -> (
    None
):
    body = json.loads(codec.encode(_full()))
    body["added_by_a_newer_host"] = {"anything": 1}
    body["leases"][0]["since"] = "2026-10-26"
    body["exchange_reads"][0]["facts"]["a_new_balance"] = "1"

    assert codec.decode(json.dumps(body).encode()) == codec.decode(
        codec.encode(_full())
    )


def test_a_field_the_type_defaults_may_be_missing() -> None:
    body = json.loads(codec.encode(_full()))
    del body["exchange_reads"][1]["facts"]["asset_mode"]

    read = codec.decode(json.dumps(body).encode())

    futures = read.facts.exchange_reads[1].snapshot
    assert isinstance(futures, FuturesLoaded)
    assert futures.facts.asset_mode is None


@pytest.mark.parametrize(
    "damage",
    [
        lambda b: b.pop("caps"),
        lambda b: b.update(enabled_venues=["no-such-venue"]),
        lambda b: b.update(enabled_venues="spot_testnet"),
        lambda b: b["venue_keys"][0].update(key_saved="yes"),
        lambda b: b["leases"][0].pop("symbol"),
        lambda b: b["caps"].update(max_open_orders=1.5),
        lambda b: b["exchange_reads"][0]["facts"].pop("symbol"),
        lambda b: b["exchange_reads"][0]["facts"].update(base_free=0.5),
        lambda b: b["exchange_reads"][0]["facts"].update(base_free="NaN"),
        lambda b: b["exchange_reads"][0]["facts"].update(read_at="2026-10-26T12:00:00"),
        lambda b: b["exchange_reads"][0].update(state="mystery"),
        lambda b: b["exchange_reads"][1]["facts"].update(position_mode="sideways"),
    ],
    ids=[
        "no-caps",
        "unknown-venue",
        "venues-not-a-list",
        "key-saved-not-a-flag",
        "lease-without-symbol",
        "caps-not-whole",
        "facts-without-symbol",
        "decimal-as-number",
        "decimal-not-finite",
        "moment-without-zone",
        "unknown-state",
        "unknown-enum-member",
    ],
)
def test_a_file_that_is_not_what_the_types_say_is_unreadable_not_defaulted(
    damage: object,
) -> None:
    body = json.loads(codec.encode(_full()))
    damage(body)  # type: ignore[operator]

    with pytest.raises(HostFactsUnreadableError):
        codec.decode(json.dumps(body).encode())


def test_a_file_of_another_schema_is_unreadable() -> None:
    body = json.loads(codec.encode(_full()))
    body["schema"] = "sew.host-facts/2"

    with pytest.raises(HostFactsUnreadableError):
        codec.decode(json.dumps(body).encode())
