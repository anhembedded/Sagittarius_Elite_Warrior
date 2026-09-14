"""`execute_stream()`'s headless (non-interactive) CLI path.

Covers the one thing that can be covered safely: a real dispatch failure must be
reported and exit non-zero instead of propagating as an uncaught traceback
(`EPIC-018F`).

**The success path is deliberately not covered, and that is load-bearing.**
After a successful start, `execute_stream()` enters `while True: time.sleep(1)`
by design — it is a foreground CLI that blocks until Ctrl+C. A test that reaches
that line does not fail, it **hangs forever**, and pytest has no timeout
configured, so the whole run stalls with no failure reported.

That is not hypothetical. `EPIC-025` PR 0.4a-2 changed `execute_stream()` to
dispatch through `ICommandDispatcher` instead of `App.dispatch`, and this test
kept mocking `app.dispatch` — which the new code never calls. The mock stopped
raising, `response.success` became a truthy `Mock`, and the test walked into the
infinite loop. The whole gate then stalled at 96% with nothing reported
`FAILED`, three runs in a row, and it took a `py-spy` dump to find. `BUG-119`
has the full account.

So the mock below must intercept **the call the code actually makes**. If a
future change moves dispatch somewhere else again, update this fixture in the
same commit — or this test becomes a hang, not a failure.
"""

from argparse import Namespace

import pytest
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.start_live_stream import (
    StartLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.cli.stream_cmd import (
    execute_stream,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.market_data.cli.dispatching_app import (
    dispatching_app,
)


def _args(**overrides) -> Namespace:
    base = {"symbols": "BTCUSDT", "interval": "1m"}
    base.update(overrides)
    return Namespace(**base)


def test_execute_stream_dispatch_raises_reports_and_exits(capsys):
    app, dispatcher = dispatching_app(raises=ConnectionError("Network error"))

    with pytest.raises(SystemExit) as exc_info:
        execute_stream(app, _args())

    assert exc_info.value.code == 1
    args, _ = dispatcher.dispatch.call_args
    assert args[0] == StartLiveStreamCommand
    captured = capsys.readouterr()
    assert "❌ Failed to start stream: Network error" in captured.out


def test_execute_stream_exits_when_the_engine_refuses_to_start(capsys):
    """A refusal is a response, not an exception: `success=False` must exit
    non-zero **before** the blocking loop, not stream nothing forever.

    This case is why the refusal branch is worth a test of its own — it is the
    one path where `execute_stream()` returns a result and still must not reach
    `while True`.
    """
    app, _dispatcher = dispatching_app(success=False, message="already streaming")

    with pytest.raises(SystemExit) as exc_info:
        execute_stream(app, _args())

    assert exc_info.value.code == 1
    assert "Failed to start stream: already streaming" in capsys.readouterr().out
