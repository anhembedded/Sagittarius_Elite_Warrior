"""`BUG-263` — a task cancelled while its `python-binance` client is being created closes the client.

@details `AsyncClient.create` opens an `aiohttp` session in the constructor and closes it only when the
ping raises `Exception`; a cancel raises `CancelledError`, which is not one, so the host stop that
cancels a just-started stream printed `Unclosed client session`. These tests use the library's real
`AsyncClient` with only its ping held back (no network), and read the leak where the process reads it:
the loop's exception handler, called when the unclosed session is collected.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from unittest.mock import patch

import pytest
from binance import AsyncClient
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.closing_on_cancel import (
    create_closing_on_cancel,
)
from Sagittarius_Elite_Warrior.tests.aiohttp_sessions import Sessions, record_sessions


@pytest.fixture
def sessions(monkeypatch: pytest.MonkeyPatch) -> Sessions:
    return record_sessions(monkeypatch)


async def _cancel(task: asyncio.Task[object]) -> None:
    task.cancel()
    # Not `pytest.raises`: its captured traceback would keep the creating frame, and the client
    # in it, alive past the point where the leak is read.
    try:
        await task
    except asyncio.CancelledError:
        return
    raise AssertionError("the cancelled task finished")


def _ping_held_back(entered: asyncio.Event) -> Callable[..., Awaitable[None]]:
    async def hang(_self: AsyncClient, *_a: object, **_k: object) -> None:
        entered.set()
        await asyncio.sleep(3600)

    return hang


async def _close(client: AsyncClient) -> None:
    await client.close_connection()


def _create() -> Awaitable[AsyncClient]:
    return AsyncClient.create(api_key="key", api_secret="secret", testnet=True)


async def test_the_library_alone_leaks_the_session_of_a_cancelled_creation(
    sessions: Sessions,
) -> None:
    """The defect, so the next test is known to be able to fail."""
    entered = asyncio.Event()
    with patch.object(AsyncClient, "ping", _ping_held_back(entered)):
        task = asyncio.ensure_future(_create())
        await entered.wait()
        await _cancel(task)

    assert len(sessions.unclosed()) == 1


async def test_a_cancel_during_the_creation_closes_the_session(
    sessions: Sessions,
) -> None:
    entered = asyncio.Event()

    async def create() -> AsyncClient:
        return await _create()

    async def get_server_time(_self: AsyncClient) -> dict[str, int]:
        return {"serverTime": 0}

    async def ping_after_the_cancel(_self: AsyncClient) -> None:
        entered.set()
        await asyncio.sleep(0.05)

    with (
        patch.object(AsyncClient, "ping", ping_after_the_cancel),
        patch.object(AsyncClient, "get_server_time", get_server_time),
    ):
        task = asyncio.ensure_future(create_closing_on_cancel(create, _close, 2.0))
        await entered.wait()
        await _cancel(task)

    assert sessions.opened, "the library opened a session"
    assert sessions.unclosed() == []


async def test_a_creation_that_fails_after_the_cancel_is_not_closed_twice() -> None:
    closed: list[object] = []

    async def create() -> object:
        await asyncio.sleep(0.05)
        raise ConnectionError("down")

    async def close(client: object) -> None:
        closed.append(client)

    task = asyncio.ensure_future(create_closing_on_cancel(create, close, 2.0))
    await asyncio.sleep(0)
    await _cancel(task)

    assert closed == []


async def test_a_creation_that_outlasts_the_wait_is_logged_and_the_cancel_still_ends_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def create() -> object:
        await asyncio.sleep(3600)
        return object()

    async def close(_client: object) -> None:
        raise AssertionError("nothing was built")

    with caplog.at_level(logging.WARNING, logger="App"):
        task = asyncio.ensure_future(create_closing_on_cancel(create, close, 0.01))
        await asyncio.sleep(0)
        await _cancel(task)

    assert any("[client-create-cancelled]" in r.getMessage() for r in caplog.records)


async def test_an_uncancelled_creation_returns_its_client_and_closes_nothing() -> None:
    sentinel = object()
    closed: list[object] = []

    async def create() -> object:
        return sentinel

    async def close(client: object) -> None:
        closed.append(client)

    assert await create_closing_on_cancel(create, close, 2.0) is sentinel
    assert closed == []
