"""`BOT-204` - `deploy/linux/sew-update`: see `deploy_world.py` for the setup.

The order is the point: since BOT-203 the new unit may only be installed after the code it
goes with. The stand-ins stamp each step with what the checkout and the installed unit were at
that moment, so the order is read from the log, not assumed.
"""

from __future__ import annotations

import hashlib

from Sagittarius_Elite_Warrior.tests.unit.scripts.deploy_world import (
    DEPLOY,
    DeployWorld,
)

_NEW_UNIT = (DEPLOY / "sew-run.service").read_text(encoding="utf-8") + "# release 2\n"


def _md5(text: str) -> str:
    return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()[:8]


def _running_host_with_a_new_release(deploy: DeployWorld) -> str:
    return deploy.running_with_a_new_release(_NEW_UNIT)


def test_the_unit_is_installed_only_after_the_code_it_goes_with(
    deploy: DeployWorld,
) -> None:
    second = _running_host_with_a_new_release(deploy)
    old_unit = _md5((deploy.unit_dir / "sew-run.service").read_text(encoding="utf-8"))

    run = deploy.update()

    assert run.code == 0, run.err + run.out
    assert deploy.head() == second
    assert (deploy.unit_dir / "sew-run.service").read_text(
        encoding="utf-8"
    ) == _NEW_UNIT
    lines = deploy.lines()
    commands = [
        line
        for line in lines
        if not line.startswith(("pip-saw", "checkout-saw", "systemctl-saw"))
    ]
    names = [c.split()[0] + " " + " ".join(c.split()[1:2]) for c in commands]
    stop = names.index("systemctl stop")
    start = names.index("systemctl start")
    assert (
        stop
        < names.index("venv-pip install")
        < names.index("systemctl daemon-reload")
        < start
    )
    assert names.index("systemctl cat") < start
    # at the pip install the checkout is the new release and the installed unit is still the old one
    [pip] = deploy.calls("pip-saw")
    assert f"checkout={deploy.short_head()}" in pip
    assert f"unit={old_unit}" in pip
    # at the daemon-reload the installed unit is the new one
    [reload_] = deploy.calls("systemctl-saw")
    assert reload_ == f"systemctl-saw unit={_md5(_NEW_UNIT)}"
    engine = [c for c in lines if "engine_pin.py" in c or "compileall" in c]
    assert len(engine) == 2
    assert lines.index(engine[1]) < lines.index("systemctl daemon-reload")


def test_it_stops_copies_the_state_and_takes_the_dated_archive_before_it_changes_code(
    deploy: DeployWorld,
) -> None:
    _running_host_with_a_new_release(deploy)
    first = deploy.short_head()

    run = deploy.update()

    assert run.code == 0, run.err + run.out
    [copy] = (deploy.root / "var" / "lib" / "sew").glob("state.before-*")
    assert (copy / "bots" / "44wa1x.json").read_text(
        encoding="utf-8"
    ) == '{"id": "44wa1x"}'
    [taken] = deploy.calls("sew-backup")
    assert f"root={deploy.root}" in taken
    assert f"dir={deploy.root}/var/backups/sew" in taken
    assert taken.endswith(f"head={first}")
    assert deploy.lines().index("systemctl stop sew-run") < deploy.lines().index(taken)


def test_the_credentials_line_is_checked_before_the_start(deploy: DeployWorld) -> None:
    _running_host_with_a_new_release(deploy)

    run = deploy.update()

    assert run.code == 0
    lines = deploy.lines()
    assert lines.index("systemctl cat sew-run") < lines.index("systemctl start sew-run")


def test_a_drop_in_that_sets_the_credentials_line_is_refused_before_the_stop(
    deploy: DeployWorld,
) -> None:
    _running_host_with_a_new_release(deploy)
    drop_in = deploy.unit_dir / "sew-run.service.d"
    drop_in.mkdir()
    (drop_in / "reset.conf").write_text(
        "[Service]\nLoadCredential=\n", encoding="utf-8"
    )
    before = deploy.head()

    run = deploy.update()

    assert run.code == 2
    assert "reset.conf sets LoadCredential=" in run.err
    assert "nothing was stopped or changed" in run.err
    assert deploy.calls("systemctl stop") == []
    assert deploy.head() == before


def test_the_preflight_lines_and_the_recovering_reminder_are_printed_after_the_start(
    deploy: DeployWorld,
) -> None:
    _running_host_with_a_new_release(deploy)

    run = deploy.update()

    assert "[preflight] credentials-present: ok" in run.out
    assert "[recovering] bot 44wa1x" in run.out
    assert "RECOVERING" in run.out
    assert "M bot resume <id>" in run.out
    joined = "\n".join(deploy.lines())
    assert "bot resume" not in joined
    assert "resume" not in joined.replace("--resume-", "")


def test_a_host_that_was_not_running_stays_stopped(deploy: DeployWorld) -> None:
    deploy.installed()
    deploy.commit("release 2")

    run = deploy.update()

    assert run.code == 0, run.err + run.out
    assert "systemctl stop sew-run" not in deploy.lines()
    assert "systemctl start sew-run" not in deploy.lines()
    assert "did not run before" in run.out


def test_no_start_leaves_a_running_host_stopped(deploy: DeployWorld) -> None:
    _running_host_with_a_new_release(deploy)

    run = deploy.update("--no-start")

    assert run.code == 0, run.err + run.out
    assert "systemctl start sew-run" not in deploy.lines()
    assert "--no-start" in run.out


def test_the_default_ref_is_the_remote_master_and_a_tag_or_a_sha_is_taken_as_given(
    deploy: DeployWorld,
) -> None:
    deploy.installed()
    first = deploy.head()
    deploy.tag("v1")
    second = deploy.commit("release 2")
    third = deploy.commit("release 3")

    assert deploy.update().code == 0
    assert deploy.head() == third
    assert deploy.update("v1").code == 0
    assert deploy.head() == first
    assert deploy.update(second).code == 0
    assert deploy.head() == second


def test_a_bare_branch_name_means_the_remote_branch_not_a_stale_local_one(
    deploy: DeployWorld,
) -> None:
    deploy.installed()
    stale = deploy.head()
    newest = deploy.commit("release 2")
    assert stale != newest

    run = deploy.update("master-warrior")

    assert run.code == 0, run.err + run.out
    assert deploy.head() == newest


def test_an_unknown_ref_is_refused_before_anything_stops(deploy: DeployWorld) -> None:
    _running_host_with_a_new_release(deploy)
    before = deploy.head()

    run = deploy.update("no-such-ref")

    assert run.code == 2
    assert "names no commit" in run.err
    assert deploy.calls("systemctl stop") == []
    assert deploy.head() == before


def test_a_local_edit_the_release_would_overwrite_is_refused_before_the_stop(
    deploy: DeployWorld,
) -> None:
    deploy.installed()
    deploy.set_state("active")
    deploy.commit(
        "release 2", **{"src__config__user_config.json": '{"changed": true}\n'}
    )
    config = deploy.checkout / "src" / "config" / "user_config.json"
    config.write_text('{"bots.account_loss_cap": "500 USDT"}\n', encoding="utf-8")
    before = deploy.head()

    run = deploy.update()

    assert run.code == 2
    assert "src/config/user_config.json" in run.err
    assert "nothing was stopped or changed" in run.err
    assert deploy.calls("systemctl stop") == []
    assert deploy.head() == before
    assert (
        config.read_text(encoding="utf-8") == '{"bots.account_loss_cap": "500 USDT"}\n'
    )


def test_a_local_edit_the_release_leaves_alone_is_kept(deploy: DeployWorld) -> None:
    deploy.installed()
    deploy.commit("release 2", **{"README.md": "release 2\n"})
    config = deploy.checkout / "src" / "config" / "user_config.json"
    config.write_text('{"bots.account_loss_cap": "500 USDT"}\n', encoding="utf-8")

    run = deploy.update()

    assert run.code == 0, run.err + run.out
    assert (deploy.checkout / "README.md").read_text(encoding="utf-8") == "release 2\n"
    assert (
        config.read_text(encoding="utf-8") == '{"bots.account_loss_cap": "500 USDT"}\n'
    )
    assert "your local edits are kept" in run.out


def test_dry_run_changes_nothing(deploy: DeployWorld) -> None:
    _running_host_with_a_new_release(deploy)
    before_files = deploy.snapshot()
    before = deploy.head()
    deploy.log.write_text("", encoding="utf-8")

    run = deploy.update("--dry-run")

    assert run.code == 0, run.err + run.out
    assert deploy.snapshot() == before_files
    assert deploy.head() == before
    assert "would:" in run.out
    assert "Dry run: nothing was changed." in run.out
    for mutation in (
        "systemctl stop",
        "systemctl start",
        "venv-pip",
        "systemctl daemon-reload",
    ):
        assert deploy.calls(mutation) == [], mutation


def test_it_needs_an_installation_and_root(deploy: DeployWorld) -> None:
    bare = deploy.update()
    deploy.installed()
    unprivileged = deploy.update(euid="1000")

    assert bare.code == 2
    assert "run sew-install first" in bare.err
    assert unprivileged.code == 2
    assert "run this as root" in unprivileged.err


def test_it_refreshes_the_links_the_profile_and_the_backup_units_of_an_older_install(
    deploy: DeployWorld,
) -> None:
    """The first run on a host installed by hand (runbook section 2): the profile, the links
    and the backup units are new to it, and the backup timer is enabled once."""
    deploy.installed()
    for path in (
        deploy.root / "etc" / "profile.d" / "sew.sh",
        deploy.unit_dir / "sew-backup.service",
        deploy.unit_dir / "sew-backup.timer",
        deploy.sbin / "sew-update",
    ):
        path.unlink()
    deploy.commit("release 2")

    run = deploy.update()

    assert run.code == 0, run.err + run.out
    assert (deploy.root / "etc" / "profile.d" / "sew.sh").read_bytes() == (
        DEPLOY / "sew-profile.sh"
    ).read_bytes()
    assert (deploy.sbin / "sew-update").is_symlink()
    assert "systemctl enable --now sew-backup.timer" in deploy.lines()


def test_the_script_of_another_clone_upgrades_the_installed_checkout_not_itself(
    deploy: DeployWorld,
) -> None:
    """The adoption path: the world runs the repository's script, which is not the installed
    checkout, and it is the installed checkout that moves."""
    deploy.installed()
    newest = deploy.commit("release 2")
    assert deploy.checkout != DEPLOY.parents[1]

    run = deploy.update()

    assert run.code == 0, run.err + run.out
    assert deploy.head() == newest


def test_a_host_restarting_after_a_crash_is_stopped_so_it_cannot_start_under_the_upgrade(
    deploy: DeployWorld,
) -> None:
    deploy.installed()
    deploy.set_state("activating")
    deploy.set_state("result", "exit-code")
    deploy.set_state("main_status", "1")
    newest = deploy.commit("release 2")

    run = deploy.update()

    assert run.code == 0, run.err + run.out
    assert deploy.head() == newest
    assert "restarting after a failure" in run.out
    lines = deploy.lines()
    assert lines.index("systemctl stop sew-run") < lines.index(
        deploy.calls("venv-pip")[0]
    )
    assert "systemctl start sew-run" in lines
