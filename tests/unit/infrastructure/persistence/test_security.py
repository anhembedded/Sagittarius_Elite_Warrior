from unittest.mock import Mock

import pytest

from Sagittarius_Elite_Warrior.src.infrastructure.persistence.database_manager import (
    DatabaseConfig,
    DatabaseManager,
)


def test_database_manager_path_traversal():
    config = DatabaseConfig(db_dir="/tmp/valid_dir")
    manager = DatabaseManager(config)

    try:
        from Sagittarius_Elite_Warrior.src.infrastructure.persistence import (
            database_manager,
        )

        mock_regex = Mock()
        mock_regex.match.return_value = True

        with pytest.MonkeyPatch().context() as m:
            m.setattr(database_manager, "_VALID_SYMBOL_REGEX", mock_regex)
            with pytest.raises(
                PermissionError, match="Path traversal attempt detected"
            ):
                manager.get_session("../../../etc/passwd")
    finally:
        manager.dispose_all()


def test_database_manager_valid_path():
    config = DatabaseConfig(db_dir=":memory:")
    manager = DatabaseManager(config)
    try:
        # Just ensuring a valid symbol doesn't throw PermissionError
        manager.get_session("BTCUSDT")
    finally:
        manager.dispose_all()
