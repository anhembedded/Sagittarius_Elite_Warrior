import pytest
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.database_manager import (
    DatabaseConfig,
    DatabaseManager,
)


def test_database_manager_path_traversal():
    config = DatabaseConfig(db_dir="/tmp/valid_dir")
    manager = DatabaseManager(config)

    try:
        # We must mock re.match to bypass the symbol validation so we can test the path traversal logic
        import re

        original_match = re.match

        def mock_match(pattern, string):
            if pattern == r"^[A-Za-z0-9_-]+$":
                return True
            return original_match(pattern, string)

        with pytest.MonkeyPatch().context() as m:
            m.setattr(re, "match", mock_match)
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
