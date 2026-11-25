"""`EPIC-047G` - `sew-link-key list`, `remove` and `shell`: what is installed, removing exactly one key, and the account's login shell
as its own command (the owner's decision of 2026-11-25: the guard shell, never /bin/sh)."""

from __future__ import annotations

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.tests.unit.scripts.sew_link_key_world import World


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(tmp_path)


def _two_keys(world: World) -> tuple[Path, Path]:
    one, two = world.make_key("one", "one"), world.make_key("two", "two")
    world.run("add", str(one))
    world.run("add", str(two))
    return one, two


def test_list_names_each_key_by_fingerprint_with_its_comment_and_never_the_key(
    world: World,
) -> None:
    one, _two = _two_keys(world)

    run = world.run("list")

    assert run.code == 0
    assert run.out.count("SHA256:") == 2
    assert "restricted to the bridge" in run.out
    assert "one" in run.out
    assert world.body_of(one) not in run.out


def test_list_flags_a_line_that_is_not_the_bridge_restriction(world: World) -> None:
    world.ssh.mkdir(mode=0o700)
    key = world.make_key("own", "own")
    world.auth.write_text(key.read_text(encoding="utf-8"), encoding="utf-8")

    run = world.run("list")

    assert "NOT installed by sew-link-key" in run.out


def test_list_of_nothing_says_so(world: World) -> None:
    assert "no key" in world.run("list").out


def test_remove_by_comment_removes_that_key_and_only_that_key(world: World) -> None:
    one, two = _two_keys(world)

    run = world.run("remove", "two")

    assert run.code == 0, run.err
    assert world.auth_lines() == [world.restricted_line(one, "one")]
    assert world.mode(world.auth) == 0o600
    assert world.leftovers() == []
    assert world.body_of(two) not in run.out


def test_remove_by_fingerprint(world: World) -> None:
    one, _two = _two_keys(world)
    fingerprint = next(
        word for word in world.run("list").out.split() if word.startswith("SHA256:")
    )

    world.run("remove", fingerprint)

    assert len(world.auth_lines()) == 1
    assert world.body_of(one) not in "".join(world.auth_lines())
    assert fingerprint not in world.run("list").out


def test_remove_refuses_a_comment_that_names_two_keys(world: World) -> None:
    one, two = world.make_key("one", "same"), world.make_key("two", "same")
    world.run("add", str(one))
    world.run("add", str(two))

    run = world.run("remove", "same")

    assert run.code == 2
    assert "2 keys" in run.err
    assert len(world.auth_lines()) == 2


def test_remove_of_an_unknown_key_is_a_refusal_and_changes_nothing(
    world: World,
) -> None:
    _two_keys(world)
    before = world.auth.read_bytes()

    run = world.run("remove", "nobody")

    assert run.code == 2
    assert world.auth.read_bytes() == before


def test_remove_dry_run_changes_nothing(world: World) -> None:
    _two_keys(world)
    before = world.auth.read_bytes()

    run = world.run("remove", "--dry-run", "one")

    assert run.code == 0
    assert "would" in run.out
    assert world.auth.read_bytes() == before


def test_remove_leaves_other_lines_alone(world: World) -> None:
    key = world.make_key("desk", "desk")
    world.run("add", str(key))
    with open(world.auth, "a", encoding="utf-8") as handle:
        handle.write("# the owner's note\n")

    world.run("remove", "desk")

    assert world.auth.read_text(encoding="utf-8") == "# the owner's note\n"


# -- the login shell -----------------------------------------------------------------------


def test_shell_set_installs_the_guard_lists_it_and_changes_the_account(
    world: World,
) -> None:
    run = world.run("shell", "set")

    assert run.code == 0, run.err
    assert world.guard.read_bytes() == world.guard_source.read_bytes()
    assert world.mode(world.guard) == 0o755
    assert str(world.guard) in world.shells.read_text(encoding="utf-8").splitlines()
    assert f"sew:x:990:990::{world.home}:{world.guard}" in world.passwd.read_text()
    assert "UNPROVEN" in run.out


def test_shell_set_twice_lists_the_guard_once(world: World) -> None:
    world.run("shell", "set")
    world.run("shell", "set")

    assert world.shells.read_text().splitlines().count(str(world.guard)) == 1


def test_shell_set_supplies_a_newline_a_shells_file_lacked(world: World) -> None:
    world.shells.write_text("/bin/sh", encoding="utf-8")

    world.run("shell", "set")

    assert world.shells.read_text().splitlines() == ["/bin/sh", str(world.guard)]


def test_shell_set_dry_run_changes_nothing(world: World) -> None:
    before = world.passwd.read_text()

    run = world.run("shell", "set", "--dry-run")

    assert run.code == 0
    assert "would" in run.out
    assert not world.guard.exists()
    assert world.passwd.read_text() == before
    assert not world.calls.exists()


def test_shell_set_dry_run_on_a_host_already_set_has_nothing_to_add_to_the_shells_file(
    world: World,
) -> None:
    world.run("shell", "set")

    run = world.run("shell", "set", "--dry-run")

    assert "would: add" not in run.out


def test_shell_unset_puts_nologin_back_and_removes_the_guard(world: World) -> None:
    world.run("shell", "set")

    run = world.run("shell", "unset")

    assert run.code == 0, run.err
    assert "/usr/sbin/nologin" in world.passwd.read_text()
    assert not world.guard.exists()
    assert str(world.guard) not in world.shells.read_text()


def test_shell_show_says_which_it_is(world: World) -> None:
    assert "nologin" in world.run("shell", "show").out
    world.run("shell", "set")
    assert "(guard)" in world.run("shell", "show").out
    world.set_account_shell("/bin/sh")
    assert "(other:/bin/sh)" in world.run("shell", "show").out


def test_shell_set_refuses_without_root_or_without_the_account(world: World) -> None:
    assert world.run("shell", "set", euid="1000").code == 2
    world.passwd.write_text("root:x:0:0:root:/root:/bin/bash\n", encoding="utf-8")
    assert world.run("shell", "set").code == 2
    assert not world.guard.exists()


def test_shell_set_refuses_when_the_checkout_has_no_guard_to_install(
    world: World,
) -> None:
    world.guard_source.unlink()

    run = world.run("shell", "set")

    assert run.code == 2
    assert "sew-update" in run.err


def test_remove_refuses_a_symlinked_ssh_directory_that_holds_the_key(
    world: World,
) -> None:
    key = world.make_key("desk", "desk")
    world.run("add", str(key))
    target = world.root / "elsewhere"
    world.ssh.rename(target)
    world.ssh.symlink_to(target)
    before = (target / "authorized_keys").read_bytes()

    run = world.run("remove", "desk")

    assert run.code == 2
    assert "symbolic link" in run.err
    assert (target / "authorized_keys").read_bytes() == before
