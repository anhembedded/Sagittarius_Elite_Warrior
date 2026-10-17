"""A real `main.py run` process for a test to signal and read (`EPIC-038D`).

Shared by the process-level tests (`tests/integration/presentation/test_run_process.py`)
and the sanity test that points the log scan at `run` itself. A real process, because
a signal, a lock and an exit status belong to one: a double of any of them proves the
double.

The child runs `main()` exactly as `python src/main.py run` would, inside the sanity
tier's network boundary for a child process (`BUG-199`,
`tests/sanity/fake_exchange/child_process.py`): a `sitecustomize` on its path blocks
every non-loopback connection, points every `python-binance` endpoint - mainnet
included - at the fake exchange and swaps the websocket transport, **before** `main()`
imports anything, so a venue that has a key can never reach a real host. What the child
refused is read back when it ends and fails the test: a refusal that the child's own code
catches and logs would otherwise leave it green. A test may also hand the child a patch
(`patch=`) that runs first - a stop policy that never finishes, a full disk - the way a
test plants a double in a process it cannot reach otherwise.

A child that leaves by `os._exit` (the host's forced exit) runs no `atexit`, so it
reports nothing; the in-process tests of that path use the doubles instead.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
from collections.abc import Mapping
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.tests.sanity.fake_exchange.child_process import (
    child_environment as boundary_environment,
)
from Sagittarius_Elite_Warrior.tests.sanity.fake_exchange.child_process import (
    refused_by_child,
)
from Sagittarius_Elite_Warrior.tests.sanity.fake_exchange.server import FakeServerUrls

_REPO_PARENT = Path(__file__).resolve().parents[2]

#: Booting the app and the pre-flight take seconds; nothing waits on a sleep, only on a line.
START_BUDGET_SECONDS = 90.0
STOP_BUDGET_SECONDS = 60.0

FAKE_KEY = "fake-api-key-for-a-test"
FAKE_SECRET = "SECRET-SENTINEL-6d2f81c4-never-print-me"  # noqa: S105 - a marker, not a credential

#: The one venue the tests give a key. A venue with no key is not "in use", so the
#: pre-flight and the clock probe ask the exchange about this venue and no other.
DEFAULT_CREDENTIALS: Mapping[str, str] = {
    "BINANCE_FUTURES_TESTNET_API_KEY": FAKE_KEY,
    "BINANCE_FUTURES_TESTNET_API_SECRET": FAKE_SECRET,
}

CHILD_SCRIPT = """
import os, sys
exec(os.environ.get("SEW_CHILD_PATCH", ""))
sys.argv = ["main.py", *sys.argv[1:]]
from Sagittarius_Elite_Warrior.src.main import main
sys.exit(main())
"""


def boundary_directory(data_root: Path) -> Path:
    """Where the boundary writes its `sitecustomize` and its refusal report: beside the
    data root, never in it (a test scans every file under the data root for a secret)."""
    return data_root.parent / f"{data_root.name}-boundary"


def child_environment(
    data_root: Path,
    urls: FakeServerUrls,
    credentials: Mapping[str, str],
    patch: str = "",
) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("BINANCE_", "SEW_", "CREDENTIALS_DIRECTORY"))
    }
    env.update(
        {
            DATA_ROOT_ENV: str(data_root),
            "SEW_CHILD_PATCH": patch,
            "QT_QPA_PLATFORM": "offscreen",
            # No operating-system keyring: the keys come from the environment or from nowhere.
            "PYTHON_KEYRING_BACKEND": "keyring.backends.null.Keyring",
            "PYTHONPATH": str(_REPO_PARENT),
            **credentials,
        }
    )
    return boundary_environment(boundary_directory(data_root), urls, env)


class RunChild:
    """A running `main.py <command>`, whose stdout and stderr are read as they arrive."""

    def __init__(
        self,
        data_root: Path,
        urls: FakeServerUrls,
        *args: str,
        patch: str = "",
        credentials: Mapping[str, str] | None = None,
        script: str = CHILD_SCRIPT,
        command: str = "run",
    ) -> None:
        self._boundary_directory = boundary_directory(data_root)
        env = child_environment(
            data_root,
            urls,
            DEFAULT_CREDENTIALS if credentials is None else credentials,
            patch,
        )
        self._process = subprocess.Popen(
            [sys.executable, "-c", script, command, *args],
            cwd=str(_REPO_PARENT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        self._lock = threading.Condition()
        self._stdout: list[str] = []
        self._stderr: list[str] = []
        self._readers = [
            threading.Thread(
                target=self._read,
                args=(self._process.stdout, self._stdout),
                daemon=True,
            ),
            threading.Thread(
                target=self._read,
                args=(self._process.stderr, self._stderr),
                daemon=True,
            ),
        ]
        for reader in self._readers:
            reader.start()

    def _read(self, stream: object, into: list[str]) -> None:
        assert stream is not None
        for line in stream:  # type: ignore[attr-defined]
            with self._lock:
                into.append(line)
                self._lock.notify_all()

    @property
    def pid(self) -> int:
        return self._process.pid

    @property
    def stdout(self) -> str:
        with self._lock:
            return "".join(self._stdout)

    @property
    def stderr(self) -> str:
        with self._lock:
            return "".join(self._stderr)

    @property
    def evidence(self) -> str:
        return f"--- stdout ---\n{self.stdout}\n--- stderr ---\n{self.stderr}"

    def wait_for_stdout(
        self, needle: str, timeout_s: float = START_BUDGET_SECONDS
    ) -> None:
        with self._lock:
            found = self._lock.wait_for(
                lambda: (
                    any(needle in line for line in self._stdout)
                    or self._process.poll() is not None
                ),
                timeout=timeout_s,
            )
        assert found and needle in self.stdout, (
            f"never saw {needle!r}; the process said:\n{self.evidence}"
        )

    def send(self, which: signal.Signals) -> None:
        self._process.send_signal(which)

    def finish(self, timeout_s: float = STOP_BUDGET_SECONDS) -> int:
        try:
            code = self._process.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()
            pytest.fail(f"the process did not end in {timeout_s}s:\n{self.evidence}")
        for reader in self._readers:
            reader.join(timeout=10)
        refused = refused_by_child(self._boundary_directory)
        assert refused == [], (
            f"the process tried to reach a host outside the fake exchange: {refused}"
        )
        return code

    def kill(self) -> None:
        if self._process.poll() is None:
            self._process.kill()
            self._process.wait()
