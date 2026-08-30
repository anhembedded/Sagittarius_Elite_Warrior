"""`EPIC-018F` — `execute_stream()`'s headless (non-interactive) CLI path.

Only covers the fix this task made: a real `dispatch()` failure must be
reported and exit non-zero instead of propagating as an uncaught
traceback. Does not cover the post-start `while True: sleep` loop — that
path only runs after a successful start and isn't part of this fix.
"""

from argparse import Namespace
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.use_cases.stream.start_live_stream import (
    StartLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.stream_cmd import execute_stream
from sagittarius_engine import App


def _args(**overrides) -> Namespace:
    base = {"symbols": "BTCUSDT", "interval": "1m"}
    base.update(overrides)
    return Namespace(**base)


def test_execute_stream_dispatch_raises_reports_and_exits(capsys):
    app = Mock(spec=App)
    app.dispatch.side_effect = ConnectionError("Network error")

    with pytest.raises(SystemExit) as exc_info:
        execute_stream(app, _args())

    assert exc_info.value.code == 1
    args, _ = app.dispatch.call_args
    assert args[0] == StartLiveStreamCommand
    captured = capsys.readouterr()
    assert "❌ Failed to start stream: Network error" in captured.out
