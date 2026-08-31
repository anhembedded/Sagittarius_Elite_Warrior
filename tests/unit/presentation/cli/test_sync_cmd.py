"""`EPIC-018F` — `execute_sync()`'s headless (non-interactive) CLI path.

Only covers the fix this task made: a real `dispatch()` failure must be
reported and exit non-zero instead of propagating as an uncaught
traceback — same class of bug `sync_cli_handler.py` (interactive path)
already had fixed, that this headless sibling still had.
"""

from argparse import Namespace
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.sync_cmd import execute_sync
from sagittarius_engine import App


def _args(**overrides) -> Namespace:
    base = {"symbols": "BTCUSDT", "interval": "1m", "days": 30}
    base.update(overrides)
    return Namespace(**base)


def test_execute_sync_dispatches_command(capsys):
    app = Mock(spec=App)
    app.dispatch.return_value = None

    execute_sync(app, _args())

    args, _ = app.dispatch.call_args
    assert args[0] == SyncMarketDataCommand


def test_execute_sync_dispatch_raises_reports_and_exits(capsys):
    app = Mock(spec=App)
    app.dispatch.side_effect = ConnectionError("Network error")

    with pytest.raises(SystemExit) as exc_info:
        execute_sync(app, _args())

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "❌ Sync failed: Network error" in captured.out
