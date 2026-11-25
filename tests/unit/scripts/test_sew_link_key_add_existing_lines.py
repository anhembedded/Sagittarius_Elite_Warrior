"""`EPIC-047G` - `sew-link-key add` against a file that already has lines: the same key found whatever its line looks like, and a
file the tool will not write through (a symlink, another owner).

Mutation checks (each turns a test here red): the duplicate test loosened to a substring, the foreign-line refusal removed, the
symlink or ownership refusal removed, `chown` without `-h`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.tests.unit.scripts.sew_link_key_world import World


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(tmp_path)


def test_a_comment_line_holding_the_key_does_not_count_as_installed(
    world: World,
) -> None:
    key = world.make_key("desk")
    world.ssh.mkdir(mode=0o700)
    old = f"# old copy: {key.read_text(encoding='utf-8').strip()}\n"
    world.auth.write_text(old, encoding="utf-8")

    run = world.run("add", str(key))

    assert run.code == 0, run.err
    assert "already installed" not in run.out
    assert world.auth_lines() == [old.strip(), world.restricted_line(key)]


def test_the_same_key_on_a_line_that_is_not_the_bridge_restriction_is_a_refusal(
    world: World,
) -> None:
    key = world.make_key("desk")
    world.ssh.mkdir(mode=0o700)
    loose = f'command="/bin/sh" {key.read_text(encoding="utf-8").strip()}\n'
    world.auth.write_text(loose, encoding="utf-8")

    run = world.run("add", str(key))

    assert run.code == 2
    assert "NOT the bridge restriction" in run.err
    assert world.auth.read_text(encoding="utf-8") == loose


def test_a_longer_key_with_the_same_start_is_not_taken_for_the_installed_one(
    world: World,
) -> None:
    key = world.make_key("desk")
    body = world.body_of(key)
    world.ssh.mkdir(mode=0o700)
    other = f'restrict,command="{world.launcher}" ssh-ed25519 {body}EXTRA other\n'
    world.auth.write_text(other, encoding="utf-8")

    run = world.run("add", str(key))

    assert run.code == 0, run.err
    assert len(world.auth_lines()) == 2


def test_a_symlinked_ssh_directory_is_refused_and_its_target_is_left_alone(
    world: World,
) -> None:
    key = world.make_key("desk")
    target = world.root / "elsewhere"
    target.mkdir(mode=0o755)
    world.ssh.symlink_to(target)

    run = world.run("add", str(key))

    assert run.code == 2
    assert "symbolic link" in run.err
    assert world.mode(target) == 0o755
    assert list(target.iterdir()) == []


def test_a_symlinked_authorized_keys_is_refused_and_its_target_is_left_alone(
    world: World,
) -> None:
    key = world.make_key("desk")
    world.ssh.mkdir(mode=0o700)
    target = world.root / "somewhere-else"
    target.write_text("untouched\n", encoding="utf-8")
    world.auth.symlink_to(target)

    run = world.run("add", str(key))

    assert run.code == 2
    assert "symbolic link" in run.err
    assert target.read_text(encoding="utf-8") == "untouched\n"


@pytest.mark.parametrize(
    "separator",
    ["\t", "   ", " \t "],
    ids=["tab", "spaces", "mixed"],
)
def test_an_unrestricted_line_for_the_same_key_is_found_whatever_whitespace_it_uses(
    world: World, separator: str
) -> None:
    key = world.make_key("desk")
    kind, body = key.read_text(encoding="utf-8").split()[:2]
    world.ssh.mkdir(mode=0o700)
    loose = f"{kind}{separator}{body} own\n"
    world.auth.write_text(loose, encoding="utf-8")

    run = world.run("add", str(key))

    assert run.code == 2
    assert "NOT the bridge restriction" in run.err
    assert world.auth.read_text(encoding="utf-8") == loose


def test_a_line_with_options_of_its_own_for_the_same_key_is_found(world: World) -> None:
    key = world.make_key("desk")
    world.ssh.mkdir(mode=0o700)
    optioned = f'from="10.0.0.1",no-pty {key.read_text(encoding="utf-8").strip()}\n'
    world.auth.write_text(optioned, encoding="utf-8")

    run = world.run("add", str(key))

    assert run.code == 2
    assert world.auth.read_text(encoding="utf-8") == optioned


def test_our_own_line_with_odd_whitespace_after_the_restriction_still_counts_as_installed(
    world: World,
) -> None:
    key = world.make_key("desk")
    world.run("add", str(key))
    again = world.run("add", "--comment", "renamed", str(key))

    assert "already installed" in again.out
    assert len(world.auth_lines()) == 1


def test_the_ownership_check_runs_for_a_real_root_and_a_file_of_another_owner_is_refused(
    world: World,
) -> None:
    key = world.make_key("desk")
    world.ssh.mkdir(mode=0o700)
    owner_is_mallory = (
        'if [ "$1" = "-c" ] && [ "$2" = "%U" ]; then echo mallory; exit 0; fi\n'
        'exec /usr/bin/stat "$@"'
    )

    run = world.run("add", str(key), shims={"stat": owner_is_mallory}, real_chown=True)

    assert run.code == 2
    assert "owned by mallory" in run.err
    assert not world.auth.exists()


def test_the_script_never_follows_a_link_when_it_hands_a_file_to_the_account(
    world: World,
) -> None:
    key = world.make_key("desk")
    record = world.root / "chown.args"
    chown = f'echo "$@" >> "{record}"'

    world.run("add", str(key), shims={"chown": chown}, real_chown=True)

    calls = record.read_text(encoding="utf-8").splitlines()
    assert calls
    assert all(call.startswith("-h sew:sew ") for call in calls)
