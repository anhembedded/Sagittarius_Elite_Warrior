"""`BOT-204` - `deploy/linux/sew-update` when something goes wrong: see `deploy_world.py` for the setup.

What the script does when the host never started, when a step fails past the stop, and when
the release cannot be installed: the host is left stopped, says so, and a re-run restores it.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.tests.unit.scripts.deploy_world import (
    DEPLOY,
    DeployWorld,
)

_NEW_UNIT = (DEPLOY / "sew-run.service").read_text(encoding="utf-8") + "# release 2\n"


def _running_host_with_a_new_release(deploy: DeployWorld) -> str:
    return deploy.running_with_a_new_release(_NEW_UNIT)


def test_a_host_installed_but_never_started_updates_without_an_archive(
    deploy: DeployWorld,
) -> None:
    """`sew-install` leaves no `state/`; the real `sew-backup` refuses that, the double does too."""
    deploy.installed()
    newest = deploy.commit("release 2")

    run = deploy.update()

    assert run.code == 0, run.err + run.out
    assert deploy.head() == newest
    assert deploy.calls("sew-backup") == []
    assert "no archive taken" in run.out


def test_a_rerun_after_a_failure_past_the_stop_restores_the_host_and_names_the_old_release(
    deploy: DeployWorld,
) -> None:
    _running_host_with_a_new_release(deploy)
    original = deploy.head()
    deploy.set_state("pip_fails")

    failed = deploy.update()

    assert failed.code == 1
    assert "AFTER the host was stopped" in failed.err
    assert "systemctl start sew-run" in failed.err
    assert (deploy.root / "opt" / "sew" / ".sew-update-pending").is_file()
    deploy.clear_state("pip_fails")

    again = deploy.update()

    assert again.code == 0, again.err + again.out
    assert "restores it" in again.out
    assert "systemctl start sew-run" in deploy.lines()
    assert "RECOVERING" in again.out
    assert f"Rollback: sudo sew-update {original}" in again.out
    assert not (deploy.root / "opt" / "sew" / ".sew-update-pending").exists()


def test_a_clean_update_leaves_no_marker(deploy: DeployWorld) -> None:
    _running_host_with_a_new_release(deploy)

    assert deploy.update().code == 0

    assert not (deploy.root / "opt" / "sew" / ".sew-update-pending").exists()


def test_a_host_that_did_not_drain_stops_the_upgrade_before_any_change(
    deploy: DeployWorld,
) -> None:
    _running_host_with_a_new_release(deploy)
    deploy.set_state("main_status", "1")
    before = deploy.head()

    run = deploy.update()

    assert run.code == 1
    assert "did not drain cleanly" in run.err
    assert "sew-run is NOT running" in run.err
    assert deploy.head() == before
    assert deploy.calls("venv-pip") == []
    assert deploy.calls("systemctl start") == []


def test_a_start_that_fails_prints_the_log_and_exits_1(deploy: DeployWorld) -> None:
    _running_host_with_a_new_release(deploy)
    deploy.set_state("start_fails")

    run = deploy.update()

    assert run.code == 1
    assert "[preflight] credentials-present: ok" in run.out
    assert "did not start" in run.err


def test_a_release_without_the_install_files_fails_with_the_rollback_command(
    deploy: DeployWorld,
) -> None:
    deploy.installed()
    before = deploy.head()
    bare = deploy.drop_from_origin("deploy/linux/sew-update")

    run = deploy.update(bare)

    assert run.code == 1
    assert "predates the install scripts" in run.err
    assert f"sudo sew-update {before}" in run.err
