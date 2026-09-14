"""One place that knows how this module's CLI reaches the dispatcher.

Every test in this package needs the same thing: an `App` whose container hands
back a dispatcher the test controls. Written once here rather than four times,
for a reason that is not tidiness — it is the whole cause of `BUG-119`.

`EPIC-025` PR 0.4a-2 changed the CLI to dispatch through `ICommandDispatcher`
instead of `App.dispatch`. Four test files still mocked `app.dispatch`, which
the new code never calls, so their mocks stopped intercepting anything. Nine of
them merely failed. The tenth — `test_stream_cmd.py` — walked past the
`response.success` check on a truthy `Mock` and into `execute_stream()`'s
`while True: time.sleep(1)`, and **hung the entire gate at 96% with nothing
reported `FAILED`**, three runs in a row.

With the knowledge of *where* dispatch happens in one file, the next change to
that seam breaks one import, not five mocks — and the one that hangs cannot be
the one that is forgotten.

`Mock(spec=App)` alone is what makes this dangerous rather than merely wrong:
`app.container.resolve(anything)` returns a fresh permissive `Mock`, so an
unconfigured dispatcher reports success for every command it is handed.
"""

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from sagittarius_engine import App


def dispatching_app(
    *, raises: Exception | None = None, success: bool = True, message: str = ""
) -> tuple[Mock, Mock]:
    """An `App` and the dispatcher its container resolves, both controlled.

    `raises` makes `dispatch()` fail the way a real network or database error
    does. Otherwise it returns a response carrying `success` and `message`,
    which is what the stream commands read; the sync command ignores the result
    and reports failure only by exception.

    Resolving any port other than `ICommandDispatcher` raises `KeyError` on
    purpose: a wrong resolve should be loud, not plausible.
    """
    dispatcher = Mock(spec=ICommandDispatcher)
    if raises is not None:
        dispatcher.dispatch.side_effect = raises
    else:
        response = Mock()
        response.success = success
        response.message = message
        dispatcher.dispatch.return_value = response

    app = Mock(spec=App)
    app.container.resolve.side_effect = lambda port: {ICommandDispatcher: dispatcher}[
        port
    ]
    return app, dispatcher
