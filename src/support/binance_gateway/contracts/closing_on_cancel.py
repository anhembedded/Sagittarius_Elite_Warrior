"""`BUG-263` — create a `python-binance` async client without leaking its HTTP session when the
creating task is cancelled.

@details `AsyncClient.create` builds the client, whose constructor opens an `aiohttp` session, then
awaits a ping and a server-time read; it closes the session if those raise `Exception`. A task
cancelled during them raises `CancelledError`, which is a `BaseException`: the session is never
closed and the caller holds no handle to it, so the process prints `Unclosed client session` when
the object is collected, at host stop. A host stop that cancels a stream the same moment a session
opened it (a Stop opens the order session to cancel a bot's orders) is such a task.

The creation runs as its own task, shielded from the cancel; if the caller is cancelled while it
runs, the caller waits for it (at most `wait_seconds`), closes what it built, and re-raises.

Extension cases (`architecture-rule.md` §7.2.1): a fourth stream creates its client through the same
function; nothing here changes.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger("App.Binance")

#: The same step `websocket_teardown` gives a client to close inside the runtime's drain.
CLOSE_WAIT_SECONDS = 1.5


async def create_closing_on_cancel[ClientT](
    create: Callable[[], Awaitable[ClientT]],
    close: Callable[[ClientT], Awaitable[None]],
    wait_seconds: float = CLOSE_WAIT_SECONDS,
) -> ClientT:
    """@return the client `create` built.

    @param wait_seconds How long a cancelled caller waits for the creation to end, so it can close
    the client; the drain a cancel comes from is bounded, and a creation that outlasts it is
    logged and left (the one case that can still leak).
    @raise asyncio.CancelledError the caller was cancelled; the client, if it was built, is closed.
    """
    creating = asyncio.ensure_future(create())
    try:
        return await asyncio.shield(creating)
    except asyncio.CancelledError:
        try:
            async with asyncio.timeout(wait_seconds):
                built = await asyncio.shield(creating)
        except TimeoutError:
            logger.warning(
                "A client being created when its task was cancelled did not finish within "
                "%.1fs; its session may be left open [client-create-cancelled]",
                wait_seconds,
            )
        except Exception:
            logger.debug("Creation of a cancelled client failed", exc_info=True)
        else:
            await close(built)
        raise
