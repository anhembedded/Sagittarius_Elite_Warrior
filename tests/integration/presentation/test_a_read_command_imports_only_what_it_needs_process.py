"""`PRO-014` - `bot list` is a real process that imports the bots and nothing it does not need.

A short command used to pay about three seconds on a small server before its first line, nearly
all of it import work: every bounded context, the exchange SDK (with `dateparser` and `aiohttp`)
and `pyarrow` were imported to read a file. `cli_commands.json` now names the contexts a command
needs, the exchange adapters are named by path and the Parquet writer is imported by the first
export. This keeps that true in a fresh interpreter, which no in-process test can: the unit
tier has imported all of it long before the assertion runs.

Nothing here reaches an exchange.

Retire when: the application answers read commands from a resident process.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PROCESS_BUDGET_SECONDS = 90
_MODULES_PACKAGE = "Sagittarius_Elite_Warrior.src.modules"

#: Third-party packages a command that reads must not import.
_HEAVY = ("binance", "dateparser", "aiohttp", "pyarrow")

_CHILD = """
import json, sys
out = sys.argv[1]
sys.argv = ["main.py", *sys.argv[2:]]
from Sagittarius_Elite_Warrior.src.main import main
status = main()
loaded = {name.split(".")[0] for name in sys.modules} | set(sys.modules)
with open(out, "w", encoding="utf-8") as handle:
    json.dump({"status": status, "loaded": sorted(loaded)}, handle)
"""


def _run(tmp_path: Path, *args: str) -> tuple[int, set[str]]:
    data_root = tmp_path / "data"
    data_root.mkdir(exist_ok=True)
    report = tmp_path / "report.json"
    env = {
        k: v for k, v in os.environ.items() if not k.startswith(("BINANCE_", "SEW_"))
    }
    env.update(
        {
            DATA_ROOT_ENV: str(data_root),
            "QT_QPA_PLATFORM": "offscreen",
            "PYTHON_KEYRING_BACKEND": "keyring.backends.null.Keyring",
            "PYTHONPATH": str(_REPO_ROOT.parent),
        }
    )
    subprocess.run(
        [sys.executable, "-c", _CHILD, str(report), *args],
        cwd=str(_REPO_ROOT.parent),
        capture_output=True,
        text=True,
        timeout=_PROCESS_BUDGET_SECONDS,
        check=False,
        env=env,
    )
    document = json.loads(report.read_text(encoding="utf-8"))
    return document["status"], set(document["loaded"])


def _module(module_id: str) -> str:
    return f"{_MODULES_PACKAGE}.{module_id}.module"


@pytest.mark.parametrize("words", [("bot", "list"), ("bot", "show", "no-such-bot")])
def test_a_command_that_reads_bots_imports_no_exchange_sdk_and_no_unrelated_context(
    tmp_path: Path, words: tuple[str, ...]
) -> None:
    _, loaded = _run(tmp_path, *words)

    assert not (set(_HEAVY) & loaded), sorted(set(_HEAVY) & loaded)
    for built in ("bots", "trading", "market_data"):
        assert _module(built) in loaded, built
    for left_out in ("strategy", "backtesting", "alerting", "operations"):
        assert _module(left_out) not in loaded, left_out


def test_a_control_verb_gets_the_context_that_owns_host_control_and_still_no_sdk(
    tmp_path: Path,
) -> None:
    """`bot stop` asks the running host through `IHostControl`, which `operations` binds; with
    no host running it ends with the documented exit 10 rather than failing to resolve."""
    status, loaded = _run(tmp_path, "bot", "stop", "no-such-bot")

    assert status == 10
    assert _module("operations") in loaded
    assert not (set(_HEAVY) & loaded), sorted(set(_HEAVY) & loaded)


def test_status_gets_the_operations_context_and_its_suppliers(tmp_path: Path) -> None:
    status, loaded = _run(tmp_path, "status")

    assert status == 10  # no host is running on a fresh data root
    for built in ("operations", "alerting", "bots", "trading", "market_data"):
        assert _module(built) in loaded, built
    for left_out in ("strategy", "backtesting"):
        assert _module(left_out) not in loaded, left_out


def test_a_command_that_names_no_contexts_still_gets_all_of_them(
    tmp_path: Path,
) -> None:
    """The safe direction: what declares nothing keeps every context, as before the key.
    `preflight` checks the machine and ends refused (no key) without reaching an exchange."""
    _, loaded = _run(tmp_path, "preflight")

    for context in ("market_data", "trading", "strategy", "backtesting", "bots"):
        assert _module(context) in loaded, context
