"""`BUG-143` — ending a `python-binance` socket and client inside the runtime's drain.

Two waits in the library outlast `AsyncRuntime`'s 5 s drain, and both end in a
stream task reported as left behind:

  · **The unsubscribe nobody can answer.** `KeepAliveWebsocket.__aexit__` on a
    Spot user stream sends `userDataStream.unsubscribe` through the client's
    `ws_api` and waits `TIMEOUT` (10 s) for the reply. The reply is delivered
    by `ws_api`'s read loop, and `AsyncRuntime.stop()` cancels every task at
    once, that read loop included: the reply cannot come. This is the
    owner's Spot Mainnet log, where the stream printed none of its own lines.
  · **The close that polls for a receive.** `ReconnectingWebsocket.__aexit__`
    (so `AsyncClient.close_connection()` for `ws_api`, and a Futures socket's
    exit) sets `EXITING` and polls until its read loop notices, which is only
    between receives, up to `TIMEOUT` on an idle connection. It bites when one
    stream is stopped (a reconnect, trading switched off) while the loop keeps
    running, so the read loop is alive and quiet.

The first is bounded: leaving the subscription is a courtesy, since closing the
connection ends it on the exchange. The second is removed: the read loop is
cancelled, the library's own shutdown path for it (`_read_loop` handles
`CancelledError`, signals its queue and returns), which unlike closing the
socket under it logs nothing at ERROR. The library keeps no handle to that task
(`call_soon_threadsafe` returns a `Handle`), so it is found among the loop's
tasks by the coroutine it runs and the websocket it belongs to; when it is not
found, the bounds below still end the step.

@par Extension cases (`architecture-rule.md` §7.2.1)
A third venue stream leaves its socket with `close_socket` and ends its client
with `close_client`; nothing here changes.
"""

from __future__ import annotations

import asyncio
import logging

from binance import AsyncClient
from binance.ws.reconnecting_websocket import ReconnectingWebsocket

logger = logging.getLogger("App.UserDataStream")

#: Each step's bound, below the 5 s `AsyncRuntime.stop()` allows a task in all.
STEP_SECONDS = 1.5

_READ_LOOP_CODE = ReconnectingWebsocket._read_loop.__code__


def stop_read_loop(websocket: ReconnectingWebsocket | None) -> bool:
    """Cancel `websocket`'s read loop so its close does not wait for a receive.

    Returns whether a running read loop was found and cancelled. A websocket
    that has none (a `ws_api` subscription reads through the client's loop, a
    socket already closed) is not an error.
    """
    if websocket is None:
        return False
    for task in asyncio.all_tasks():
        coroutine = task.get_coro()
        frame = getattr(coroutine, "cr_frame", None)
        if getattr(coroutine, "cr_code", None) is not _READ_LOOP_CODE or frame is None:
            continue
        if frame.f_locals.get("self") is websocket and not task.cancelling():
            task.cancel()
            return True
    return False


async def close_socket(socket: ReconnectingWebsocket) -> None:
    """Leave `socket` within `STEP_SECONDS`.

    @details A timeout is not a failure to report loudly: the reply the exit
    waits for travels through a read loop the runtime may have cancelled with
    this task, and the client's close that follows ends the subscription.
    """
    stop_read_loop(socket)
    try:
        async with asyncio.timeout(STEP_SECONDS):
            await socket.close()
    except TimeoutError:
        logger.info(
            "User data stream socket did not confirm leaving within %.1fs; "
            "closing the connection ends it.",
            STEP_SECONDS,
        )


async def close_client(client: AsyncClient) -> None:
    """Close `client`'s HTTP session and `ws_api` within `STEP_SECONDS`."""
    stop_read_loop(client.ws_api)
    try:
        async with asyncio.timeout(STEP_SECONDS):
            await client.close_connection()
    except TimeoutError:
        logger.warning(
            "User data stream AsyncClient did not close within %.1fs.", STEP_SECONDS
        )
        return
    logger.info("User data stream AsyncClient connection closed.")
