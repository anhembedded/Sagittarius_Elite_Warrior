"""`EPIC-038G` — what a headless process leaves in its log.

An unattended process is judged by its log: the CI run-log scan reads
`- (WARNING|ERROR|CRITICAL) -` records, a monitor parses the health line, and a
secret that reaches either is leaked for good. This runs the shared composition
the `run` host will wrap (`create_app`, `boot`, one health line, `stop`) in a
fresh interpreter with **PySide6 blocked**, on the **real logging
configuration** (`StdLogger` from the shipped config, never `basicConfig`), with
canary credentials in the environment, and reads what came out.

Four facts:

1. no WARNING/ERROR/CRITICAL record and no "uncollectable objects" line, so the
   scan stays quiet on a healthy headless run;
2. the health line arrives as an INFO record in the Engine's fixed field order
   and the parser reads it back from that real output;
3. no canary secret appears anywhere in stdout or stderr;
4. a plain run creates no log file under the data root.

`EPIC-038D` points this at `run` itself when the host exists; `run` adds a loop,
not a different logging path.

Retire when: the `run` host's own sanity test covers the same four facts.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_line import (
    BotCount,
    HealthLine,
    health_lines_in,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROCESS_BUDGET_SECONDS = 60

#: Distinctive enough that a substring hit cannot be a coincidence.
_CANARY_KEY = "CANARY-KEY-5f1c9e0a-never-log-me"
_CANARY_SECRET = "CANARY-SECRET-b27d44c1-never-log-me"  # noqa: S105 - a fake, planted to prove it is never logged
_CREDENTIAL_VARIABLES = tuple(
    f"BINANCE_{market}_{venue}_API_{part}"
    for market in ("SPOT", "FUTURES")
    for venue in ("TESTNET", "MAINNET")
    for part in ("KEY", "SECRET")
)

_PROBLEM_RECORD = re.compile(
    r"- (WARNING|ERROR|CRITICAL) -|uncollectable objects at shutdown"
)
_HEALTH_RECORD = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - App\.Operations - INFO - \[health\] state=",
    re.MULTILINE,
)

_EXPECTED_HEALTH = HealthLine(
    state=HostState.SERVING,
    up_s=7,
    bots=(BotCount("running", 2), BotCount("paused", 0)),
    tick_age_s=1,
    stream_age_s=None,
    skew_ms=-3,
    rss_mb=250,
)

_HEADLESS_BOOT = """
import logging, sys
for _name in ("PySide6", "shiboken6", "pyqtgraph"):
    sys.modules[_name] = None

from Sagittarius_Elite_Warrior.src.modules.operations.application.health_line import (
    BotCount, HealthLine, log_health_line,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import HostState
from Sagittarius_Elite_Warrior.src.shell.app_config import load_app_config
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app

config_manager, _ = load_app_config(["run"])
app = create_app(config_manager)
app.boot()
log_health_line(
    logging.getLogger("App.Operations"),
    HealthLine(
        state=HostState.SERVING, up_s=7,
        bots=(BotCount("running", 2), BotCount("paused", 0)),
        tick_age_s=1, stream_age_s=None, skew_ms=-3, rss_mb=250,
    ),
)
app.stop()
print("HEADLESS_BOOT_DONE")
"""


def _run_headless_boot(data_root: Path) -> subprocess.CompletedProcess[str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("BINANCE_", "SEW_"))
    }
    env.update({DATA_ROOT_ENV: str(data_root), "QT_QPA_PLATFORM": "offscreen"})
    for name in _CREDENTIAL_VARIABLES:
        env[name] = _CANARY_KEY if name.endswith("_KEY") else _CANARY_SECRET
    return subprocess.run(
        [sys.executable, "-c", _HEADLESS_BOOT],
        cwd=str(_REPO_ROOT.parent),
        capture_output=True,
        text=True,
        timeout=_PROCESS_BUDGET_SECONDS,
        check=False,
        env=env,
    )


@dataclass(frozen=True, slots=True)
class _Boot:
    result: subprocess.CompletedProcess[str]
    data_root: Path

    @property
    def log(self) -> str:
        return self.result.stdout + self.result.stderr

    @property
    def evidence(self) -> str:
        return (
            f"exit {self.result.returncode}\n--- stdout ---\n{self.result.stdout}\n"
            f"--- stderr ---\n{self.result.stderr}"
        )


@pytest.fixture(scope="module")
def boot(tmp_path_factory: pytest.TempPathFactory) -> Iterator[_Boot]:
    """One headless boot, read by all four facts."""
    data_root = tmp_path_factory.mktemp("headless_data_root")
    yield _Boot(_run_headless_boot(data_root), data_root)


def test_a_headless_boot_leaves_no_unexpected_warning_or_error_in_the_log(
    boot: _Boot,
) -> None:
    assert boot.result.returncode == 0, boot.evidence
    assert "HEADLESS_BOOT_DONE" in boot.result.stdout, boot.evidence
    problems = _PROBLEM_RECORD.findall(boot.log)
    assert not problems, f"the run-log scan would fail: {problems}\n{boot.evidence}"


def test_the_health_line_in_the_real_log_output_parses_back(boot: _Boot) -> None:
    assert _HEALTH_RECORD.search(boot.result.stdout), boot.evidence
    assert health_lines_in(boot.result.stdout) == (_EXPECTED_HEALTH,), boot.evidence


def test_no_credential_reaches_the_log(boot: _Boot) -> None:
    assert boot.result.returncode == 0, boot.evidence
    assert _CANARY_KEY not in boot.log, "an API key reached the log"
    assert _CANARY_SECRET not in boot.log, "an API secret reached the log"


def test_a_plain_headless_run_writes_no_log_file(boot: _Boot) -> None:
    assert boot.result.returncode == 0, boot.evidence
    logs_dir = boot.data_root / "logs"
    written = sorted(os.listdir(logs_dir)) if logs_dir.exists() else []
    assert written == [], f"a plain run wrote log files: {written}"
