"""`BOT-204` - `deploy/linux/sew-install`: see `deploy_world.py` for the setup.

Not provable here: a real systemd, a real `useradd` and `chown` to the `sew` account, a real
pip install and the exchange. The stand-ins record the order and the arguments instead.
"""

from __future__ import annotations

import os
import stat
import subprocess

import pytest
from Sagittarius_Elite_Warrior.tests.unit.scripts.deploy_world import (
    DEPLOY,
    DeployWorld,
)
from Sagittarius_Elite_Warrior.tests.unit.scripts.service_files_world import (
    require_tool,
)


def test_a_fresh_install_builds_the_whole_layout(deploy: DeployWorld) -> None:
    run = deploy.install()

    assert run.code == 0, run.err + run.out
    mode = lambda p: stat.S_IMODE(p.stat().st_mode)
    assert mode(deploy.root / "opt" / "sew") == 0o755
    assert mode(deploy.root / "var" / "lib" / "sew") == 0o700
    assert mode(deploy.root / "etc" / "sew") == 0o750
    assert mode(deploy.root / "etc" / "sew" / "credentials") == 0o700
    env_file = deploy.root / "etc" / "sew" / "sew.env"
    assert env_file.read_text(encoding="utf-8") == ""
    assert mode(env_file) == 0o640
    assert (deploy.checkout / ".git").is_dir()
    assert os.access(deploy.root / "opt" / "sew" / "venv" / "bin" / "python", os.X_OK)
    assert [c for c in deploy.calls("useradd")] == [
        "useradd --system --home-dir /var/lib/sew --shell /usr/sbin/nologin --user-group sew"
    ]


def test_it_installs_the_unit_the_units_the_profile_and_the_links(
    deploy: DeployWorld,
) -> None:
    run = deploy.install()

    assert run.code == 0, run.err + run.out
    for name in ("sew-run.service", "sew-backup.service", "sew-backup.timer"):
        assert (deploy.unit_dir / name).read_bytes() == (DEPLOY / name).read_bytes()
    profile = deploy.root / "etc" / "profile.d" / "sew.sh"
    assert profile.read_bytes() == (DEPLOY / "sew-profile.sh").read_bytes()
    for tool in ("sew-key", "sew-backup", "sew-update", "sew-install"):
        link = deploy.sbin / tool
        assert link.is_symlink()
        assert os.readlink(link) == str(deploy.checkout / "deploy" / "linux" / tool)
        assert os.access(link, os.X_OK)
    calls = deploy.lines()
    assert "systemctl daemon-reload" in calls
    assert "systemctl enable sew-run" in calls
    assert "systemctl enable --now sew-backup.timer" in calls


def test_the_python_stack_is_installed_under_the_lock_with_a_readable_umask(
    deploy: DeployWorld,
) -> None:
    run = deploy.install()

    assert run.code == 0, run.err + run.out
    [pip] = deploy.calls("venv-pip")
    assert "install --quiet --disable-pip-version-check -r" in pip
    assert "requirements-headless.txt -c" in pip
    assert pip.endswith("requirements.lock")
    [saw] = deploy.calls("pip-saw")
    assert saw.endswith("umask=0022")
    python_calls = deploy.calls("venv-python")
    assert any("engine_pin.py install" in c for c in python_calls)
    assert any("-m compileall -q" in c for c in python_calls)
    order = [
        c.split()[0]
        for c in deploy.lines()
        if c.startswith(("venv-pip", "venv-python"))
    ]
    assert order.index("venv-pip") < order.index("venv-python")


def test_it_does_not_start_the_service_and_says_why_and_what_comes_next(
    deploy: DeployWorld,
) -> None:
    run = deploy.install()

    assert run.code == 0
    assert "systemctl start sew-run" not in "\n".join(deploy.lines())
    assert "is enabled but NOT started" in run.out
    assert "exit 5" in run.out
    for step in (
        "sudo sew-key add",
        "alerting_discord_webhook",
        "alerting_deadman_ping_url",
        "bots.account_loss_cap",
        "preflight --venue futures_testnet",
        "RECOVERING",
        "M bot resume",
    ):
        assert step in run.out, step


def test_start_starts_it_and_the_app_is_proven_to_run_as_the_service_account(
    deploy: DeployWorld,
) -> None:
    run = deploy.install("--start")

    assert run.code == 0, run.err + run.out
    assert "systemctl start sew-run" in deploy.lines()
    assert "sew-run was started (--start)" in run.out
    assert "sudo-as sew" in deploy.lines()
    assert any(c.endswith("main.py status") for c in deploy.calls("venv-python"))


@pytest.mark.parametrize("code", [0, 10, 11])
def test_an_app_that_answers_status_with_0_10_or_11_is_a_working_install(
    deploy: DeployWorld, code: int
) -> None:
    deploy.set_state("status_exit", str(code))

    assert deploy.install().code == 0


def test_an_app_that_does_not_start_fails_the_install_with_exit_1(
    deploy: DeployWorld,
) -> None:
    deploy.set_state("status_exit", "1")

    run = deploy.install()

    assert run.code == 1
    assert "the app does not start as sew" in run.err


def test_a_second_run_changes_nothing_and_touches_no_secret(
    deploy: DeployWorld,
) -> None:
    deploy.install()
    secrets = deploy.root / "etc" / "sew"
    (secrets / "sew.env").write_text(
        "BINANCE_SPOT_TESTNET_API_KEY=KEEPME\n", encoding="utf-8"
    )
    key_file = secrets / "credentials" / "futures_mainnet_api_key"
    key_file.write_text("KEEPKEY", encoding="utf-8")
    key_file.chmod(0o600)
    config = deploy.checkout / "src" / "config" / "user_config.json"
    config.write_text('{"bots.account_loss_cap": "500 USDT"}\n', encoding="utf-8")
    deploy.log.write_text("", encoding="utf-8")
    before = deploy.snapshot()
    pinned = deploy.head()

    run = deploy.install()

    assert run.code == 0, run.err + run.out
    assert deploy.snapshot() == before
    assert (secrets / "sew.env").read_text(encoding="utf-8").endswith("KEEPME\n")
    assert key_file.read_text(encoding="utf-8") == "KEEPKEY"
    assert (
        config.read_text(encoding="utf-8") == '{"bots.account_loss_cap": "500 USDT"}\n'
    )
    assert deploy.head() == pinned
    assert deploy.calls("useradd") == []
    assert deploy.calls("apt-get") == []


def test_a_loosely_moded_credentials_directory_is_tightened_not_recreated(
    deploy: DeployWorld,
) -> None:
    deploy.install()
    directory = deploy.root / "etc" / "sew" / "credentials"
    (directory / "spot_mainnet_api_key").write_text("K", encoding="utf-8")
    directory.chmod(0o750)

    assert deploy.install().code == 0

    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert (directory / "spot_mainnet_api_key").read_text(encoding="utf-8") == "K"


def test_a_hand_pasted_sew_backup_is_kept_aside_and_replaced_by_the_link(
    deploy: DeployWorld,
) -> None:
    deploy.sbin.mkdir(parents=True)
    old = deploy.sbin / "sew-backup"
    old.write_text("#!/bin/sh\necho the heredoc version\n", encoding="utf-8")

    run = deploy.install()

    assert run.code == 0, run.err
    assert (deploy.sbin / "sew-backup").is_symlink()
    [kept] = [
        p for p in deploy.sbin.iterdir() if p.name.startswith("sew-backup.before-")
    ]
    assert "heredoc version" in kept.read_text(encoding="utf-8")


def test_dry_run_changes_nothing_and_says_what_it_would_do(deploy: DeployWorld) -> None:
    before = deploy.snapshot()

    run = deploy.install("--dry-run")

    assert run.code == 0, run.err + run.out
    assert deploy.snapshot() == before
    assert "would:" in run.out
    assert "Dry run: nothing was changed." in run.out
    for mutation in ("useradd", "apt-get", "venv-pip"):
        assert deploy.calls(mutation) == [], mutation
    assert not (deploy.root / "opt").exists()


def test_dry_run_on_an_installed_host_changes_nothing(deploy: DeployWorld) -> None:
    deploy.installed()
    (deploy.unit_dir / "sew-run.service").write_text("old\n", encoding="utf-8")
    before = deploy.snapshot()

    run = deploy.install("--dry-run")

    assert run.code == 0, run.err + run.out
    assert deploy.snapshot() == before
    assert "would: install" in run.out


def test_a_running_host_keeps_its_code_and_refuses_a_ref(deploy: DeployWorld) -> None:
    deploy.installed()
    deploy.set_state("active")
    pinned = deploy.head()

    again = deploy.install()
    refused = deploy.install("--ref", "origin/master-warrior")

    assert again.code == 0, again.err + again.out
    assert "leaves its code alone" in again.out
    assert deploy.calls("venv-pip") == []
    assert refused.code == 2
    assert "sew-update" in refused.err
    assert deploy.head() == pinned


def test_a_drop_in_that_resets_the_credentials_line_is_refused(
    deploy: DeployWorld,
) -> None:
    drop_in = deploy.unit_dir / "sew-run.service.d"
    drop_in.mkdir()
    (drop_in / "reset.conf").write_text(
        "[Service]\nLoadCredential=\n", encoding="utf-8"
    )

    run = deploy.install()

    assert run.code == 2
    assert "LoadCredential=" in run.err
    assert "expected exactly: LoadCredential=sew:/etc/sew/credentials" in run.err


def test_the_comment_in_the_unit_that_names_loadcredential_is_not_a_second_line(
    deploy: DeployWorld,
) -> None:
    """The runbook's `grep LoadCredential` also prints the unit's comment; the check is anchored."""
    unit = (DEPLOY / "sew-run.service").read_text(encoding="utf-8")
    comments = [
        line
        for line in unit.splitlines()
        if "LoadCredential" in line and line.startswith("#")
    ]
    assert comments, "the unit's comment that names the word is what this test is about"

    assert deploy.install().code == 0


def test_a_ref_is_checked_out_on_a_fresh_install(deploy: DeployWorld) -> None:
    deploy.tag("v1")
    deploy.commit("later work", **{"src__marker.txt": "later\n"})

    run = deploy.install("--ref", "v1")

    assert run.code == 0, run.err + run.out
    assert not (deploy.checkout / "src" / "marker.txt").exists()


def test_a_release_without_the_install_files_is_refused_with_the_remedy(
    deploy: DeployWorld,
) -> None:
    deploy.drop_from_origin("deploy/linux/sew-update")

    run = deploy.install()

    assert run.code == 2
    assert "predates the install scripts" in run.err


def test_missing_python_venv_is_installed_from_apt_and_not_otherwise(
    deploy: DeployWorld,
) -> None:
    deploy.set_state("no_venv_module")

    run = deploy.install()

    assert run.code == 0, run.err + run.out
    installs = [c for c in deploy.calls("apt-get") if "install" in c]
    assert len(installs) == 1
    assert installs[0].endswith("python3.12-venv")
    assert "git" not in installs[0]


def test_it_runs_from_inside_the_checkout_it_installs(deploy: DeployWorld) -> None:
    """The owner cloned straight into /opt/sew: no second clone, the checkout stays as it is."""
    deploy.checkout.parent.mkdir(parents=True)
    subprocess.run(
        [require_tool("git"), "clone", "-q", str(deploy.origin), str(deploy.checkout)],
        check=True,
    )
    pinned = deploy.head()

    run = deploy.install()

    assert run.code == 0, run.err + run.out
    assert "the checkout exists" in run.out
    assert deploy.head() == pinned


def test_a_directory_that_is_not_a_checkout_is_not_overwritten(
    deploy: DeployWorld,
) -> None:
    deploy.checkout.mkdir(parents=True)
    (deploy.checkout / "mine.txt").write_text("mine", encoding="utf-8")

    run = deploy.install()

    assert run.code == 2
    assert "is not a git checkout" in run.err
    assert (deploy.checkout / "mine.txt").read_text(encoding="utf-8") == "mine"


def test_no_key_value_can_reach_an_argument_because_no_script_reads_one() -> None:
    for name in ("sew-install", "sew-update", "sew-lib.sh"):
        text = (DEPLOY / name).read_text(encoding="utf-8")
        assert "read -s" not in text, name
        assert "API_SECRET" not in text, name


def test_a_host_restarting_after_a_crash_counts_as_running(deploy: DeployWorld) -> None:
    deploy.installed()
    deploy.set_state("activating")

    run = deploy.install()

    assert run.code == 0, run.err + run.out
    assert "leaves its code alone" in run.out
    assert deploy.calls("venv-pip") == []
