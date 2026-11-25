"""`EPIC-047G` - `sew-link-key add` installs one restricted line for one public key and refuses everything else.

Mutation checks (each turns a test here red): the `restrict` option dropped from the line, a private key accepted, a
second key replacing the first, a mode loosened, a line appended without a newline, other lines touched.
"""

from __future__ import annotations

import fcntl
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.tests.unit.scripts.sew_link_key_world import World


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(tmp_path)


def test_it_installs_exactly_the_restricted_line_the_remote_link_proved(
    world: World,
) -> None:
    key = world.make_key("desk", "Win desk")

    run = world.run("add", "--comment", "desk-windows", str(key))

    assert run.code == 0, run.err
    assert world.auth_lines() == [world.restricted_line(key, "desk-windows")]
    assert world.auth_lines()[0].startswith(
        f'restrict,command="{world.launcher}" ssh-ed25519 '
    )


def test_the_file_and_its_directory_are_owner_only(world: World) -> None:
    key = world.make_key("desk")

    world.run("add", str(key))

    assert world.mode(world.ssh) == 0o700
    assert world.mode(world.auth) == 0o600
    assert world.leftovers() == []


def test_the_same_key_twice_is_one_line_and_the_file_is_unchanged(world: World) -> None:
    key = world.make_key("desk")
    world.run("add", str(key))
    before = world.auth.read_bytes()

    again = world.run("add", "--comment", "another-name", str(key))

    assert again.code == 0
    assert "already installed" in again.out
    assert world.auth.read_bytes() == before


def test_a_second_key_is_added_and_never_replaces_the_first(world: World) -> None:
    first, second = world.make_key("one", "one"), world.make_key("two", "two")
    world.run("add", str(first))

    world.run("add", str(second))

    assert world.auth_lines() == [
        world.restricted_line(first, "one"),
        world.restricted_line(second, "two"),
    ]


def test_other_lines_are_kept_byte_for_byte_and_a_missing_newline_is_supplied(
    world: World,
) -> None:
    world.ssh.mkdir(mode=0o700)
    foreign = "# the owner's own\nssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFOREIGN owner@elsewhere"
    world.auth.write_text(foreign, encoding="utf-8")
    key = world.make_key("desk")

    world.run("add", str(key))

    text = world.auth.read_text(encoding="utf-8")
    assert text == f"{foreign}\n{world.restricted_line(key)}\n"


def test_a_loose_directory_is_set_back_to_owner_only(world: World) -> None:
    world.ssh.mkdir(mode=0o755)
    world.ssh.chmod(0o755)
    key = world.make_key("desk")

    world.run("add", str(key))

    assert world.mode(world.ssh) == 0o700


def test_the_output_and_the_log_name_a_fingerprint_and_never_the_key(
    world: World,
) -> None:
    key = world.make_key("desk")

    run = world.run("add", str(key))

    assert "SHA256:" in run.out
    assert world.body_of(key) not in run.out + run.err


def test_a_key_from_standard_input_and_a_windows_file_are_accepted(
    world: World,
) -> None:
    key = world.make_key("desk")
    crlf = key.read_text(encoding="utf-8").rstrip("\n") + "\r\n"

    run = world.run("add", "-", stdin=crlf)

    assert run.code == 0, run.err
    assert world.auth_lines() == [world.restricted_line(key)]


def test_the_comment_is_sanitized_so_it_cannot_carry_an_option(world: World) -> None:
    key = world.make_key("desk")

    world.run("add", "--comment", 'x" command="evil', str(key))

    (line,) = world.auth_lines()
    assert line.count("command=") == 1
    assert '"evil' not in line
    assert line.startswith(f'restrict,command="{world.launcher}" ')


def _refused(world: World, run_code: int, run_err: str) -> None:
    assert run_code == 2, run_err
    assert not world.auth.exists() or world.auth_lines() == []
    assert world.leftovers() == []


def test_a_private_key_is_refused_and_never_echoed(world: World) -> None:
    key = world.make_key("desk")
    private = Path(str(key).removesuffix(".pub"))

    run = world.run("add", str(private))

    _refused(world, run.code, run.err)
    assert "PRIVATE" in run.err
    assert "BEGIN" not in run.out + run.err


def test_a_private_key_on_standard_input_is_refused(world: World) -> None:
    key = world.make_key("desk")
    private = Path(str(key).removesuffix(".pub")).read_text(encoding="utf-8")

    run = world.run("add", "-", stdin=private)

    _refused(world, run.code, run.err)


def test_two_keys_in_one_file_are_refused(world: World) -> None:
    one, two = world.make_key("one"), world.make_key("two")
    both = world.root / "both.pub"
    both.write_text(one.read_text() + two.read_text(), encoding="utf-8")

    run = world.run("add", str(both))

    _refused(world, run.code, run.err)
    assert "more than one line" in run.err


@pytest.mark.parametrize(
    "prefix",
    [
        'command="/bin/sh" ',
        "restrict ",
        'from="1.2.3.4" ',
        "no-pty,",
        "cert-authority ",
    ],
    ids=["command", "restrict", "from", "no-pty", "authority"],
)
def test_a_line_with_options_of_its_own_is_refused(world: World, prefix: str) -> None:
    key = world.make_key("desk")
    optioned = world.root / "optioned.pub"
    optioned.write_text(prefix + key.read_text(), encoding="utf-8")

    run = world.run("add", str(optioned))

    _refused(world, run.code, run.err)


def test_a_certificate_is_refused(world: World) -> None:
    key = world.make_key("desk")
    body = world.body_of(key)
    cert = world.root / "cert.pub"
    cert.write_text(f"ssh-ed25519-cert-v01@openssh.com {body} desk\n", encoding="utf-8")

    run = world.run("add", str(cert))

    _refused(world, run.code, run.err)
    assert "certificate" in run.err


@pytest.mark.parametrize(
    "content",
    [
        "",
        "\n",
        "ssh-ed25519 AAAA desk\n",
        "ssh-ed25519 not-base64!! desk\n",
        "hello world\n",
    ],
    ids=["empty", "newline", "short-body", "bad-chars", "words"],
)
def test_something_that_is_not_a_public_key_is_refused(
    world: World, content: str
) -> None:
    bad = world.root / "bad.pub"
    bad.write_text(content, encoding="utf-8")

    run = world.run("add", str(bad))

    _refused(world, run.code, run.err)


def test_a_utf16_file_is_refused_with_the_reason(world: World) -> None:
    key = world.make_key("desk")
    utf16 = world.root / "utf16.pub"
    utf16.write_bytes(key.read_text(encoding="utf-8").encode("utf-16"))

    run = world.run("add", str(utf16))

    _refused(world, run.code, run.err)
    assert "NUL" in run.err


def test_a_huge_file_is_refused(world: World) -> None:
    huge = world.root / "huge.pub"
    huge.write_text("ssh-ed25519 " + "A" * 20000 + "\n", encoding="utf-8")

    run = world.run("add", str(huge))

    _refused(world, run.code, run.err)


def test_a_small_rsa_key_is_refused_and_a_large_one_accepted(world: World) -> None:
    small = world.make_key("small", kind="rsa", bits="2048")
    large = world.make_key("large", kind="rsa", bits="3072")

    refused = world.run("add", str(small))
    accepted = world.run("add", str(large))

    assert refused.code == 2
    assert accepted.code == 0, accepted.err


def test_a_dry_run_says_what_it_would_do_and_writes_nothing(world: World) -> None:
    key = world.make_key("desk")

    run = world.run("add", "--dry-run", str(key))

    assert run.code == 0
    assert "would" in run.out
    assert not world.ssh.exists()


def test_without_root_it_refuses_before_reading_anything(world: World) -> None:
    key = world.make_key("desk")

    run = world.run("add", str(key), euid="1000")

    assert run.code == 2
    assert "run this as root" in run.err
    assert not world.ssh.exists()


def test_a_missing_launcher_is_a_refusal_not_a_line_nothing_can_run(
    world: World,
) -> None:
    key = world.make_key("desk")
    world.launcher.unlink()

    run = world.run("add", str(key))

    _refused(world, run.code, run.err)
    assert "launcher" in run.err


def test_two_runs_at_once_are_refused_by_the_lock(world: World) -> None:
    key = world.make_key("desk")
    with open(world.lock, "w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)

        run = world.run("add", str(key))

    assert run.code == 2
    assert "another sew-link-key" in run.err
    assert not world.ssh.exists()


def test_a_run_that_is_really_root_refuses_a_test_override(world: World) -> None:
    run = world.run("list", real_uid="0")

    assert run.code == 2
    assert "SEW_LINK_" in run.err


def test_add_never_changes_the_login_shell_and_says_so_when_it_is_not_the_guard(
    world: World,
) -> None:
    key = world.make_key("desk")
    before = world.passwd.read_text()

    run = world.run("add", str(key))

    assert world.passwd.read_text() == before
    assert "sew-link-key shell set" in run.out
    assert "UNPROVEN" in run.out
    assert not world.calls.exists()


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
