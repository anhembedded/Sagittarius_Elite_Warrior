"""`BUG-172` — candles stored before each venue had a store are never relabelled by guess.

@details Real SQLite and the repository the app builds. A legacy store is written
the way an earlier build did (every shard in the configured directory), then
`label_legacy_store` runs, then each venue's store is read. The rows belong to the
venue the setting names; a setting that names none leaves them served to nobody.
Testnet candles must never come back as real-money prices.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.database_manager import (
    DatabaseConfig,
    DatabaseManager,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.legacy_store_label import (
    MARKER,
    QUARANTINE_DIRECTORY,
    LegacyStoreOutcome,
    label_legacy_store,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.sqlalchemy_repository import (
    SQLAlchemyMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.venue_directory import (
    venue_directory,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    candle,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)

_SYMBOL = "BTCUSDT"
_MINUTE = TimeFrame.ONE_MINUTE


@pytest.fixture
def legacy_store(tmp_path: Path) -> Path:
    """What an earlier build left: one Spot shard in the configured directory."""
    manager = DatabaseManager(DatabaseConfig(db_dir=str(tmp_path)))
    SQLAlchemyMarketDataRepository(manager).save_klines(
        MarketType.SPOT, [candle(_SYMBOL, 0, close_price=111.0)]
    )
    manager.dispose_all()
    return tmp_path


@pytest.fixture
def served() -> Iterator[list[DatabaseManager]]:
    managers: list[DatabaseManager] = []
    yield managers
    for manager in managers:
        manager.dispose_all()


def _served_by(
    base: Path, venue: MarketDataVenue, opened: list[DatabaseManager]
) -> list[float]:
    """The closes `venue`'s own store serves for the legacy series."""
    manager = DatabaseManager(DatabaseConfig(db_dir=venue_directory(str(base), venue)))
    opened.append(manager)
    rows = SQLAlchemyMarketDataRepository(manager).get_klines(
        MarketType.SPOT, _SYMBOL, _MINUTE
    )
    return [row.close_price for row in rows]


def test_a_futures_testnet_setting_labels_the_rows_testnet(
    legacy_store: Path, served
) -> None:
    outcome = label_legacy_store(str(legacy_store), "futures_testnet")

    assert outcome is LegacyStoreOutcome.LABELLED
    assert _served_by(legacy_store, MarketDataVenue.FUTURES_TESTNET, served) == [111.0]
    assert _served_by(legacy_store, MarketDataVenue.MAINNET_PUBLIC, served) == []
    assert _served_by(legacy_store, MarketDataVenue.SPOT_TESTNET, served) == []


def test_a_mainnet_setting_labels_the_rows_mainnet(legacy_store: Path, served) -> None:
    outcome = label_legacy_store(str(legacy_store), "mainnet_public")

    assert outcome is LegacyStoreOutcome.LABELLED
    assert _served_by(legacy_store, MarketDataVenue.MAINNET_PUBLIC, served) == [111.0]
    for testnet in (MarketDataVenue.FUTURES_TESTNET, MarketDataVenue.SPOT_TESTNET):
        assert _served_by(legacy_store, testnet, served) == []


@pytest.mark.parametrize("setting", [None, "", "mainnet", 5, "FUTURES_TESTNET"])
def test_an_unreadable_setting_serves_the_rows_to_no_venue(
    legacy_store: Path, served, setting: object
) -> None:
    outcome = label_legacy_store(str(legacy_store), setting)

    assert outcome is LegacyStoreOutcome.QUARANTINED
    for venue in MarketDataVenue:
        assert _served_by(legacy_store, venue, served) == []
    kept = list((legacy_store / QUARANTINE_DIRECTORY).glob("*.db"))
    assert [path.name for path in kept] == ["spot_BTCUSDT.db"], "nothing is deleted"


def test_it_runs_once_so_rows_written_later_are_never_taken_for_legacy(
    legacy_store: Path, served
) -> None:
    label_legacy_store(str(legacy_store), "futures_testnet")
    manager = DatabaseManager(
        DatabaseConfig(
            db_dir=venue_directory(str(legacy_store), MarketDataVenue.MAINNET_PUBLIC)
        )
    )
    served.append(manager)
    SQLAlchemyMarketDataRepository(manager).save_klines(
        MarketType.SPOT, [candle(_SYMBOL, 0, close_price=65000.0)]
    )

    again = label_legacy_store(str(legacy_store), "futures_testnet")

    assert again is LegacyStoreOutcome.ALREADY_LABELLED
    assert _served_by(legacy_store, MarketDataVenue.MAINNET_PUBLIC, served) == [65000.0]
    assert (legacy_store / MARKER).is_file()


def test_a_store_with_nothing_in_it_is_marked_so_later_rows_are_not_legacy(
    tmp_path: Path,
) -> None:
    assert (
        label_legacy_store(str(tmp_path), "mainnet_public")
        is LegacyStoreOutcome.NOTHING_TO_LABEL
    )
    assert (tmp_path / MARKER).is_file()


def test_a_clash_moves_nothing_and_leaves_the_next_start_to_try_again(
    legacy_store: Path,
) -> None:
    testnet_dir = legacy_store / MarketDataVenue.FUTURES_TESTNET.value
    testnet_dir.mkdir()
    (testnet_dir / "spot_BTCUSDT.db").write_bytes(b"already here")

    with pytest.raises(FileExistsError):
        label_legacy_store(str(legacy_store), "futures_testnet")

    assert (legacy_store / "spot_BTCUSDT.db").is_file()
    assert (testnet_dir / "spot_BTCUSDT.db").read_bytes() == b"already here"
    assert not (legacy_store / MARKER).exists()
