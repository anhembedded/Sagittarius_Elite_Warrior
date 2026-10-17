"""`bot order <id>` as a real process on a real data root (`BOT-187`).

The unit tests prove the report and the verb over a fake store. This proves what only a process
shows: that the command boots as a read-only copy (a RUNNING bot's file is left byte for byte,
no lock file is taken), reads a runtime the JSON store really wrote, and reports a damaged file
and an unknown id in words with the exit code a script reads.

Nothing here reaches an exchange: the verb opens no session.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.persistence.json_bot_store import (
    JsonBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_runtime_codec import (
    encode_runtime,
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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_level_fsm_matrix import (
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
    LevelOrder,
    RuntimeLevel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PROCESS_BUDGET_SECONDS = 90
_FAKE_SECRET = "SECRET-SENTINEL-4c1d7e90-never-print-me"  # noqa: S105 - a marker, not a credential
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
            "BINANCE_FUTURES_TESTNET_API_KEY": "fake-api-key-for-a-test",
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


def _save(
    bots_dir: Path, bot_id: str, state: BotLifecycleState, runtime: object
) -> None:
    definition = BotDefinition(
        name=f"bot {bot_id}",
        kind="grid",
        venue=TradingVenue.SPOT_TESTNET,
        symbol="BTCUSDT",
        config={"lower": "60000"},
    )
    JsonBotStore(bots_dir).save(
        StoredBot(
            Bot(BotId(bot_id), definition, BotLifecycle(state), _CREATED),
            runtime,  # type: ignore[arg-type]
        )
    )


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    bots = tmp_path / "state" / "bots"
    ladder = GridRuntime(
        (
            RuntimeLevel(
                3,
                Decimal(61000),
                Decimal(1),
                LevelState.RESTING,
                LevelOrder(
                    "sew-aaaaaa-3", OrderSide.BUY, Decimal(61000), Decimal("0.01")
                ),
            ),
        )
    )
    _save(bots, "aaaaaa", BotLifecycleState.RUNNING, dict(encode_runtime(ladder)))
    _save(bots, "bbbbbb", BotLifecycleState.STOPPED, {})
    (bots / "dddddd.json").write_text("{ this is not json", encoding="utf-8")
    return tmp_path


def test_bot_order_prints_the_stored_orders_and_changes_nothing(
    data_root: Path,
) -> None:
    file = data_root / "state" / "bots" / "aaaaaa.json"
    before = file.read_text(encoding="utf-8")

    result = _run(data_root, "bot", "order", "aaaaaa", "--json")

    assert result.returncode == ExitCode.SUCCESS, result.stderr
    data = json.loads(result.stdout)["data"]
    assert data["source"] == "stored"
    assert data["orders"] == [
        {
            "level": 3,
            "side": "BUY",
            "price": "61000",
            "quantity": "0.01",
            "executed": "0",
            "state": "RESTING",
            "client_order_id": "sew-aaaaaa-3",
        }
    ]
    # Read-only: the writable boot would have made this RUNNING bot RECOVERING and taken the lock.
    assert file.read_text(encoding="utf-8") == before
    assert not (data_root / "state" / "instance.lock").exists()
    assert _FAKE_SECRET not in result.stdout + result.stderr


def test_bot_order_text_view_lists_the_order_and_says_it_is_stored(
    data_root: Path,
) -> None:
    result = _run(data_root, "bot", "order", "aaaaaa")

    assert result.returncode == ExitCode.SUCCESS, result.stderr
    assert "not read from the exchange" in result.stdout
    assert "sew-aaaaaa-3" in result.stdout
    assert "Traceback" not in result.stderr


def test_a_bot_with_no_run_prints_no_orders(data_root: Path) -> None:
    result = _run(data_root, "bot", "order", "bbbbbb")

    assert result.returncode == ExitCode.SUCCESS, result.stderr
    assert "No orders." in result.stdout


def test_a_damaged_bot_file_is_reported_not_crashed(data_root: Path) -> None:
    result = _run(data_root, "bot", "order", "dddddd")

    assert result.returncode == ExitCode.SUCCESS, result.stderr
    assert "dddddd.json" in result.stdout
    assert "Traceback" not in result.stderr


def test_an_unknown_bot_id_exits_2_in_words(data_root: Path) -> None:
    result = _run(data_root, "bot", "order", "zzzzzz")

    assert result.returncode == ExitCode.USAGE
    assert "zzzzzz" in result.stderr
    assert "Traceback" not in result.stderr
