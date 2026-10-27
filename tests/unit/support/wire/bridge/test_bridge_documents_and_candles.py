"""`EPIC-047H` - the bridge serves the host's market-data and reads files like the facts file, and the closed candles on a call.

The session is the real one over ports shaped from the ABCs; the files are values a test moves.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_protocol import (
    DOCUMENTS_LOOK_S,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_bridge_candles import (
    UnknownCandleSeriesError,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.bridge.bridge_world import (
    ROOTS,
    Desk,
    FakeCandles,
    FakeDocument,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_operations import (
    full_host_reads,
    full_market_data,
    minimal_market_data,
)

MARKET_ROOT = "sew.market-data-document/1"
READS_ROOT = "sew.host-reads-document/1"


def _desk(
    candles: FakeCandles | None = None,
) -> tuple[Desk, FakeDocument, FakeDocument]:
    market = FakeDocument(MARKET_ROOT, full_market_data(), revision=70)
    reads = FakeDocument(READS_ROOT, full_host_reads(), revision=9)
    desk = Desk(documents={"market": market, "reads": reads}, candles=candles)
    desk.greet()
    return desk, market, reads


def test_the_snapshot_carries_each_file_under_its_kind_beside_the_facts() -> None:
    desk, _, _ = _desk()

    snapshot = desk.result_of(desk.call("snapshot"))

    documents = snapshot["documents"]
    assert isinstance(documents, dict)
    assert sorted(documents) == ["market", "reads"]
    assert documents["market"]["revision"] == 70  # type: ignore[index]
    assert ROOTS.schema_of(documents["market"]["document"]) == MARKET_ROOT  # type: ignore[index]
    assert ROOTS.schema_of(documents["reads"]["document"]) == READS_ROOT  # type: ignore[index]
    assert ROOTS.schema_of(snapshot["facts"]["document"]) == "sew.host-facts-document/1"  # type: ignore[index]


def test_a_new_revision_of_one_file_is_one_event_of_its_kind_and_the_others_stay_quiet() -> (
    None
):
    desk, market, _ = _desk()
    desk.result_of(desk.call("snapshot"))
    desk.result_of(desk.call("subscribe"))

    market.host_wrote(minimal_market_data(), revision=71)
    desk.advance(DOCUMENTS_LOOK_S)

    (event,) = desk.events("market")
    assert (event["revision"], event["state"]) == (71, "live")
    assert desk.events("reads") == []
    assert desk.events("facts") == []


def test_the_same_revision_is_no_event_and_the_snapshots_revision_is_not_sent_again() -> (
    None
):
    desk, market, _ = _desk()
    market.host_wrote(full_market_data(), revision=80)
    desk.result_of(desk.call("snapshot"))
    desk.result_of(desk.call("subscribe"))

    desk.advance(DOCUMENTS_LOOK_S)
    desk.advance(DOCUMENTS_LOOK_S)

    assert desk.events("market") == []


def test_a_session_with_no_extra_files_snapshots_an_empty_documents_object() -> None:
    desk = Desk()
    desk.greet()

    assert desk.result_of(desk.call("snapshot"))["documents"] == {}


def _ask(desk: Desk, **params: object) -> int:
    base: dict[str, object] = {
        "venue": "futures_testnet",
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "limit": 3,
    }
    return desk.call("candles", **(base | params))


def test_a_candles_call_returns_the_window_the_store_gave_and_passes_the_query_on() -> (
    None
):
    candles = FakeCandles()
    desk, _, _ = _desk(candles)

    result = desk.result_of(_ask(desk, before="2026-10-27T09:00:00+00:00"))

    assert ROOTS.schema_of(result["window"]) == "sew.candle-window/1"
    (query,) = candles.asked
    assert (query.venue, query.symbol, query.timeframe, query.limit) == (
        "futures_testnet",
        "BTCUSDT",
        "1m",
        3,
    )
    assert query.before is not None
    assert query.before.utcoffset() is not None


@pytest.mark.parametrize(
    "params",
    [
        {"limit": "3"},
        {"venue": 5},
        {"before": "yesterday"},
        {"before": "2026-10-27T09:00:00"},
        {"before": 7},
    ],
    ids=[
        "limit-text",
        "venue-number",
        "before-words",
        "before-no-zone",
        "before-number",
    ],
)
def test_a_malformed_candles_call_is_a_call_error_and_reads_nothing(
    params: dict[str, object],
) -> None:
    candles = FakeCandles()
    desk, _, _ = _desk(candles)

    call_id = _ask(desk, **params)

    assert desk.error_of(call_id)["code"] == "bad_candles"
    assert candles.asked == []


def test_a_series_the_store_cannot_name_is_a_bad_candles_error_with_its_words() -> None:
    candles = FakeCandles()
    candles.refusal = UnknownCandleSeriesError("'7x' is not a timeframe")
    desk, _, _ = _desk(candles)

    error = desk.error_of(_ask(desk, timeframe="7x"))

    assert (error["code"], error["message"]) == (
        "bad_candles",
        "'7x' is not a timeframe",
    )


def test_a_build_with_no_candle_reader_says_so() -> None:
    desk, _, _ = _desk(None)

    assert desk.error_of(_ask(desk))["code"] == "no_candles"
