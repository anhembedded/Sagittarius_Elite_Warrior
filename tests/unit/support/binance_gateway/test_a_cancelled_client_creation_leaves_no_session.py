"""`BUG-263` — a task cancelled while its `python-binance` client is being created closes the session.

@details `AsyncClient.create` opens an `aiohttp` session in the constructor and closes it only when the
ping raises `Exception`; a cancel raises `CancelledError`, which is not one, so the host stop that
cancels a just-started stream printed `Unclosed client session`. These tests use the library's real
`AsyncClient` with only its ping held back (no network), and read the leak from each session's
`closed` flag. The cancel is delivered the way `AsyncRuntime._drain` delivers it, to every task of
the loop, so a helper task that does the creation would be cancelled too.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable, Callable
from unittest.mock import Mock, patch

import pytest
from binance import AsyncClient
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.closing_on_cancel import (
    create_closing_on_cancel,
)
from Sagittarius_Elite_Warrior.tests.aiohttp_sessions import Sessions, record_sessions
from sagittarius_engine.runtime.async_runtime.async_runtime import AsyncRuntime


@pytest.fixture
def sessions(monkeypatch: pytest.MonkeyPatch) -> Sessions:
    return record_sessions(monkeypatch)


async def _cancelled(task: asyncio.Task[object]) -> None:
    task.cancel()
    # Not `pytest.raises`: its captured traceback would keep the creating frame alive.
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
        await _cancelled(task)

    assert len(sessions.unclosed()) == 1


async def test_a_cancel_during_the_creation_closes_the_session(
    sessions: Sessions,
) -> None:
    entered = asyncio.Event()
    with patch.object(AsyncClient, "ping", _ping_held_back(entered)):
        task = asyncio.ensure_future(
            create_closing_on_cancel(
                AsyncClient.create, api_key="key", api_secret="secret", testnet=True
            )
        )
        await entered.wait()
        await _cancelled(task)

    assert sessions.opened, "the library opened a session"
    assert sessions.unclosed() == []


async def test_a_creation_that_fails_closes_the_session_and_raises_its_error(
    sessions: Sessions,
) -> None:
    async def refused(_self: AsyncClient, *_a: object, **_k: object) -> None:
        raise ConnectionError("down")

    with patch.object(AsyncClient, "ping", refused), pytest.raises(ConnectionError):
        await create_closing_on_cancel(
            AsyncClient.create, api_key="key", api_secret="secret", testnet=True
        )

    assert sessions.unclosed() == []


async def test_a_created_client_keeps_a_usable_session_and_closes_it_with_itself(
    sessions: Sessions,
) -> None:
    async def answered(_self: AsyncClient, *_a: object, **_k: object) -> None:
        return None

    async def server_time(_self: AsyncClient) -> dict[str, int]:
        return {"serverTime": 0}

    with (
        patch.object(AsyncClient, "ping", answered),
        patch.object(AsyncClient, "get_server_time", server_time),
    ):
        client = await create_closing_on_cancel(
            AsyncClient.create, api_key="key", api_secret="secret", testnet=True
        )

    assert [s.closed for s in sessions.opened] == [False]
    await client.close_connection()
    assert sessions.unclosed() == []


async def test_the_creation_gets_the_arguments_it_was_given() -> None:
    seen: dict[str, object] = {}

    async def create(**kwargs: object) -> str:
        seen.update(kwargs)
        return "client"

    assert await create_closing_on_cancel(create, testnet=True) == "client"
    assert seen["testnet"] is True
    assert "connector" in seen["session_params"]  # type: ignore[operator]


def test_the_runtime_drain_that_cancels_every_task_leaves_no_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real `AsyncRuntime.stop()`: its drain cancels every task of the loop at once, the
    way the host stop does (review of PR 710: a helper task would have been cancelled too)."""
    sessions = record_sessions(monkeypatch)
    entered = threading.Event()

    async def hang(_self: AsyncClient, *_a: object, **_k: object) -> None:
        entered.set()
        await asyncio.sleep(3600)

    runtime = AsyncRuntime(Mock())
    with patch.object(AsyncClient, "ping", hang):
        runtime.start()
        runtime.run_coroutine(
            create_closing_on_cancel(
                AsyncClient.create, api_key="key", api_secret="secret", testnet=True
            )
        )
        assert entered.wait(timeout=5.0), "the creation reached the ping"
        runtime.stop(timeout=10.0)

    assert sessions.opened, "the library opened a session"
    assert sessions.unclosed() == []
