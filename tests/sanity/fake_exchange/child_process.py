"""`BUG-199` — the same network boundary, for a process the tier launches.

`test_self_check_process.py` starts the real entry point as a subprocess, so the
in-process block and endpoint redirect of `conftest.py` do not exist there. The
child opens the real window, whose charts sync an empty store, and it did that
against `api.binance.com` and `testnet.binance.vision`.

A child cannot be monkeypatched, so it is configured the way any Python process
is configured from outside: a `sitecustomize` module on its `PYTHONPATH`. That
module (written to the test's own directory, never to the repository) calls
`install()` below before the application is imported, applying the very same
three pieces the in-process boundary uses — non-loopback block, endpoint
redirect, websocket transport. What the child refused is written to a file the
parent reads, because a refusal the child's own code catches and logs would
otherwise leave the test green.

Retire when: the sanity tier launches no process that talks to an exchange.
"""

from __future__ import annotations

import atexit
import json
import os
from collections.abc import Mapping
from contextlib import ExitStack
from pathlib import Path

import pytest

from .binance_endpoints import binance_clients_pointed_at
from .server import FakeServerUrls
from .stream_transport import fake_websocket_transport

_SITECUSTOMIZE = "from fake_exchange.child_process import install\n\ninstall()\n"
_SPOT = "SEW_FAKE_EXCHANGE_SPOT"
_FUTURES = "SEW_FAKE_EXCHANGE_FUTURES"
_MARGIN = "SEW_FAKE_EXCHANGE_MARGIN"
_REFUSED_LOG = "SEW_FAKE_EXCHANGE_REFUSED_LOG"

_SANITY_DIR = Path(__file__).resolve().parents[1]
_WORKSPACE = Path(__file__).resolve().parents[3].parent


def child_environment(
    workdir: Path, urls: FakeServerUrls, base: Mapping[str, str]
) -> dict[str, str]:
    """`base` plus what makes a Python child honour the boundary."""
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "sitecustomize.py").write_text(_SITECUSTOMIZE, encoding="utf-8")
    search_path = os.pathsep.join(
        [str(workdir), str(_SANITY_DIR), str(_WORKSPACE), base.get("PYTHONPATH", "")]
    )
    return {
        **base,
        "PYTHONPATH": search_path,
        _SPOT: urls.spot,
        _FUTURES: urls.futures,
        _MARGIN: urls.margin,
        _REFUSED_LOG: str(workdir / "refused.json"),
    }


def refused_by_child(workdir: Path) -> list[str]:
    """Every non-loopback destination the child tried to reach, as it exited."""
    log = workdir / "refused.json"
    return json.loads(log.read_text(encoding="utf-8")) if log.exists() else []


def install() -> None:
    """Runs inside the child, from its `sitecustomize`, until the process exits."""
    from Sagittarius_Elite_Warrior.tests.unit import network_block

    urls = FakeServerUrls(
        spot=os.environ[_SPOT],
        futures=os.environ[_FUTURES],
        margin=os.environ[_MARGIN],
    )
    patcher = pytest.MonkeyPatch()
    refused = network_block.install(patcher)
    boundary = ExitStack()
    boundary.enter_context(binance_clients_pointed_at(urls))
    boundary.enter_context(fake_websocket_transport())

    # The registration is what keeps the stack, and so every patch in it, alive:
    # an `ExitStack` that is garbage-collected unwinds the contexts it holds.
    atexit.register(boundary.close)

    def report() -> None:
        Path(os.environ[_REFUSED_LOG]).write_text(
            json.dumps(sorted(set(refused))), encoding="utf-8"
        )

    atexit.register(report)
