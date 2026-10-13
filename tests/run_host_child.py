"""A real `main.py run` process for a test to signal and read (`EPIC-038D`).

Shared by the process-level tests (`tests/integration/presentation/test_run_process.py`)
and the sanity test that points the log scan at `run` itself. A real process, because
a signal, a lock and an exit status belong to one: a double of any of them proves the
double.

The child runs `main()` exactly as `python src/main.py run` would. The only thing moved
is where the exchange is: `python-binance`'s URLs are pointed at the fake exchange
(`tests/sanity/binance_fake_server.py`) **before** `main()` imports anything, mainnet
included, so a venue that has a key can never reach a real host. A test may also hand
the child a patch (`patch=`) that runs first - a stop policy that never finishes, a
full disk - the way a test plants a double in a process it cannot reach otherwise.
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
from binance.client import Client
Client.FUTURES_TESTNET_URL = os.environ["SEW_FAKE_FUTURES"]
Client.FUTURES_URL = os.environ["SEW_FAKE_FUTURES"]
Client.API_URL = os.environ["SEW_FAKE_SPOT"]
Client.API_TESTNET_URL = os.environ["SEW_FAKE_SPOT"]
Client.MARGIN_API_URL = os.environ["SEW_FAKE_MARGIN"]
exec(os.environ.get("SEW_CHILD_PATCH", ""))
sys.argv = ["main.py", *sys.argv[1:]]
from Sagittarius_Elite_Warrior.src.main import main
sys.exit(main())
"""


class FakeExchangeUrls:
    """The three base URLs the child is pointed at (a `FakeServerUrls` has them)."""

    futures: str
    spot: str
    margin: str


def child_environment(
    data_root: Path,
    urls: FakeExchangeUrls,
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
            "SEW_FAKE_FUTURES": urls.futures,
            "SEW_FAKE_SPOT": urls.spot,
            "SEW_FAKE_MARGIN": urls.margin,
            "SEW_CHILD_PATCH": patch,
            "QT_QPA_PLATFORM": "offscreen",
            # No operating-system keyring: the keys come from the environment or from nowhere.
            "PYTHON_KEYRING_BACKEND": "keyring.backends.null.Keyring",
            "PYTHONPATH": str(_REPO_PARENT),
            **credentials,
        }
    )
    return env


class RunChild:
    """A running `main.py <command>`, whose stdout and stderr are read as they arrive."""

    def __init__(
        self,
        data_root: Path,
        urls: FakeExchangeUrls,
        *args: str,
        patch: str = "",
        credentials: Mapping[str, str] | None = None,
        script: str = CHILD_SCRIPT,
        command: str = "run",
    ) -> None:
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
        return code

    def kill(self) -> None:
        if self._process.poll() is None:
            self._process.kill()
            self._process.wait()
