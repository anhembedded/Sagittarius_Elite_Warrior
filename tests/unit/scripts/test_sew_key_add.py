"""`BOT-200` — `sew-key add`: see `sew_key_world.py` for the setup."""

from __future__ import annotations

import json
import os
import subprocess
import sys

from Sagittarius_Elite_Warrior.tests.unit.scripts.service_files_world import (
    require_tool,
)
from Sagittarius_Elite_Warrior.tests.unit.scripts.sew_key_world import (
    KEY,
    OLD_KEY,
    OLD_SECRET,
    SCRIPT,
    SECRET,
    World,
    accepted,
    mode_of,
    nothing_leaked,
    refused,
    typed,
)


def test_the_script_is_clean_under_shellcheck_and_parses_under_bash() -> None:
    subprocess.run([require_tool("bash"), "-n", str(SCRIPT)], check=True)
    done = subprocess.run(
        [require_tool("shellcheck"), "-x", str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout


def test_the_script_is_executable_and_names_no_bashism_the_runbook_does_not_use() -> (
    None
):
    assert os.access(SCRIPT, os.X_OK)
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash\n")
    assert "set -euo pipefail" in text
    assert "umask 077" in text
    assert "eval " not in text


def test_add_mainnet_writes_two_files_mode_0600_with_the_values_and_no_newline(
    world: World,
) -> None:
    run = world.run("add", answers=typed("futures_mainnet"))

    assert run.code == 0, run.err
    key_file = world.mainnet("futures_mainnet", "key")
    secret_file = world.mainnet("futures_mainnet", "secret")
    assert key_file.read_text(encoding="utf-8") == KEY
    assert secret_file.read_text(encoding="utf-8") == SECRET
    assert mode_of(key_file) == mode_of(secret_file) == 0o600
    assert world.leftovers() == []
    nothing_leaked(run)


def test_add_mainnet_replaces_the_old_pair_and_leaves_the_other_venue_alone(
    world: World,
) -> None:
    world.seed_mainnet("futures_mainnet")
    world.seed_mainnet("spot_mainnet", "SPOTKEY", "SPOTSECRET")

    run = world.run("add", "futures_mainnet", answers=typed("futures_mainnet"))

    assert run.code == 0, run.err
    assert world.mainnet("futures_mainnet", "key").read_text(encoding="utf-8") == KEY
    assert world.mainnet("spot_mainnet", "key").read_text(encoding="utf-8") == "SPOTKEY"
    assert (
        world.mainnet("spot_mainnet", "secret").read_text(encoding="utf-8")
        == "SPOTSECRET"
    )


def test_the_key_reaches_the_check_by_standard_input_and_by_no_argument(
    world: World,
) -> None:

    run = world.run("add", answers=typed("futures_mainnet"))

    assert run.code == 0, run.err
    called = json.loads(world.stub_log.read_text(encoding="utf-8"))
    assert called["argv"] == ["key", "check", "--json"]
    assert world.stub_stdin.read_text(encoding="utf-8") == f"{KEY}\n{SECRET}\n"


def test_a_check_that_refuses_the_key_writes_nothing_and_says_why(world: World) -> None:
    world.seed_mainnet("futures_mainnet")

    run = world.run(
        "add",
        answers=f"{KEY}\n{SECRET}\n",
        check=refused("withdrawal_enabled", "This mainnet key can withdraw funds."),
    )

    assert run.code != 0
    assert "can withdraw funds" in run.err
    assert "nothing was written" in run.err
    assert (
        world.mainnet("futures_mainnet", "key").read_text(encoding="utf-8") == OLD_KEY
    )
    assert (
        world.mainnet("futures_mainnet", "secret").read_text(encoding="utf-8")
        == OLD_SECRET
    )
    assert world.leftovers() == []
    nothing_leaked(run)


def test_a_venue_typed_that_does_not_match_writes_nothing(world: World) -> None:
    world.seed_mainnet("futures_mainnet")

    run = world.run("add", answers=typed("spot_mainnet"))

    assert run.code != 0
    assert "does not match" in run.err
    assert (
        world.mainnet("futures_mainnet", "key").read_text(encoding="utf-8") == OLD_KEY
    )
    assert not world.mainnet("spot_mainnet", "key").exists()
    assert world.leftovers() == []
    nothing_leaked(run)


def test_a_key_for_another_venue_than_the_one_asked_for_writes_nothing(
    world: World,
) -> None:
    run = world.run("add", "spot_mainnet", answers=typed("spot_mainnet"))

    assert run.code != 0
    assert "futures_mainnet" in run.err
    assert list(world.credentials.iterdir()) == []


def test_a_key_that_can_trade_both_markets_is_stored_for_the_onetyped(
    world: World,
) -> None:
    run = world.run(
        "add",
        answers=typed("spot_mainnet"),
        check=accepted("spot_mainnet", "futures_mainnet"),
    )

    assert run.code == 0, run.err
    assert world.mainnet("spot_mainnet", "key").read_text(encoding="utf-8") == KEY
    assert not world.mainnet("futures_mainnet", "key").exists()


def test_a_character_a_binance_key_never_has_stops_before_the_check(
    world: World,
) -> None:
    run = world.run("add", answers=f"{KEY}$x\n{SECRET}\n")

    assert run.code != 0
    assert "never has" in run.err
    assert not world.stub_log.exists(), "the check must not have been asked"
    nothing_leaked(run)


def test_add_testnet_edits_only_its_two_lines_and_keeps_the_others_and_themode_of(
    world: World,
) -> None:
    world.env_file.write_text(
        "# the testnet keys\n"
        "BINANCE_SPOT_TESTNET_API_KEY=SPOTKEY\n"
        "BINANCE_FUTURES_TESTNET_API_KEY=OLDFUTURESKEY\n"
        "SOMETHING_ELSE=1\n"
        "BINANCE_FUTURES_TESTNET_API_SECRET=OLDFUTURESSECRET\n"
        "BINANCE_SPOT_TESTNET_API_SECRET=SPOTSECRET\n",
        encoding="utf-8",
    )
    world.env_file.chmod(0o640)

    run = world.run(
        "add", answers=typed("futures_testnet"), check=accepted("futures_testnet")
    )

    assert run.code == 0, run.err
    lines = world.env_file.read_text(encoding="utf-8").splitlines()
    assert "# the testnet keys" in lines
    assert "SOMETHING_ELSE=1" in lines
    assert "BINANCE_SPOT_TESTNET_API_KEY=SPOTKEY" in lines
    assert "BINANCE_SPOT_TESTNET_API_SECRET=SPOTSECRET" in lines
    assert f"BINANCE_FUTURES_TESTNET_API_KEY={KEY}" in lines
    assert f"BINANCE_FUTURES_TESTNET_API_SECRET={SECRET}" in lines
    assert not any("OLDFUTURES" in line for line in lines)
    assert len(lines) == 6
    assert mode_of(world.env_file) == 0o640
    assert world.leftovers() == []
    nothing_leaked(run)


def test_add_testnet_creates_sew_env_mode_0640_when_there_is_none(world: World) -> None:
    run = world.run(
        "add", answers=typed("spot_testnet"), check=accepted("spot_testnet")
    )

    assert run.code == 0, run.err
    assert world.env_file.read_text(encoding="utf-8").splitlines() == [
        f"BINANCE_SPOT_TESTNET_API_KEY={KEY}",
        f"BINANCE_SPOT_TESTNET_API_SECRET={SECRET}",
    ]
    assert mode_of(world.env_file) == 0o640


def test_the_files_are_private_whatever_the_callers_umask(world: World) -> None:
    run = subprocess.run(
        [require_tool("sh"), "-c", f"umask 000; exec bash '{SCRIPT}' add"],
        input=typed("futures_mainnet"),
        capture_output=True,
        text=True,
        check=False,
        env={
            "PATH": os.environ["PATH"],
            "SEW_KEY_CREDENTIALS_DIR": str(world.credentials),
            "SEW_KEY_ENV_FILE": str(world.env_file),
            "SEW_KEY_UNIT_DIR": str(world.units),
            "SEW_KEY_CHECK_COMMAND": str(world.stub),
            "SEW_KEY_PYTHON": sys.executable,
            "SEW_KEY_EUID": "0",
            "SEW_KEY_NO_CHOWN": "1",
            "STUB_LOG": str(world.stub_log),
            "STUB_STDIN": str(world.stub_stdin),
            "STUB_ANSWER": __import__("json").dumps(accepted("futures_mainnet")),
        },
    )

    assert run.returncode == 0, run.stderr
    assert mode_of(world.mainnet("futures_mainnet", "key")) == 0o600
    assert mode_of(world.mainnet("futures_mainnet", "secret")) == 0o600


def test_remove_mainnet_truncates_the_files_and_never_deletes_them(
    world: World,
) -> None:
    world.seed_mainnet("futures_mainnet")

    run = world.run("remove", "futures_mainnet", answers="futures_mainnet\n")

    assert run.code == 0, run.err
    for suffix in ("key", "secret"):
        path = world.mainnet("futures_mainnet", suffix)
        assert path.exists(), "a missing file would stop the unit with 243/CREDENTIALS"
        assert path.read_bytes() == b""
        assert mode_of(path) == 0o600
    assert "restart sew-run" in run.out
