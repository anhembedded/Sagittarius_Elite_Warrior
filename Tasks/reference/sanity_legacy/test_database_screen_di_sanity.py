"""
Layer 1 sanity test for Database screen (Storage Vault): boots the app for real
(no mocked dispatch, no UI) and verifies every query and command handler
resolves cleanly in DI container.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from Sagittarius_Elite_Warrior.src.application.use_cases.database.clear_market_data import (
    ClearMarketDataCommand,
    ClearMarketDataCommandHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.database.repair_data_gap import (
    RepairDataGapCommand,
    RepairDataGapCommandHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.audit_database_integrity import (
    AuditDatabaseIntegrityQuery,
    AuditDatabaseIntegrityQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_database_gaps import (
    GetDatabaseGapsQuery,
    GetDatabaseGapsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_database_status import (
    GetDatabaseStatusQuery,
    GetDatabaseStatusQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.list_available_symbols import (
    ListAvailableSymbolsQuery,
    ListAvailableSymbolsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.scan_all_databases import (
    ScanAllDatabasesQuery,
    ScanAllDatabasesQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.bulk_sync_market_data import (
    BulkSyncMarketDataCommand,
    BulkSyncMarketDataCommandHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data import (
    SyncMarketDataCommand,
    SyncMarketDataCommandHandler,
)
from Sagittarius_Elite_Warrior.src.main import create_app
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_DATABASE_COMMANDS = {
    GetDatabaseStatusQuery: GetDatabaseStatusQueryHandler,
    GetDatabaseGapsQuery: GetDatabaseGapsQueryHandler,
    AuditDatabaseIntegrityQuery: AuditDatabaseIntegrityQueryHandler,
    ScanAllDatabasesQuery: ScanAllDatabasesQueryHandler,
    ListAvailableSymbolsQuery: ListAvailableSymbolsQueryHandler,
    ClearMarketDataCommand: ClearMarketDataCommandHandler,
    RepairDataGapCommand: RepairDataGapCommandHandler,
    SyncMarketDataCommand: SyncMarketDataCommandHandler,
    BulkSyncMarketDataCommand: BulkSyncMarketDataCommandHandler,
}


@pytest.fixture(scope="module")
def booted_app():
    config_manager = ConfigManager()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    config_manager.load_json(os.path.join(base_dir, "src", "config", "app_config.json"))
    config_manager.load_json(
        os.path.join(base_dir, "src", "config", "user_config.json")
    )

    app = create_app(config_manager)

    with (
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.AsyncClient"
        ),
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.BinanceSocketManager"
        ),
    ):
        app.boot()
        yield app
        app.stop()


@pytest.mark.parametrize("command_cls,expected_handler_cls", _DATABASE_COMMANDS.items())
def test_database_command_resolves_to_its_handler(
    booted_app, command_cls, expected_handler_cls
):
    """
    Asserts every Database CQRS command/query resolves to the real handler
    class, and that the resolved handler is an instance of expected_handler_cls.
    """
    resolved_handler = booted_app.context.container.resolve(command_cls)

    assert resolved_handler is not None, (
        f"Expected container to resolve handler for {command_cls.__name__}, "
        f"but got None — check binance_bot_module.py"
    )
    assert isinstance(resolved_handler, expected_handler_cls), (
        f"Expected container.resolve({command_cls.__name__}) to produce an "
        f"instance of {expected_handler_cls.__name__}, got {type(resolved_handler).__name__}"
    )
