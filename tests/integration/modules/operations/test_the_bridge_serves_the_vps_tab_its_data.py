"""`EPIC-047H` - the real bridge process serves the host's market data, reads and closed candles, and still holds no socket.

The files are written the way the host writes them (`WireDocumentSink`, the host's candle writer); the process is
the one `sshd` starts. What only a process can show: the entry point wires the three new readers, a rewrite of the
market-data file is an event on the pipe within the bridge's look, a closed-candle call is answered from the store
read-only while a writer holds a transaction open, and the process still has no socket.
"""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.readonly_candle_shards import (
    shard_path,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.wire_document_file import (
    WireDocumentSink,
)
from Sagittarius_Elite_Warrior.src.modules.operations.composition.wire_roots import (
    HOST_READS_DOCUMENT_ROOT,
    MARKET_DATA_DOCUMENT_ROOT,
    OPERATIONS_WIRE_ROOTS,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_reads_document import (
    HOST_READS_FILE_NAME,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.market_data_document import (
    MARKET_DATA_FILE_NAME,
)
from Sagittarius_Elite_Warrior.src.shell.wire_roots import link_roots
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_protocol import (
    EXIT_ENDED,
)
from Sagittarius_Elite_Warrior.src.support.wire.wire_roots import WireRoots
from Sagittarius_Elite_Warrior.tests.integration.modules.operations.test_the_bridge_process import (
    _a_data_root,
    _bridge,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_operations import (
    full_host_reads,
    full_market_data,
)

pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="reads /proc for the process's sockets"
)

VENUE = TradingVenue.FUTURES_TESTNET


def _the_host_wrote(state: Path, revision: int) -> None:
    now = datetime.now(UTC)
    roots = WireRoots(OPERATIONS_WIRE_ROOTS)
    market, reads = full_market_data(), full_host_reads()
    WireDocumentSink(
        state / MARKET_DATA_FILE_NAME, roots, MARKET_DATA_DOCUMENT_ROOT
    ).publish(
        replace(
            market, header=replace(market.header, revision=revision, written_at=now)
        )
    )
    WireDocumentSink(
        state / HOST_READS_FILE_NAME, roots, HOST_READS_DOCUMENT_ROOT
    ).publish(replace(reads, header=replace(reads.header, written_at=now)))


def _the_host_stored_candles(data_root: Path) -> sqlite3.Connection:
    """A shard the way the host's writer lays it out, with a writer left holding a transaction open."""
    path = shard_path(data_root / "database", VENUE, "BTCUSDT")
    path.parent.mkdir(parents=True)
    writer = sqlite3.connect(path, isolation_level=None)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute(
        "CREATE TABLE klines (symbol VARCHAR NOT NULL, interval VARCHAR NOT NULL, open_time DATETIME NOT NULL,"
        " open_price FLOAT NOT NULL, high_price FLOAT NOT NULL, low_price FLOAT NOT NULL, close_price FLOAT NOT NULL,"
        " volume FLOAT NOT NULL, close_time DATETIME NOT NULL, quote_asset_volume FLOAT NOT NULL,"
        " number_of_trades INTEGER NOT NULL, taker_buy_base_asset_volume FLOAT NOT NULL,"
        " taker_buy_quote_asset_volume FLOAT NOT NULL, PRIMARY KEY (symbol, interval, open_time))"
    )
    for minute in range(5):
        writer.execute(
            "INSERT INTO klines VALUES ('BTCUSDT','1m',?,1.5,2.5,1.25,2.0,3.0,?,0,0,0,0)",
            (
                f"2026-10-27 09:0{minute}:00.000000",
                f"2026-10-27 09:0{minute}:59.000000",
            ),
        )
    writer.execute("BEGIN IMMEDIATE")
    return writer


def test_the_bridge_serves_the_market_file_the_reads_file_and_the_closed_candles_and_holds_no_socket(
    tmp_path: Path,
) -> None:
    data_root, _ = _a_data_root(tmp_path)
    _the_host_wrote(data_root / "state", revision=70)
    writer = _the_host_stored_candles(data_root)
    roots = link_roots()
    try:
        with _bridge(data_root) as bridge:
            bridge.greet()
            bridge.next_of("welcome")

            snapshot = bridge.call(1, "snapshot")["data"]
            assert isinstance(snapshot, dict)
            documents = snapshot["documents"]
            assert sorted(documents) == ["market", "reads"]
            assert (documents["market"]["state"], documents["market"]["revision"]) == (
                "live",
                70,
            )
            market = roots.decode(documents["market"]["document"])
            assert market.symbols[0].symbol == "BTCUSDT"  # type: ignore[attr-defined]
            assert roots.decode(documents["reads"]["document"]).reads.planner  # type: ignore[attr-defined]

            answer = bridge.call(
                2,
                "candles",
                venue=VENUE.value,
                symbol="BTCUSDT",
                timeframe="1m",
                limit=3,
            )
            window = roots.decode(answer["data"]["window"])  # type: ignore[index]
            assert [c.open_time.minute for c in window.candles] == [2, 3, 4]  # type: ignore[attr-defined]
            assert window.older_available  # type: ignore[attr-defined]

            missing = bridge.call(
                3,
                "candles",
                venue=VENUE.value,
                symbol="ETHUSDT",
                timeframe="1m",
                limit=3,
            )
            assert not roots.decode(missing["data"]["window"]).shard_found  # type: ignore[attr-defined,index]

            assert bridge.call(4, "subscribe")["type"] == "result"
            _the_host_wrote(data_root / "state", revision=71)
            event = bridge.next_of("event")
            assert (event["kind"], event["revision"]) in {("market", 71), ("reads", 9)}

            assert bridge.sockets() == []
            assert bridge.hang_up() == EXIT_ENDED
    finally:
        writer.close()
