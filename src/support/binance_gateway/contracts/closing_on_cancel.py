"""`BUG-263` — create a `python-binance` async client without leaking its HTTP session when the
creating task is cancelled.

@details `AsyncClient.create` builds the client, whose constructor opens an `aiohttp` session, then
awaits a ping and a server-time read; it closes the session if those raise `Exception`. A task
cancelled during them raises `CancelledError`, which is a `BaseException`: the session is never
closed and the caller holds no handle to it, so the process prints `Unclosed client session` when
the object is collected, at host stop. A host stop that cancels a stream the same moment a session
opened it (a Stop opens the order session to cancel a bot's orders) is such a task.

`AsyncRuntime`'s drain cancels every task of the loop, so a helper task that does the creation is
cancelled too and cannot be waited for. What survives is the handle this module gives the caller
before the library starts: the `aiohttp` connector, passed in as the session's own. A session is
closed exactly when its connector is (`ClientSession.closed`), and a session that is closed warns of
nothing, so closing the connector on any exit before the client is returned ends the leak. After
the client is returned the session owns the connector and closes it with itself.

Extension cases (`architecture-rule.md` §7.2.1): a fourth stream creates its client through the same
function; nothing here changes.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from aiohttp import TCPConnector


async def create_closing_on_cancel[ClientT](
    create: Callable[..., Awaitable[ClientT]], **kwargs: object
) -> ClientT:
    """@return the client `create(**kwargs)` built, whose session uses a connector made here.

    @param create `AsyncClient.create`, called with `kwargs` and the connector as `session_params`.
    @raise BaseException whatever `create` raised, a cancel included, after the connector is closed.
    """
    connector = TCPConnector()
    try:
        return await create(**kwargs, session_params={"connector": connector})
    except BaseException:
        await connector.close()
        raise
