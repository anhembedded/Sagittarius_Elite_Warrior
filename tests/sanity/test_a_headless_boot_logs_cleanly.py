"""`EPIC-038G`, pointed at `run` by `EPIC-038D` - what a headless host leaves in its log.

An unattended process is judged by its log: the CI run-log scan reads
`- (WARNING|ERROR|CRITICAL) -` records, a monitor parses the health line, and a
secret that reaches either is leaked for good. This starts `main.py run` - the real
entry point, the real composition root, the real logging configuration (`StdLogger`
from the shipped config, never `basicConfig`) - in a fresh interpreter with **PySide6
blocked**, over the fake exchange, with canary credentials in the environment, lets it
serve until it has written health lines, stops it with a real SIGTERM, and reads what
came out.

Four facts, as `EPIC-038G` stated them for the shared composition `run` wraps (and, from
`EPIC-038E`, a fifth at the end of this file: the same canary provisioned as a systemd
credential and as a permission-checked file):

1. no WARNING/ERROR/CRITICAL record and no "uncollectable objects" line, except the one
   WARNING `run` must write at start - *"no alert channel is configured for bot events;
   nothing will tell you if a bot halts"* (`EPIC-038D`) - until `EPIC-036B` routes bot
   events to a person. It is named below; a second one, or any other, fails;
2. the health line arrives as an INFO record in the Engine's fixed field order and the
   parser reads it back from `run`'s real stdout, for the serving state and the draining one;
3. no canary secret appears anywhere in stdout or stderr, **after** the run read the
   canary through the real credential provider (a clean log alone proves nothing if no
   credential path ran): the child counts what the provider resolved and says so at exit;
4. a plain run creates no log file under the data root.

Retire when: the `run` host stops being the headless entry point.
"""

from __future__ import annotations

import os
import re
import signal
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_line import (
    health_lines_in,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)
from Sagittarius_Elite_Warrior.tests.run_host_child import CHILD_SCRIPT, RunChild

sys.path.insert(0, str(Path(__file__).resolve().parent))
from binance_fake_server import run_binance_fake_server

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="stops the host with a POSIX SIGTERM; Windows' Ctrl-Break needs a Windows runner",
)

#: Distinctive enough that a substring hit cannot be a coincidence.
_CANARY_KEY = "CANARY-KEY-5f1c9e0a-never-log-me"
_CANARY_SECRET = "CANARY-SECRET-b27d44c1-never-log-me"  # noqa: S105 - a fake, planted to prove it is never logged
_CREDENTIALS = {
    "BINANCE_FUTURES_TESTNET_API_KEY": _CANARY_KEY,
    "BINANCE_FUTURES_TESTNET_API_SECRET": _CANARY_SECRET,
}

_PROBLEM_RECORD = re.compile(
    r"^.* - (WARNING|ERROR|CRITICAL) - .*$|^.*uncollectable objects at shutdown.*$",
    re.MULTILINE,
)
#: The one WARNING a healthy `run` writes (`EPIC-038D`); `EPIC-036B` removes it.
_EXPECTED_WARNING = "[alerts] no alert channel is configured for bot events"
#: The WARNING `--skip-preflight` writes; only the provisioned run (no key in the environment) skips.
_SKIPPED_PREFLIGHT_WARNING = "[preflight] --skip-preflight: no check ran"
_HEALTH_RECORD = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - App\.Operations - INFO - \[health\] state=",
    re.MULTILINE,
)

#: Qt is not installed on a server. Blocking it makes any import of it fail the run.
_NO_QT = """
import sys
for _name in ("PySide6", "shiboken6", "pyqtgraph"):
    sys.modules[_name] = None
"""

#: What the run read of the canary, counted at the provider every venue uses and
#: said at exit, after the log: without a read, the absence of a leak means nothing.
_COUNT_CREDENTIAL_READS = """
import atexit
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters import env_first_credentials_provider as _p

_reads = []
_resolve = _p.EnvFirstCredentialsProvider.resolve

def _counting(self):
    resolved = _resolve(self)
    if resolved.credentials is not None and resolved.credentials.api_key.startswith("CANARY-KEY-"):
        _reads.append(1)
    return resolved

_p.EnvFirstCredentialsProvider.resolve = _counting
atexit.register(lambda: print(f"CREDENTIALS_READ={len(_reads)}", flush=True))
"""


@dataclass(frozen=True, slots=True)
class _Run:
    code: int
    stdout: str
    stderr: str
    data_root: Path

    @property
    def log(self) -> str:
        return self.stdout + self.stderr

    @property
    def evidence(self) -> str:
        return f"exit {self.code}\n--- stdout ---\n{self.stdout}\n--- stderr ---\n{self.stderr}"


@pytest.fixture(scope="module")
def run(tmp_path_factory: pytest.TempPathFactory) -> Iterator[_Run]:
    """One `run`, started, served for a few health lines, signalled and read by all four facts."""
    data_root = tmp_path_factory.mktemp("headless_data_root")
    with run_binance_fake_server() as urls:
        child = RunChild(
            data_root,
            urls,
            "--health-interval",
            "1",
            patch=_COUNT_CREDENTIAL_READS,
            credentials=_CREDENTIALS,
            script=_NO_QT + CHILD_SCRIPT,
        )
        try:
            child.wait_for_stdout("[health] state=SERVING")
            child.wait_for_stdout("up=1s")
            child.send(signal.SIGTERM)
            code = child.finish()
        finally:
            child.kill()
        yield _Run(code, child.stdout, child.stderr, data_root)


def test_a_run_leaves_no_unexpected_warning_or_error_in_the_log(run: _Run) -> None:
    assert run.code == 0, run.evidence
    assert "workers closed" in run.stdout, run.evidence
    problems = [
        record.group(0)
        for record in _PROBLEM_RECORD.finditer(run.log)
        if _EXPECTED_WARNING not in record.group(0)
    ]
    assert not problems, f"the run-log scan would fail: {problems}\n{run.evidence}"
    assert _EXPECTED_WARNING in run.log, "`run` must warn that no alert channel exists"


def test_the_health_line_in_the_hosts_real_stdout_parses_back(run: _Run) -> None:
    assert _HEALTH_RECORD.search(run.stdout), run.evidence
    lines = health_lines_in(run.stdout)
    assert lines, run.evidence
    states = {line.state for line in lines}
    assert HostState.SERVING in states and HostState.DRAINING in states, run.evidence
    assert all(line.rss_mb is None or line.rss_mb > 0 for line in lines)


def test_no_credential_reaches_the_log(run: _Run) -> None:
    assert run.code == 0, run.evidence
    # Positive proof first: the run read the canary through the real provider, so the
    # absence below is not just "nothing touched it".
    match = re.search(r"CREDENTIALS_READ=(\d+)", run.stdout)
    assert match is not None and int(match.group(1)) > 0, run.evidence
    assert _CANARY_KEY not in run.log, "an API key reached the log"
    assert _CANARY_SECRET not in run.log, "an API secret reached the log"


def test_no_credential_reaches_a_file_the_run_wrote(run: _Run) -> None:
    assert run.code == 0, run.evidence
    _assert_no_canary_in_any_file_the_run_wrote(run.data_root)


def test_a_plain_run_writes_no_log_file(run: _Run) -> None:
    assert run.code == 0, run.evidence
    logs_dir = run.data_root / "logs"
    written = sorted(os.listdir(logs_dir)) if logs_dir.exists() else []
    assert written == [], f"a plain run wrote log files: {written}"


def _assert_no_canary_in_any_file_the_run_wrote(data_root: Path) -> None:
    """The log is one place a secret could leak; the health snapshot
    (`state/health.json`) and every other file under the data root are the rest."""
    written = [
        Path(folder) / name for folder, _, names in os.walk(data_root) for name in names
    ]
    # The scan must cover the snapshot, or its silence proves nothing about it.
    assert data_root / "state" / "health.json" in written, [str(p) for p in written]
    for path in written:
        content = path.read_bytes()
        assert _CANARY_KEY.encode() not in content, f"an API key reached {path}"
        assert _CANARY_SECRET.encode() not in content, f"an API secret reached {path}"


def _provision(directory: Path, venue: str) -> None:
    """One venue's pair as owner-only files, the way an operator leaves them."""
    directory.mkdir(parents=True, exist_ok=True)
    for part, value in (("key", _CANARY_KEY), ("secret", _CANARY_SECRET)):
        path = directory / f"{venue}_api_{part}"
        path.write_text(f"{value}\n", encoding="utf-8")
        path.chmod(0o600)


#: `EPIC-038E` - read the canary the way a server gets it, through the production order
#: (`build_secret_stores`), after the host has stopped, and say what each venue resolved.
_READ_THE_PROVISIONED_CANARY = """
import atexit

def _resolve_provisioned():
    from Sagittarius_Elite_Warrior.src.modules.trading.composition.secret_store_order import build_secret_stores
    from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import MainnetCredentialsProvider
    from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import TradingVenue

    stores = build_secret_stores()
    for venue in (TradingVenue.FUTURES_MAINNET, TradingVenue.SPOT_MAINNET):
        resolved = MainnetCredentialsProvider(stores, venue).resolve()
        key = resolved.credentials.api_key if resolved.credentials is not None else ""
        print(f"RESOLVED {venue.value} via {resolved.source.value} canary={key.startswith('CANARY-KEY-')}", flush=True)

atexit.register(_resolve_provisioned)
"""


@pytest.fixture(scope="module")
def provisioned_run(tmp_path_factory: pytest.TempPathFactory) -> Iterator[_Run]:
    """`EPIC-038E` - one `run` whose canary arrives as a systemd credential (futures
    mainnet) and as a permission-checked file (spot mainnet), not as environment
    variables."""
    data_root = tmp_path_factory.mktemp("headless_data_root")
    credentials = tmp_path_factory.mktemp("systemd_credentials")
    secret_files = tmp_path_factory.mktemp("secret_files")
    _provision(credentials, "futures_mainnet")
    _provision(secret_files, "spot_mainnet")
    with run_binance_fake_server() as urls:
        child = RunChild(
            data_root,
            urls,
            "--health-interval",
            "1",
            "--skip-preflight",  # no key is in the environment, so the pre-flight would refuse with 5
            patch=_READ_THE_PROVISIONED_CANARY,
            credentials={
                "CREDENTIALS_DIRECTORY": str(credentials),
                "SEW_SECRET_FILES_DIR": str(secret_files),
            },
            script=_NO_QT + CHILD_SCRIPT,
        )
        try:
            child.wait_for_stdout("[health] state=SERVING")
            child.send(signal.SIGTERM)
            code = child.finish()
        finally:
            child.kill()
        yield _Run(code, child.stdout, child.stderr, data_root)


def test_no_credential_provisioned_by_systemd_or_a_secret_file_reaches_the_log(
    provisioned_run: _Run,
) -> None:
    assert provisioned_run.code == 0, provisioned_run.evidence
    # Positive proof first: each canary was resolved through the backend named, so
    # the absence below is not just "nothing touched it".
    out = provisioned_run.stdout
    assert "RESOLVED futures_mainnet via systemd-credential canary=True" in out, (
        provisioned_run.evidence
    )
    assert "RESOLVED spot_mainnet via secret-file canary=True" in out, (
        provisioned_run.evidence
    )
    _assert_no_canary_in_any_file_the_run_wrote(provisioned_run.data_root)
    assert _CANARY_KEY not in provisioned_run.log, "an API key reached the log"
    assert _CANARY_SECRET not in provisioned_run.log, "an API secret reached the log"
    problems = [
        record.group(0)
        for record in _PROBLEM_RECORD.finditer(provisioned_run.log)
        if _EXPECTED_WARNING not in record.group(0)
        and _SKIPPED_PREFLIGHT_WARNING not in record.group(0)
    ]
    assert not problems, provisioned_run.evidence
