"""`main.py` as a real process: its exit status and its stdout are what a script reads (`EPIC-038B`).

The unit tests prove each piece (the outcome table, the renderers, the entry
point's branches) with doubles. This one proves the pieces are wired: a child
process runs `main()` exactly as `python src/main.py` would, against the fake
exchange (`tests/sanity/binance_fake_server.py`, only the endpoint moves), and
the test reads `$?`, stdout and stderr. Nothing here is a live exchange.

The child is `python -c` with a three-line preamble that moves `python-binance`'s
testnet URLs to the fake server, then calls the real `main()` and exits with its
return value — the same `sys.exit(main())` the file's `__main__` block does.

**The secret.** The environment carries a recognisable fake secret; the output
of every run, text and JSON, is searched for it (`test_no_secret_reaches_a_json_report`).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sanity"))
from binance_fake_server import FakeServerUrls, run_binance_fake_server

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PROCESS_BUDGET_SECONDS = 90

_FAKE_KEY = "fake-api-key-for-a-test"
_FAKE_SECRET = "SECRET-SENTINEL-4c1d9e7a-never-print-me"  # noqa: S105 - a marker, not a credential

_CHILD = """
import os, sys
from binance.client import Client
Client.FUTURES_TESTNET_URL = os.environ["SEW_FAKE_FUTURES"]
Client.API_URL = os.environ["SEW_FAKE_SPOT"]
Client.MARGIN_API_URL = os.environ["SEW_FAKE_MARGIN"]
sys.argv = ["main.py", *sys.argv[1:]]
from Sagittarius_Elite_Warrior.src.main import main
sys.exit(main())
"""


@pytest.fixture
def exchange() -> Iterator[FakeServerUrls]:
    with run_binance_fake_server() as urls:
        yield urls


def _run(
    tmp_path: Path, urls: FakeServerUrls, *args: str, with_keys: bool = True
) -> subprocess.CompletedProcess[str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("BINANCE_")
    }
    env.update(
        {
            DATA_ROOT_ENV: str(tmp_path),
            "SEW_FAKE_FUTURES": urls.futures,
            "SEW_FAKE_SPOT": urls.spot,
            "SEW_FAKE_MARGIN": urls.margin,
            "QT_QPA_PLATFORM": "offscreen",
            # No operating-system keyring: the keys come from the environment
            # or from nowhere, so "no credentials" is deterministic anywhere.
            "PYTHON_KEYRING_BACKEND": "keyring.backends.null.Keyring",
        }
    )
    if with_keys:
        env["BINANCE_FUTURES_TESTNET_API_KEY"] = _FAKE_KEY
        env["BINANCE_FUTURES_TESTNET_API_SECRET"] = _FAKE_SECRET
    return subprocess.run(
        [sys.executable, "-c", _CHILD, *args],
        cwd=str(_REPO_ROOT.parent),
        capture_output=True,
        text=True,
        timeout=_PROCESS_BUDGET_SECONDS,
        check=False,
        env={**env, "PYTHONPATH": str(_REPO_ROOT.parent)},
    )


def test_a_healthy_exchange_status_exits_zero_and_prints_the_text_report(
    tmp_path: Path, exchange: FakeServerUrls
) -> None:
    result = _run(tmp_path, exchange, "exchange-status")

    assert result.returncode == int(ExitCode.SUCCESS), result.stderr
    assert "Connection: ✔" in result.stdout


def test_exchange_status_json_is_the_only_thing_on_stdout(
    tmp_path: Path, exchange: FakeServerUrls
) -> None:
    result = _run(tmp_path, exchange, "exchange-status", "--json")

    assert result.returncode == int(ExitCode.SUCCESS), result.stderr
    document = json.loads(result.stdout)  # a log line before it would raise
    assert document["schema"] == "sew.exchange-status/1"
    assert document["data"]["reachable"] is True
    assert document["data"]["failure"] is None


def test_no_secret_reaches_a_json_report(
    tmp_path: Path, exchange: FakeServerUrls
) -> None:
    """The status holds a venue, balances and a failure kind, and no credential;
    this runs the command with a recognisable secret in the environment and
    searches every byte it wrote. A leak through the report, a log line or a
    traceback fails here."""
    for args in (
        ("exchange-status", "--json"),
        ("exchange-status",),
        ("exchange-status", "--format", "json"),
    ):
        result = _run(tmp_path, exchange, *args)

        assert _FAKE_SECRET not in result.stdout, args
        assert _FAKE_SECRET not in result.stderr, args
        assert _FAKE_KEY not in result.stdout, args


def test_a_refused_key_exits_with_the_configuration_code_and_still_prints_the_report(
    tmp_path: Path, exchange: FakeServerUrls
) -> None:
    exchange.keys.known = {"some-other-key"}

    result = _run(tmp_path, exchange, "exchange-status", "--json")

    assert result.returncode == int(ExitCode.CONFIGURATION), result.stderr
    document = json.loads(result.stdout)
    assert document["data"]["reachable"] is False
    assert document["data"]["failure"] == "key_rejected"
    assert _FAKE_SECRET not in result.stdout + result.stderr


def test_missing_credentials_exit_with_the_configuration_code(
    tmp_path: Path, exchange: FakeServerUrls
) -> None:
    result = _run(tmp_path, exchange, "exchange-status", "--json", with_keys=False)

    assert result.returncode == int(ExitCode.CONFIGURATION), result.stderr
    assert json.loads(result.stdout)["data"]["failure"] == "not_configured"


def test_an_unknown_format_exits_with_the_usage_code_and_prints_no_report(
    tmp_path: Path, exchange: FakeServerUrls
) -> None:
    result = _run(tmp_path, exchange, "exchange-status", "--format", "yaml")

    assert result.returncode == int(ExitCode.USAGE)
    assert "unknown format 'yaml'" in result.stderr
    assert "Connection" not in result.stdout


def test_a_bare_invocation_prints_the_help_and_exits_two(
    tmp_path: Path, exchange: FakeServerUrls
) -> None:
    """D8: the default is safe in every environment — no window, no prompt."""
    result = _run(tmp_path, exchange)

    assert result.returncode == int(ExitCode.USAGE)
    assert "gui" in result.stdout
    assert "shell" in result.stdout
    assert "exchange-status" in result.stdout
    assert exchange.requests == []
