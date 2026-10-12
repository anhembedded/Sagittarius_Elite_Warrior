"""`status`, `bot list` and `bot show` as real processes on a real data root (`EPIC-038C`).

The unit tests prove the decision and the report with doubles. This proves the
wiring those cannot: that a command declared `read_only` really boots as a
read-only copy (so it neither rewrites a RUNNING bot nor creates the lock it asks
about), that the lock is read from a *second process* the way a monitor would,
and that nothing a script reads holds a credential. The environment carries
recognisable fake credentials; every output is searched for them.

Nothing here reaches an exchange: these commands open no session.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.persistence.json_bot_store import (
    JsonBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.file_health_snapshot_sink import (
    FileHealthSnapshotSink,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.health_snapshot import (
    HealthSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.instance_holder import start_holder, stop_holder

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PROCESS_BUDGET_SECONDS = 90
_FAKE_KEY = "fake-api-key-for-a-test"
_FAKE_SECRET = "SECRET-SENTINEL-8b3e51d2-never-print-me"  # noqa: S105 - a marker, not a credential
_CREATED = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)

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
            "BINANCE_FUTURES_TESTNET_API_KEY": _FAKE_KEY,
            "BINANCE_FUTURES_TESTNET_API_SECRET": _FAKE_SECRET,
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


def _seed_bot(bots_dir: Path, bot_id: str, state: BotLifecycleState) -> None:
    definition = BotDefinition(
        name=f"bot {bot_id}",
        kind="grid",
        venue=TradingVenue.SPOT_TESTNET,
        symbol="BTCUSDT",
        config={"lower": "60000"},
    )
    JsonBotStore(bots_dir).save(
        StoredBot(Bot(BotId(bot_id), definition, BotLifecycle(state), _CREATED))
    )


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    bots = tmp_path / "state" / "bots"
    _seed_bot(bots, "aaaaaa", BotLifecycleState.RUNNING)
    _seed_bot(bots, "bbbbbb", BotLifecycleState.HALTED)
    (bots / "dddddd.json").write_text("{ this is not json", encoding="utf-8")
    return tmp_path


@pytest.fixture
def host(data_root: Path) -> Iterator[None]:
    """A second process holding the instance lock: a host, as far as `status` can tell."""
    holder = start_holder(data_root / "state" / "instance.lock")
    try:
        yield
    finally:
        stop_holder(holder)


def _publish(
    data_root: Path, age_s: int, sections: dict[str, dict[str, object]]
) -> None:
    now = datetime.now(UTC)
    FileHealthSnapshotSink(data_root / "state" / "health.json").publish(
        HealthSnapshot(
            app_version="9.9.9",
            pid=1,
            started_at=now - timedelta(hours=1),
            written_at=now - timedelta(seconds=age_s),
            interval_s=10,
            host_state=HostState.SERVING,
            sections=sections,  # type: ignore[arg-type]
        )
    )


def _data(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return json.loads(result.stdout)["data"]  # type: ignore[no-any-return]


def test_status_with_no_host_exits_10_and_changes_nothing(data_root: Path) -> None:
    before = (data_root / "state" / "bots" / "aaaaaa.json").read_text(encoding="utf-8")

    result = _run(data_root, "status", "--json")

    assert result.returncode == ExitCode.HOST_NOT_RUNNING, result.stderr
    data = _data(result)
    assert data["host"]["state"] == "not running"  # type: ignore[index]
    # Read-only: the writable boot would have made this RUNNING bot RECOVERING,
    # and taken a lock file the probe then finds.
    assert (data_root / "state" / "bots" / "aaaaaa.json").read_text(
        encoding="utf-8"
    ) == before
    assert not (data_root / "state" / "instance.lock").exists()
    assert not (data_root / "state" / "health.json").exists()
    assert sorted(b["bot_id"] for b in data["bots"]) == ["aaaaaa", "bbbbbb"]  # type: ignore[attr-defined]
    assert [u["bot_id"] for u in data["unreadable"]] == ["dddddd"]  # type: ignore[attr-defined]


def test_status_sees_a_second_process_holding_the_lock(
    data_root: Path, host: None
) -> None:
    result = _run(data_root, "status", "--json")

    assert result.returncode == ExitCode.HOST_UNHEALTHY, result.stderr
    assert _data(result)["host"]["state"] == "stale"  # type: ignore[index]


def test_status_of_a_host_with_a_fresh_snapshot_exits_0(
    data_root: Path, host: None
) -> None:
    _publish(data_root, 1, {"bots": {"total": 2}})

    result = _run(data_root, "status", "--json")

    assert result.returncode == ExitCode.SUCCESS, result.stderr
    data = _data(result)
    assert data["host"]["state"] == "running"  # type: ignore[index]
    assert data["sections"] == {"bots": {"total": 2}}


def test_status_exits_11_when_a_section_is_unavailable(
    data_root: Path, host: None
) -> None:
    _publish(data_root, 1, {"trading": {"status": "unavailable", "reason": "x"}})

    result = _run(data_root, "status", "--json")

    assert result.returncode == ExitCode.HOST_UNHEALTHY
    assert _data(result)["unavailable_sections"] == ["trading"]


def test_a_fresh_file_with_no_host_is_not_running(data_root: Path) -> None:
    _publish(data_root, 1, {"bots": {"total": 2}})

    assert _run(data_root, "status", "--json").returncode == ExitCode.HOST_NOT_RUNNING


def test_bot_list_and_show_read_beside_a_running_host(
    data_root: Path, host: None
) -> None:
    listed = _run(data_root, "bot", "list", "--json")
    shown = _run(data_root, "bot", "show", "bbbbbb", "--json")
    unreadable = _run(data_root, "bot", "show", "dddddd", "--json")

    assert listed.returncode == ExitCode.SUCCESS, listed.stderr
    assert [b["state"] for b in _data(listed)["bots"]] == ["RUNNING", "HALTED"]  # type: ignore[attr-defined]
    assert shown.returncode == ExitCode.SUCCESS, shown.stderr
    assert [b["bot_id"] for b in _data(shown)["bots"]] == ["bbbbbb"]  # type: ignore[attr-defined]
    assert unreadable.returncode == ExitCode.SUCCESS
    assert _data(unreadable)["unreadable"][0]["state"] == "unreadable"  # type: ignore[index]


def test_an_unknown_bot_id_exits_2_with_a_plain_message(data_root: Path) -> None:
    result = _run(data_root, "bot", "show", "zzzzzz")

    assert result.returncode == ExitCode.USAGE
    assert "zzzzzz" in result.stderr
    assert "Traceback" not in result.stderr


def test_bot_without_a_verb_is_a_usage_error(data_root: Path) -> None:
    assert _run(data_root, "bot").returncode == ExitCode.USAGE


def test_no_secret_reaches_any_output_of_these_commands(
    data_root: Path, host: None
) -> None:
    _publish(data_root, 1, {"bots": {"total": 2}})
    outputs = []
    for args in (
        ("status", "--json"),
        ("status",),
        ("bot", "list", "--json"),
        ("bot", "list"),
        ("bot", "show", "aaaaaa", "--json"),
    ):
        result = _run(data_root, *args)
        outputs.append(result.stdout + result.stderr)

    joined = "\n".join(outputs)
    assert "Traceback" not in joined
    assert _FAKE_SECRET not in joined
    assert _FAKE_KEY not in joined
    assert _FAKE_SECRET not in (data_root / "state" / "health.json").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(
    "command",
    [
        ("preflight",),
        ("exchange-status",),
        (
            "order-preview",
            "--symbol",
            "BTCUSDT",
            "--side",
            "BUY",
            "--qty",
            "1",
            "--price",
            "100",
        ),
        (
            "order-dry-run",
            "--symbol",
            "BTCUSDT",
            "--side",
            "BUY",
            "--qty",
            "1",
            "--price",
            "100",
        ),
    ],
    ids=["preflight", "exchange-status", "order-preview", "order-dry-run"],
)
def test_a_command_that_only_reads_leaves_a_running_bot_running(
    data_root: Path, command: tuple[str, ...]
) -> None:
    """The review's finding: `preflight` booted as the writable copy, whose
    restart rule turned RUNNING bots into RECOVERING, and the next step of the
    operator's flow (`run`) would not resume them. A command that only reads is
    declared `read_only`, so it is never that copy (`command_access.py`)."""
    bot_file = data_root / "state" / "bots" / "aaaaaa.json"
    before = bot_file.read_text(encoding="utf-8")

    result = _run(data_root, *command)

    assert "Traceback" not in result.stderr, result.stderr
    assert bot_file.read_text(encoding="utf-8") == before, (
        "the bot's file was rewritten"
    )
    assert json.loads(before)["lifecycle"]["state"] == "RUNNING"
    assert not (data_root / "state" / "instance.lock").exists()
    assert not (data_root / "state" / "health.json").exists()
