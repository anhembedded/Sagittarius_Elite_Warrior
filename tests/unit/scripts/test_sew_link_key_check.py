"""`EPIC-047G` - `sew-link-key check` verifies the install end to end without a key, never changes anything, says what is
unproven, and prints the sshd drop-in and the PasswordAuthentication step instead of doing them."""

from __future__ import annotations

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.tests.unit.scripts.sew_link_key_world import World


@pytest.fixture
def ready(tmp_path: Path) -> World:
    """A host where every step is done: the guard shell set, one key added."""
    world = World(tmp_path)
    world.run("shell", "set")
    world.run("add", str(world.make_key("desk")))
    return world


def _snapshot(world: World) -> dict[str, bytes]:
    return {
        str(p.relative_to(world.root)): p.read_bytes()
        for p in world.root.rglob("*")
        if p.is_file() and not p.name.startswith("id")
    }


def test_a_host_set_up_by_the_steps_passes_and_says_it_is_unproven(
    ready: World,
) -> None:
    run = ready.run("check")

    assert run.code == 0, run.out
    assert "FAIL" not in run.out
    assert "UNPROVEN" in run.out
    assert "section 14.6, row 1" in run.out


def test_it_prints_the_password_step_and_never_does_it(ready: World) -> None:
    run = ready.run("check")

    assert "PasswordAuthentication no" in run.out
    assert "sshd_config.d/50-sew-keys-only.conf" in run.out
    assert "NEW window" in run.out


def test_a_check_changes_nothing(ready: World) -> None:
    before = _snapshot(ready)

    ready.run("check")

    assert _snapshot(ready) == before


def test_the_nologin_shell_is_a_failure_with_the_command_that_fixes_it(
    ready: World,
) -> None:
    ready.set_account_shell("/usr/sbin/nologin")

    run = ready.run("check")

    assert run.code == 1
    assert "FAIL  login shell is /usr/sbin/nologin" in run.out
    assert "sew-link-key shell set" in run.out


def test_a_general_shell_is_a_failure_the_owner_chose_against(ready: World) -> None:
    ready.set_account_shell("/bin/sh")

    run = ready.run("check")

    assert run.code == 1
    assert "never /bin/sh" in run.out


def test_a_missing_account_is_a_failure(ready: World) -> None:
    ready.passwd.write_text("root:x:0:0:root:/root:/bin/bash\n", encoding="utf-8")

    run = ready.run("check")

    assert run.code == 1
    assert "no account" in run.out


def test_a_guard_the_account_could_write_is_a_failure(ready: World) -> None:
    ready.guard.chmod(0o775)

    run = ready.run("check")

    assert run.code == 1
    assert "writable by group or others" in run.out


def test_a_guard_that_differs_from_the_checkouts_is_a_failure(ready: World) -> None:
    ready.guard.write_text(ready.guard.read_text() + "\n# edited\n", encoding="utf-8")

    run = ready.run("check")

    assert run.code == 1
    assert "differs from the checkout" in run.out


def test_a_guard_for_another_launcher_is_a_failure(ready: World) -> None:
    moved = ready.root / "elsewhere" / "sew-bridge"
    moved.parent.mkdir()
    moved.write_text("#!/bin/sh\n", encoding="utf-8")
    moved.chmod(0o755)

    run = ready.run("check", extra_env={"SEW_LINK_LAUNCHER": str(moved)})

    assert run.code == 1
    assert "names another launcher" in run.out


def test_a_launcher_that_is_not_executable_is_a_failure(ready: World) -> None:
    ready.launcher.chmod(0o644)

    run = ready.run("check")

    assert run.code == 1
    assert "not executable" in run.out


@pytest.mark.parametrize("which", ["dir", "file"])
def test_loose_modes_are_failures(ready: World, which: str) -> None:
    target = ready.ssh if which == "dir" else ready.auth
    target.chmod(0o755 if which == "dir" else 0o644)

    run = ready.run("check")

    assert run.code == 1
    assert "FAIL" in run.out


def test_a_line_that_is_not_the_bridge_restriction_is_a_warning(ready: World) -> None:
    with open(ready.auth, "a", encoding="utf-8") as handle:
        handle.write(ready.make_key("own", "own").read_text(encoding="utf-8"))

    run = ready.run("check")

    assert run.code == 0
    assert "WARN  1 line(s) are not the bridge restriction" in run.out


def test_usepam_no_is_a_failure_because_sshd_then_refuses_a_locked_account(
    ready: World,
) -> None:
    ready.set_sshd(usepam="no")

    run = ready.run("check")

    assert run.code == 1
    assert "UsePAM is not yes" in run.out


def test_pubkey_authentication_off_is_a_failure(ready: World) -> None:
    ready.set_sshd(pubkeyauthentication="no")

    assert ready.run("check").code == 1


def test_another_key_file_than_the_homes_is_a_failure(ready: World) -> None:
    ready.set_sshd(authorizedkeysfile="/etc/ssh/keys/%u")

    run = ready.run("check")

    assert run.code == 1
    assert "not .ssh/authorized_keys" in run.out


def test_forwarding_left_on_is_a_warning_with_the_drop_in_to_place(
    ready: World,
) -> None:
    ready.set_sshd(allowtcpforwarding="yes", permittty="yes")

    run = ready.run("check")

    assert run.code == 0
    assert "WARN  sshd does not forbid for sew: allowtcpforwarding permittty" in run.out
    assert "Match User sew" in run.out
    assert "AllowTcpForwarding no" in run.out
    assert "/etc/ssh/sshd_config.d/60-sew-link.conf" in run.out


def test_an_allow_list_without_the_account_is_a_warning(ready: World) -> None:
    ready.set_sshd(allowusers="alice bob")

    run = ready.run("check")

    assert "WARN  AllowUsers/AllowGroups is set" in run.out


def test_an_sshd_that_cannot_answer_is_a_warning_not_a_pass_or_a_crash(
    ready: World,
) -> None:
    run = ready.run("check", extra_env={"SEW_LINK_SSHD": "/bin/false"})

    assert run.code == 0
    assert "could not ask sshd" in run.out


def test_check_needs_root_because_the_ssh_directory_is_the_accounts(
    ready: World,
) -> None:
    run = ready.run("check", euid="1000")

    assert run.code == 2
