"""`EPIC-038G` — what a headless process leaves in its log.

An unattended process is judged by its log: the CI run-log scan reads
`- (WARNING|ERROR|CRITICAL) -` records, a monitor parses the health line, and a
secret that reaches either is leaked for good. This runs the shared composition
the `run` host will wrap (`create_app`, `boot`, one health line, `stop`) in a
fresh interpreter with **PySide6 blocked**, on the **real logging
configuration** (`StdLogger` from the shipped config, never `basicConfig`), with
canary credentials in the environment, and reads what came out.

Four facts (and, from `EPIC-038E`, a fifth at the end of this file: the same canary
provisioned as a systemd credential and as a permission-checked file):

1. no WARNING/ERROR/CRITICAL record and no "uncollectable objects" line, so the
   scan stays quiet on a healthy headless run;
2. the health line arrives as an INFO record in the Engine's fixed field order
   and the parser reads it back from that real output;
3. no canary secret appears anywhere in stdout or stderr, **after** the run read
   each venue's canary through the real credential providers (the boot alone
   resolves none, so without that read the check would prove only that boot
   does not print the environment);
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

_BOOT_AND_HEALTH_LINE = """
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

"""

_READ_THE_ENVIRONMENT_CANARY = """
# `create_app/boot/stop` resolves no credential on an empty data root, so the
# canary has to be read on purpose: through the same provider classes the venues
# use (`venue_assembly.credentials_provider`), over the same environment.
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    EnvFirstCredentialsProvider, MainnetCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.secrets_file_source import SecretsFileSource
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import TradingVenue
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.ordered_secret_stores import OrderedSecretStores
from Sagittarius_Elite_Warrior.tests.secret_stores import InMemorySecretStore

read = 0
for venue in TradingVenue:
    if venue is TradingVenue.DISABLED:
        continue
    provider = (
        MainnetCredentialsProvider(OrderedSecretStores.single(InMemorySecretStore()), venue)
        if venue.is_mainnet
        else EnvFirstCredentialsProvider(SecretsFileSource("no-such-secrets-file.json"), venue)
    )
    credentials = provider.resolve().credentials
    if credentials is not None and credentials.api_key.startswith("CANARY-KEY-"):
        read += 1
print(f"CREDENTIALS_READ={read}")
"""

#: `EPIC-038E` - the same boot, but the canary is provisioned the way a server gets it:
#: one venue's pair as a systemd credential, the other's as a permission-checked
#: file, read through the production order (`build_secret_stores`), never the environment.
_READ_THE_PROVISIONED_CANARY = """
from Sagittarius_Elite_Warrior.src.modules.trading.composition.secret_store_order import build_secret_stores
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import MainnetCredentialsProvider
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import TradingVenue

stores = build_secret_stores()
for venue in (TradingVenue.FUTURES_MAINNET, TradingVenue.SPOT_MAINNET):
    resolved = MainnetCredentialsProvider(stores, venue).resolve()
    key = resolved.credentials.api_key if resolved.credentials is not None else ""
    print(f"RESOLVED {venue.value} via {resolved.source.value} canary={key.startswith('CANARY-KEY-')}")
"""

_BOOT_DONE = """
app.stop()
print("HEADLESS_BOOT_DONE")
"""


def _run_headless_boot(
    data_root: Path,
    reads_the_canary: str = _READ_THE_ENVIRONMENT_CANARY,
    *,
    environment_canary: bool = True,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("BINANCE_", "SEW_", "CREDENTIALS_DIRECTORY"))
    }
    env.update({DATA_ROOT_ENV: str(data_root), "QT_QPA_PLATFORM": "offscreen"})
    if environment_canary:
        for name in _CREDENTIAL_VARIABLES:
            env[name] = _CANARY_KEY if name.endswith("_KEY") else _CANARY_SECRET
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, "-c", _BOOT_AND_HEALTH_LINE + reads_the_canary + _BOOT_DONE],
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
    # Positive proof first: the run read every venue's canary through the real
    # provider classes, so the absence below is not just "nothing touched it".
    assert (
        f"CREDENTIALS_READ={len(_CREDENTIAL_VARIABLES) // 2}" in boot.result.stdout
    ), boot.evidence
    assert _CANARY_KEY not in boot.log, "an API key reached the log"
    assert _CANARY_SECRET not in boot.log, "an API secret reached the log"


def test_no_credential_reaches_a_file_the_run_wrote(boot: _Boot) -> None:
    assert boot.result.returncode == 0, boot.evidence
    _assert_no_canary_in_any_file_the_run_wrote(boot.data_root)


def test_a_plain_headless_run_writes_no_log_file(boot: _Boot) -> None:
    assert boot.result.returncode == 0, boot.evidence
    logs_dir = boot.data_root / "logs"
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


@pytest.fixture(scope="module")
def provisioned_boot(tmp_path_factory: pytest.TempPathFactory) -> Iterator[_Boot]:
    """`EPIC-038E` - one headless boot whose canary arrives as a systemd credential
    (futures mainnet) and as a permission-checked file (spot mainnet), not as
    environment variables."""
    data_root = tmp_path_factory.mktemp("headless_data_root")
    credentials = tmp_path_factory.mktemp("systemd_credentials")
    secret_files = tmp_path_factory.mktemp("secret_files")
    _provision(credentials, "futures_mainnet")
    _provision(secret_files, "spot_mainnet")
    yield _Boot(
        _run_headless_boot(
            data_root,
            _READ_THE_PROVISIONED_CANARY,
            environment_canary=False,
            extra_env={
                "CREDENTIALS_DIRECTORY": str(credentials),
                "SEW_SECRET_FILES_DIR": str(secret_files),
            },
        ),
        data_root,
    )


def test_no_credential_provisioned_by_systemd_or_a_secret_file_reaches_the_log(
    provisioned_boot: _Boot,
) -> None:
    assert provisioned_boot.result.returncode == 0, provisioned_boot.evidence
    # Positive proof first: each canary was resolved through the backend named, so
    # the absence below is not just "nothing touched it".
    out = provisioned_boot.result.stdout
    assert "RESOLVED futures_mainnet via systemd-credential canary=True" in out, (
        provisioned_boot.evidence
    )
    assert "RESOLVED spot_mainnet via secret-file canary=True" in out, (
        provisioned_boot.evidence
    )
    _assert_no_canary_in_any_file_the_run_wrote(provisioned_boot.data_root)
    assert _CANARY_KEY not in provisioned_boot.log, "an API key reached the log"
    assert _CANARY_SECRET not in provisioned_boot.log, "an API secret reached the log"
    assert not _PROBLEM_RECORD.findall(provisioned_boot.log), provisioned_boot.evidence
