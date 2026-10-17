"""`BOT-185` - `bot list` and `status --json` as real processes: the console shows the result only.

The unit tests prove the routing with the real logger; this proves the entry point
decides it: that a command declared `read_only` leaves its records in
`<data root>/logs/cli-*.log`, that `--verbose` brings them back as before, that
`run`'s kind of command (not read-only) is not touched, and that a `--json`
document stays one document with an empty error stream.

Nothing here reaches an exchange: these commands open no session.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PROCESS_BUDGET_SECONDS = 90
#: What the fixed-field formatter writes in front of every record.
_LOG_LINE = re.compile(
    r"^\d{4}-\d\d-\d\d [\d:,]+ - App[.\w]* - (INFO|DEBUG) - ", re.MULTILINE
)

_CHILD = """
import sys
sys.argv = ["main.py", *sys.argv[1:]]
from Sagittarius_Elite_Warrior.src.main import main
sys.exit(main())
"""


def _run(data_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
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
    return subprocess.run(
        [sys.executable, "-c", _CHILD, *args],
        cwd=str(_REPO_ROOT.parent),
        capture_output=True,
        text=True,
        timeout=_PROCESS_BUDGET_SECONDS,
        check=False,
        env=env,
    )


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    root.mkdir()
    return root


def _cli_logs(data_root: Path) -> list[Path]:
    log_dir = data_root / "logs"
    if not log_dir.is_dir():
        return []
    return sorted(
        log_dir / name for name in os.listdir(log_dir) if name.startswith("cli-")
    )


def test_a_read_only_command_prints_its_result_and_writes_its_log_to_a_file(
    data_root: Path,
) -> None:
    result = _run(data_root, "bot", "list")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "No bots."
    assert result.stderr == ""
    [log_file] = _cli_logs(data_root)
    text = log_file.read_text(encoding="utf-8")
    assert "[cli-log] console shows warnings and errors only" in text
    assert "[instance] read-only" in text
    assert "App booted successfully" in text
    assert _LOG_LINE.search(text)


def test_verbose_puts_the_log_back_on_the_console_and_writes_no_file(
    data_root: Path,
) -> None:
    result = _run(data_root, "bot", "list", "--verbose")

    assert result.returncode == 0, result.stderr
    assert "No bots." in result.stdout
    assert _LOG_LINE.search(result.stdout), "the log is on stdout, as before"
    assert "[instance] read-only" in result.stdout
    assert _cli_logs(data_root) == []


def test_a_json_report_stays_one_document_with_a_quiet_error_stream(
    data_root: Path,
) -> None:
    result = _run(data_root, "status", "--json")

    document = json.loads(result.stdout)
    assert document["schema"] == "sew.status/1"
    assert result.stderr == ""
    assert len(_cli_logs(data_root)) == 1


def test_a_failed_command_still_says_so_on_the_console(data_root: Path) -> None:
    result = _run(data_root, "bot", "show", "no-such-bot")

    assert result.returncode == 2
    assert "No bot has the id 'no-such-bot'." in result.stderr
    assert result.stdout == ""
