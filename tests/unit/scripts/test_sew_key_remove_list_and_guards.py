"""`BOT-200` — `sew-key remove`, `list` and its refusals: see `sew_key_world.py` for the setup."""

from __future__ import annotations

import os
from pathlib import Path

from Sagittarius_Elite_Warrior.tests.unit.scripts.service_files_world import (
    require_tool,
)
from Sagittarius_Elite_Warrior.tests.unit.scripts.sew_key_world import (
    KEY,
    OLD_KEY,
    OLD_SECRET,
    SECRET,
    World,
    mode_of,
    nothing_leaked,
    typed,
)


def test_remove_recreates_a_credential_file_that_was_missing_as_an_empty_one(
    world: World,
) -> None:
    run = world.run("remove", "spot_mainnet", answers="spot_mainnet\n")

    assert run.code == 0, run.err
    assert world.mainnet("spot_mainnet", "key").read_bytes() == b""


def test_remove_with_the_wrong_venue_typed_changes_nothing(world: World) -> None:
    world.seed_mainnet("futures_mainnet")

    run = world.run("remove", "futures_mainnet", answers="spot_mainnet\n")

    assert run.code != 0
    assert (
        world.mainnet("futures_mainnet", "key").read_text(encoding="utf-8") == OLD_KEY
    )


def test_remove_testnet_deletes_only_that_venues_two_lines(world: World) -> None:
    world.env_file.write_text(
        "BINANCE_SPOT_TESTNET_API_KEY=SPOTKEY\n"
        "BINANCE_FUTURES_TESTNET_API_KEY=FKEY\n"
        "OTHER=1\n"
        "BINANCE_FUTURES_TESTNET_API_SECRET=FSECRET\n"
        "BINANCE_SPOT_TESTNET_API_SECRET=SPOTSECRET\n",
        encoding="utf-8",
    )
    world.env_file.chmod(0o640)

    run = world.run("remove", "futures_testnet", answers="futures_testnet\n")

    assert run.code == 0, run.err
    assert world.env_file.read_text(encoding="utf-8").splitlines() == [
        "BINANCE_SPOT_TESTNET_API_KEY=SPOTKEY",
        "OTHER=1",
        "BINANCE_SPOT_TESTNET_API_SECRET=SPOTSECRET",
    ]
    assert mode_of(world.env_file) == 0o640


def test_list_says_who_has_a_key_and_prints_no_value_no_length_and_no_prefix(
    world: World,
) -> None:
    world.seed_mainnet("futures_mainnet", KEY, SECRET)
    world.mainnet("spot_mainnet", "key").write_text("", encoding="utf-8")
    world.mainnet("spot_mainnet", "secret").write_text("", encoding="utf-8")
    world.env_file.write_text(
        f"BINANCE_SPOT_TESTNET_API_KEY={KEY}\nBINANCE_SPOT_TESTNET_API_SECRET={SECRET}\n",
        encoding="utf-8",
    )
    world.env_file.chmod(0o640)

    run = world.run("list")

    assert run.code == 0, run.err
    assert "futures_mainnet" in run.out
    lines = {line.split()[0]: line for line in run.out.splitlines() if line[:1] != " "}
    assert "key present" in lines["futures_mainnet"]
    assert "no key" in lines["spot_mainnet"]
    assert "key present" in lines["spot_testnet"]
    assert "no key" in lines["futures_testnet"]
    assert "mode 600" in run.out
    assert "mode 640" in run.out
    assert not any(
        word in run.out.lower() for word in ("length", "chars", "bytes", "hash")
    )
    nothing_leaked(run)
    for fragment in (KEY[:6], KEY[-6:], SECRET[:6], SECRET[-6:]):
        assert fragment not in run.out


def test_list_names_a_missing_credential_file_as_what_stops_the_unit(
    world: World,
) -> None:
    run = world.run("list")

    assert run.code == 0, run.err
    assert "missing" in run.out
    assert "243/CREDENTIALS" in run.out


def test_a_second_site_that_sets_the_variable_shadows_the_file_and_add_refuses(
    world: World,
) -> None:
    world.env_file.write_text(
        "BINANCE_FUTURES_MAINNET_API_KEY=SHADOWKEY\n", encoding="utf-8"
    )

    run = world.run("add", answers=typed("futures_mainnet"))

    assert run.code != 0
    assert "environment variable" in run.err
    assert str(world.env_file) in run.err
    assert not world.mainnet("futures_mainnet", "key").exists()
    nothing_leaked(run)


def test_a_unit_drop_in_that_sets_the_variable_shadows_it_too(world: World) -> None:
    dropin = world.units / "sew-run.service.d"
    dropin.mkdir()
    (dropin / "keys.conf").write_text(
        "[Service]\nEnvironment=BINANCE_FUTURES_MAINNET_API_SECRET=x\n",
        encoding="utf-8",
    )

    run = world.run("add", answers=typed("futures_mainnet"))

    assert run.code != 0
    assert "keys.conf" in run.err
    assert not world.mainnet("futures_mainnet", "key").exists()


def test_a_commented_or_empty_assignment_shadows_nothing(world: World) -> None:
    world.env_file.write_text(
        "# BINANCE_FUTURES_MAINNET_API_KEY=old\nBINANCE_FUTURES_MAINNET_API_SECRET=\n",
        encoding="utf-8",
    )

    run = world.run("add", answers=typed("futures_mainnet"))

    assert run.code == 0, run.err


def test_list_warns_about_a_shadowed_venue(world: World) -> None:
    world.env_file.write_text("BINANCE_SPOT_MAINNET_API_KEY=x\n", encoding="utf-8")

    run = world.run("list")

    assert "WARNING" in run.out
    assert "spot_mainnet" in run.out


def test_the_script_refuses_to_run_unless_it_is_root(world: World) -> None:
    for args in (["add"], ["remove", "futures_mainnet"], ["list"]):
        run = world.run(*args, answers=typed("futures_mainnet"), euid="1000")

        assert run.code != 0
        assert "root" in run.err
    assert list(world.credentials.iterdir()) == []


def test_the_script_refuses_when_the_credentials_directory_is_missing(
    world: World,
) -> None:
    world.credentials.rmdir()

    run = world.run("add", answers=typed("futures_mainnet"))

    assert run.code != 0
    assert "does not exist" in run.err
    assert "runbook" in run.err


def test_an_unknown_venue_or_command_is_a_usage_error(world: World) -> None:
    assert world.run("add", "nonsense").code != 0
    assert world.run("remove", "nonsense").code != 0
    assert world.run("remove").code == 2
    assert world.run("frobnicate").code == 2
    assert world.run().code == 2


def test_the_next_steps_name_the_restart_the_recovering_bots_and_the_resume_line(
    world: World,
) -> None:
    run = world.run("add", answers=typed("futures_mainnet"))

    assert "sudo systemctl restart sew-run" in run.out
    assert "RECOVERING" in run.out
    assert "bot resume <id> [--confirm-venue <venue>]" in run.out
    assert "did not restart" in run.out


def test_a_failed_publish_leaves_no_temporary_file_and_the_old_key_in_place(
    world: World,
) -> None:
    world.seed_mainnet("futures_mainnet")
    world.mainnet("futures_mainnet", "secret").unlink()
    world.mainnet(
        "futures_mainnet", "secret"
    ).mkdir()  # a directory: the rename cannot replace it

    run = world.run("add", answers=typed("futures_mainnet"))

    assert run.code != 0
    assert world.mainnet("futures_mainnet", "key").exists()
    assert world.leftovers() == []
    nothing_leaked(run)


def test_a_secret_that_cannot_be_published_puts_the_old_key_back(
    world: World, tmp_path: Path
) -> None:
    """The failure between the two renames: a new key beside an old secret would be a pair
    the exchange refuses, found only at the next restart."""
    world.seed_mainnet("futures_mainnet")
    shim = tmp_path / "shim"
    shim.mkdir()
    mv = shim / "mv"
    real_mv = require_tool("mv")
    mv.write_text(
        f'#!/bin/sh\ncase "$*" in *_api_secret) exit 1;; esac\nexec {real_mv} "$@"\n',
        encoding="utf-8",
    )
    mv.chmod(0o755)

    run = world.run(
        "add", answers=typed("futures_mainnet"), path=f"{shim}:{os.environ['PATH']}"
    )

    assert run.code != 0
    assert "old key was put back" in run.err
    assert (
        world.mainnet("futures_mainnet", "key").read_text(encoding="utf-8") == OLD_KEY
    )
    assert (
        world.mainnet("futures_mainnet", "secret").read_text(encoding="utf-8")
        == OLD_SECRET
    )
    assert world.leftovers() == []
    nothing_leaked(run)
