from threading import Event
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.use_cases.database.prune_empty_shards.command import (
    PruneEmptyShardsCommand,
    PruneEmptyShardsResult,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.database.prune_empty_shards.handler import (
    PruneEmptyShardsCommandHandler,
)


@pytest.fixture
def mock_repo():
    return Mock()


@pytest.fixture
def handler(mock_repo):
    return PruneEmptyShardsCommandHandler(mock_repo)


def test_removes_only_shards_with_zero_klines(handler, mock_repo):
    """BUG-078: a shard that holds even one kline (in any interval) must never
    be removed — only symbols where has_any_klines() is False are candidates."""
    mock_repo.list_available_shards.return_value = ["BTCUSDT", "PHANTOM1", "PHANTOM2"]
    mock_repo.has_any_klines.side_effect = lambda symbol: symbol == "BTCUSDT"

    result = handler.execute(PruneEmptyShardsCommand())

    assert isinstance(result, PruneEmptyShardsResult)
    assert result.scanned_count == 3
    assert set(result.removed_symbols) == {"PHANTOM1", "PHANTOM2"}
    mock_repo.clear_klines.assert_any_call("PHANTOM1", interval=None)
    mock_repo.clear_klines.assert_any_call("PHANTOM2", interval=None)
    assert mock_repo.clear_klines.call_count == 2


def test_never_deletes_a_shard_with_data(handler, mock_repo):
    mock_repo.list_available_shards.return_value = ["BTCUSDT", "ETHUSDT"]
    mock_repo.has_any_klines.return_value = True

    result = handler.execute(PruneEmptyShardsCommand())

    assert result.removed_symbols == []
    mock_repo.clear_klines.assert_not_called()


def test_no_shards_on_disk_is_a_no_op(handler, mock_repo):
    mock_repo.list_available_shards.return_value = []

    result = handler.execute(PruneEmptyShardsCommand())

    assert result.removed_symbols == []
    assert result.scanned_count == 0
    mock_repo.has_any_klines.assert_not_called()
    mock_repo.clear_klines.assert_not_called()


def test_cancellation_stops_remaining_shards(handler, mock_repo):
    cancellation = Event()
    symbols = [f"SYMBOL_{i}" for i in range(50)]
    mock_repo.list_available_shards.return_value = symbols

    def cancel_after_first_check(symbol):
        cancellation.set()
        return False

    mock_repo.has_any_klines.side_effect = cancel_after_first_check

    result = handler.execute(
        PruneEmptyShardsCommand(cancellation_requested=cancellation.is_set)
    )

    assert 1 <= mock_repo.has_any_klines.call_count < len(symbols)
    # only the one checked before cancellation fired was removed
    assert len(result.removed_symbols) == 1


def test_repository_exception_from_list_shards_propagates(handler, mock_repo):
    """Prune has no per-symbol try/except of its own — a failure to even list
    shards is a real error the coordinator's caller must see and log, not a
    silently empty result."""
    mock_repo.list_available_shards.side_effect = Exception("disk unavailable")

    with pytest.raises(Exception, match="disk unavailable"):
        handler.execute(PruneEmptyShardsCommand())
