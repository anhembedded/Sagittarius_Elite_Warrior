"""A websocket-API server on loopback that answers requests and sends no events.

What a Spot user-data stream sees from Binance when the account is idle: a live
`ws_api` connection that acknowledges `userDataStream.subscribe` /
`unsubscribe` and then says nothing. The library's read loop (`python-binance`
`ReconnectingWebsocket`) then sits in its 10 s receive wait, the state `BUG-143`
is about. Real `websockets`, real library classes; only the peer is local.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from websockets.asyncio.server import ServerConnection, serve

_SUBSCRIPTION_ID = 0


async def _acknowledge_requests(connection: ServerConnection) -> None:
    async for message in connection:
        request = json.loads(message)
        await connection.send(
            json.dumps(
                {
                    "id": request["id"],
                    "status": 200,
                    "result": {"subscriptionId": _SUBSCRIPTION_ID},
                }
            )
        )


@asynccontextmanager
async def quiet_loopback_exchange() -> AsyncIterator[str]:
    """Yield the `ws://` URL of a server that answers and never pushes."""
    async with serve(_acknowledge_requests, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        yield f"ws://127.0.0.1:{port}"
