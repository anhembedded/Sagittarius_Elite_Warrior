"""`bot apply` and `bot export` as real processes (`EPIC-038I`): the lock, the exit codes, no secret.

A child runs `main()` exactly as `python src/main.py bot apply plan.json` would, inside the
sanity tier's network boundary, with canary credentials in its environment. The pure code is
`tests/unit/modules/bots/application/plan/`; the journey on the composed app and the fake
exchange is `tests/integration/modules/bots/test_bot_apply_then_start_planned_*`. What only a
process can show is here: another copy holding the data root (exit 3 for `apply`, none for
`--dry-run` or `export`), and what reaches the outputs and the files.
"""

from __future__ import annotations

import json
import signal
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.tests.integration.modules.bots.grid_fake_exchange import (
    GRID,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.run_process_support import (
    children_to_reap,
    fake_exchange,
    start_child,
)
from Sagittarius_Elite_Warrior.tests.run_host_child import FAKE_SECRET, RunChild

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sanity"))
from binance_fake_server import FakeServerUrls

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="the host is stopped with a POSIX SIGTERM"
)


@pytest.fixture
def exchange() -> Iterator[FakeServerUrls]:
    with fake_exchange() as urls:
        yield urls


@pytest.fixture
def started(exchange: FakeServerUrls) -> Iterator[list[RunChild]]:
    with children_to_reap() as children:
        yield children


def _plan(path: Path, *bots: dict[str, object]) -> Path:
    path.write_text(json.dumps({"schema": "sew.bot-plan/1", "bots": list(bots)}))
    return path


def _bot(
    name: str = "BTC grid", desired: str = "running", **extra: object
) -> dict[str, object]:
    return {
        "name": name,
        "kind": "grid",
        "venue": "spot_testnet",
        "symbol": "BTCUSDT",
        "params": dict(GRID),
        "desired_state": desired,
        **extra,
    }


def _bot_command(
    started: list[RunChild], data_root: Path, urls: FakeServerUrls, *args: str
) -> tuple[int, str, str]:
    child = start_child(started, data_root, urls, *args, command="bot")
    code = child.finish()
    return code, child.stdout, child.stderr


def _json(out: str) -> dict[str, object]:
    return json.loads(out)["data"]


def test_apply_creates_the_bot_then_says_no_changes_and_leaks_no_secret(
    started: list[RunChild], tmp_path: Path, exchange: FakeServerUrls
) -> None:
    data_root = tmp_path / "data"
    plan = _plan(tmp_path / "plan.json", _bot())

    first = _bot_command(started, data_root, exchange, "apply", str(plan), "--json")
    second = _bot_command(started, data_root, exchange, "apply", str(plan), "--json")
    listed = _bot_command(started, data_root, exchange, "list", "--json")

    assert first[0] == int(ExitCode.SUCCESS), first[1] + first[2]
    assert _json(first[1])["summary"]["create"] == 1  # type: ignore[index]
    assert second[0] == int(ExitCode.SUCCESS), second[1] + second[2]
    assert _json(second[1])["has_changes"] is False
    (bot,) = _json(listed[1])["bots"]  # type: ignore[misc]
    assert bot["name"] == "BTC grid" and bot["state"] == "DRAFT"
    record = data_root / "state" / "bot_plan.json"
    assert record.exists(), "the applied plan is recorded beside the bots"
    everything = (
        "".join(c[1] + c[2] for c in (first, second, listed)) + record.read_text()
    )
    assert FAKE_SECRET not in everything


def test_a_plan_with_a_key_field_exits_two_and_the_value_is_nowhere(
    started: list[RunChild], tmp_path: Path, exchange: FakeServerUrls
) -> None:
    plan = _plan(tmp_path / "plan.json", _bot(api_key=FAKE_SECRET))

    code, out, err = _bot_command(
        started, tmp_path / "data", exchange, "apply", str(plan)
    )

    assert code == int(ExitCode.USAGE)
    assert "api_key" in err and "unknown field" in err
    assert FAKE_SECRET not in out + err
    assert not (tmp_path / "data" / "state" / "bot_plan.json").exists()


def test_export_then_a_dry_run_is_no_changes_as_processes(
    started: list[RunChild], tmp_path: Path, exchange: FakeServerUrls
) -> None:
    data_root = tmp_path / "data"
    _bot_command(
        started, data_root, exchange, "apply", str(_plan(tmp_path / "p.json", _bot()))
    )
    out_file = tmp_path / "exported.json"

    exported = _bot_command(
        started, data_root, exchange, "export", "--all", "--output", str(out_file)
    )
    dry = _bot_command(
        started,
        data_root,
        exchange,
        "apply",
        str(out_file),
        "--dry-run",
        "--prune",
        "--json",
    )

    assert exported[0] == int(ExitCode.SUCCESS), exported[1] + exported[2]
    assert dry[0] == int(ExitCode.SUCCESS), dry[1] + dry[2]
    assert _json(dry[1])["has_changes"] is False
    assert FAKE_SECRET not in out_file.read_text() + dry[1] + dry[2]


def test_beside_a_running_host_apply_exits_three_but_a_dry_run_and_an_export_work(
    started: list[RunChild], tmp_path: Path, exchange: FakeServerUrls
) -> None:
    data_root = tmp_path / "data"
    plan = _plan(tmp_path / "plan.json", _bot())
    host = start_child(started, data_root, exchange, "--skip-preflight")
    host.wait_for_stdout("[host] BOOTING -> SERVING")
    try:
        applied = _bot_command(started, data_root, exchange, "apply", str(plan))
        dry = _bot_command(
            started, data_root, exchange, "apply", str(plan), "--dry-run", "--json"
        )
        exported = _bot_command(
            started,
            data_root,
            exchange,
            "export",
            "--all",
            "--output",
            str(tmp_path / "e.json"),
        )
    finally:
        host.send(signal.SIGTERM)
        host.finish()

    assert applied[0] == int(ExitCode.LOCK_HELD), applied[1] + applied[2]
    assert "writable copy" in applied[2] or "writable copy" in applied[1]
    assert dry[0] == int(ExitCode.SUCCESS), dry[1] + dry[2]
    assert _json(dry[1])["has_changes"] is True
    assert exported[0] == int(ExitCode.SUCCESS), exported[1] + exported[2]
    assert not (data_root / "state" / "bot_plan.json").exists(), (
        "the refused apply wrote nothing"
    )


def test_run_start_planned_with_no_applied_plan_exits_five_and_boots_nothing(
    started: list[RunChild], tmp_path: Path, exchange: FakeServerUrls
) -> None:
    child = start_child(
        started, tmp_path / "data", exchange, "--start-planned", "--skip-preflight"
    )

    code = child.finish()

    assert code == int(ExitCode.CONFIGURATION), child.stdout + child.stderr
    assert "bot apply" in child.stderr
    assert "[host]" not in child.stdout, "nothing booted, nothing served"


def test_run_start_planned_with_a_damaged_record_exits_five_and_repeats_none_of_it(
    started: list[RunChild], tmp_path: Path, exchange: FakeServerUrls
) -> None:
    data_root = tmp_path / "data"
    (data_root / "state").mkdir(parents=True)
    (data_root / "state" / "bot_plan.json").write_text(
        '{"api_key": "' + FAKE_SECRET + '"'
    )

    child = start_child(
        started, data_root, exchange, "--start-planned", "--skip-preflight"
    )
    code = child.finish()

    assert code == int(ExitCode.CONFIGURATION), child.stdout + child.stderr
    assert "record" in child.stderr
    assert FAKE_SECRET not in child.stdout + child.stderr
    assert "[host]" not in child.stdout


_SPOT_TESTNET_KEYS = {
    "BINANCE_SPOT_TESTNET_API_KEY": "fake-spot-key-for-a-test",
    "BINANCE_SPOT_TESTNET_API_SECRET": FAKE_SECRET,
}


def test_a_real_run_with_start_planned_starts_exactly_the_bot_the_plan_wants_running(
    started: list[RunChild], tmp_path: Path, exchange: FakeServerUrls
) -> None:
    """The journey in processes: apply a plan, run the host with `--start-planned`.

    The host asks for a start of the bot the plan wants running and of no other. That the bot
    then reaches RUNNING on the fake exchange is the in-process journey
    (`test_bot_apply_then_start_planned_on_the_fake_exchange.py`): this process's fake has no
    user-data stream, so the bot halts a moment after it starts, which is the fake's limit and
    not the plan's."""
    data_root = tmp_path / "data"
    plan = _plan(
        tmp_path / "plan.json", _bot("runs", "running"), _bot("waits", "stopped")
    )
    applied = start_child(
        started, data_root, exchange, "apply", str(plan), "--json", command="bot",
        credentials=_SPOT_TESTNET_KEYS,
    )  # fmt: skip
    assert applied.finish() == int(ExitCode.SUCCESS), applied.stdout + applied.stderr
    ids = {c["name"]: c["bot_id"] for c in _json(applied.stdout)["changes"]}  # type: ignore[union-attr]

    host = start_child(
        started, data_root, exchange, "--start-planned", "--skip-preflight",
        "--health-interval", "1", credentials=_SPOT_TESTNET_KEYS,
    )  # fmt: skip
    try:
        host.wait_for_stdout(f"[start-planned] bot {ids['runs']}: start requested")
        listed = _bot_command(started, data_root, exchange, "list", "--json")
    finally:
        host.send(signal.SIGTERM)
        code = host.finish()

    states = {b["name"]: b["state"] for b in _json(listed[1])["bots"]}  # type: ignore[union-attr]
    assert code == int(ExitCode.SUCCESS), host.stdout + host.stderr
    assert states["runs"] != "DRAFT", "the planned bot was started"
    assert states["waits"] == "DRAFT", "the bot the plan wants stopped was left alone"
    assert f"bot {ids['waits']}" not in host.stdout.split("[start-planned]", 1)[-1]
    assert FAKE_SECRET not in host.stdout + host.stderr + listed[1]
