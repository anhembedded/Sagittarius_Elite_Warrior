"""`BOT-204` - the scripts' hygiene and what `deploy/linux/sew-install` refuses: see `deploy_world.py` for the setup.

Not provable here: a real systemd, a real `useradd` and `chown` to the `sew` account, a real
pip install and the exchange. The stand-ins record the order and the arguments instead.
"""

from __future__ import annotations

import os
import subprocess

import pytest
from Sagittarius_Elite_Warrior.tests.unit.scripts.deploy_world import (
    DEPLOY,
    DeployWorld,
)
from Sagittarius_Elite_Warrior.tests.unit.scripts.service_files_world import (
    require_tool,
)

SCRIPTS = ("sew-install", "sew-update", "sew-backup", "sew-key")


def test_every_script_parses_under_bash_and_is_clean_under_shellcheck() -> None:
    shellcheck = require_tool("shellcheck")
    for name in (*SCRIPTS, "sew-lib.sh"):
        subprocess.run([require_tool("bash"), "-n", str(DEPLOY / name)], check=True)
    done = subprocess.run(
        [
            shellcheck,
            "-x",
            "-P",
            "SCRIPTDIR",
            *(str(DEPLOY / n) for n in (*SCRIPTS, "sew-lib.sh")),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout
    profile = subprocess.run(
        [shellcheck, "-s", "sh", str(DEPLOY / "sew-profile.sh")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert profile.returncode == 0, profile.stdout


def test_the_scripts_are_executable_strict_and_never_eval() -> None:
    for name in SCRIPTS:
        path = DEPLOY / name
        assert os.access(path, os.X_OK), name
        text = path.read_text(encoding="utf-8")
        assert text.startswith("#!/usr/bin/env bash\n"), name
        assert "set -euo pipefail" in text, name
        assert "eval " not in text, name
    assert not os.access(DEPLOY / "sew-lib.sh", os.X_OK)


@pytest.mark.parametrize(
    ("what", "expected"),
    [
        ("os", "this is not Ubuntu"),
        ("systemd", "older than 251"),
        ("disk", "free where /opt/sew goes"),
        ("clock", "clock is not synchronised"),
    ],
)
def test_a_failed_host_check_refuses_with_exit_2_and_changes_nothing(
    deploy: DeployWorld, what: str, expected: str
) -> None:
    extra: dict[str, str] = {}
    if what == "os":
        (deploy.root / "etc" / "os-release").write_text("ID=debian\n", encoding="utf-8")
    elif what == "systemd":
        deploy.set_state("systemd_version", "249")
    elif what == "disk":
        extra["SEW_DEPLOY_MIN_FREE_MB"] = "999999999"
    else:
        deploy.set_state("ntp", "no")
    before = deploy.snapshot()

    run = deploy.install(extra_env=extra)

    assert run.code == 2, run.out + run.err
    assert expected in run.err
    assert deploy.snapshot() == before
    assert deploy.calls("useradd") == []


def test_every_failed_host_check_is_listed_before_it_refuses(
    deploy: DeployWorld,
) -> None:
    (deploy.root / "etc" / "os-release").write_text("ID=debian\n", encoding="utf-8")
    deploy.set_state("systemd_version", "249")
    deploy.set_state("ntp", "no")

    run = deploy.install()

    assert run.code == 2
    assert run.err.count("FAIL ") == 3
    assert "3 host check(s) failed" in run.err


def test_skip_preflight_skips_only_the_host_checks(deploy: DeployWorld) -> None:
    (deploy.root / "etc" / "os-release").write_text("ID=debian\n", encoding="utf-8")

    run = deploy.install("--skip-preflight")

    assert run.code == 0, run.err
    assert "--skip-preflight" in run.err
    assert deploy.calls("useradd")


def test_it_refuses_unless_root_and_changes_nothing(deploy: DeployWorld) -> None:
    before = deploy.snapshot()

    run = deploy.install(euid="1000")

    assert run.code == 2
    assert "run this as root" in run.err
    assert deploy.snapshot() == before


def test_it_refuses_its_test_overrides_when_really_root(deploy: DeployWorld) -> None:
    run = deploy.install(uid="0")

    assert run.code == 2
    assert "SEW_DEPLOY_" in run.err


def test_a_bad_option_is_a_usage_refusal(deploy: DeployWorld) -> None:
    assert deploy.install("--no-such-flag").code == 2
    assert deploy.install("--ref").code == 2
