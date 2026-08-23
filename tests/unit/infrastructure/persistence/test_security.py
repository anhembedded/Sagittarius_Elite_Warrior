"""Shard-name safety for `DatabaseManager`.

The enforcement itself moved into the engine's `SqliteShardManager` (engine
`EPIC-004A`) when the generic sharding logic was factored out, so the previous
version of this file — which monkeypatched a module-level `_VALID_SYMBOL_REGEX`
that no longer exists here — could not survive as written. What is tested is the
same guarantee, now asserted through this app's own public surface: a symbol that
could escape the database directory never reaches the filesystem.

The deeper defence (containment still holds even when the name pattern is
deliberately permissive) belongs to the engine and is tested there, in
`tests/extensions/persistence/test_sqlite_shard_manager.py`.
"""

import pytest
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.database_manager import (
    DatabaseConfig,
    DatabaseManager,
)


@pytest.mark.parametrize(
    "dangerous_symbol",
    [
        "../../../etc/passwd",
        "../BTCUSDT",
        "sub/dir",
        "BTC USDT",
        "",
    ],
)
def test_database_manager_rejects_symbols_that_could_escape_the_db_dir(
    dangerous_symbol,
):
    config = DatabaseConfig(db_dir="/tmp/valid_dir")
    manager = DatabaseManager(config)

    try:
        with pytest.raises(ValueError):
            manager.get_session(dangerous_symbol)
    finally:
        manager.dispose_all()


def test_database_manager_valid_path():
    config = DatabaseConfig(db_dir=":memory:")
    manager = DatabaseManager(config)
    try:
        # Just ensuring a valid symbol doesn't throw
        manager.get_session("BTCUSDT")
    finally:
        manager.dispose_all()
