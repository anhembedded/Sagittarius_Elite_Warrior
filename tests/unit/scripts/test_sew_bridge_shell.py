"""`EPIC-047G` - `deploy/linux/sew-bridge-shell`, the sew account's login shell: it runs the bridge launcher and nothing else.

`sshd` calls a login shell as `<shell> -c "<forced command>"`, or with no argument for an interactive login. The program is the real file with its
launcher line pointing at a test launcher that records that it ran, with what environment, and what it read.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.tests.unit.scripts.service_files_world import (
    require_tool,
)
from Sagittarius_Elite_Warrior.tests.unit.scripts.sew_link_key_world import (
    GUARD_REAL,
    World,
)

STRAY_VARIABLE = "SENTINEL_NOT_FOR_THE_BRIDGE"


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(tmp_path)


def _launcher_that_records(world: World) -> Path:
    marker = world.root / "ran"
    world.launcher.write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$*" > "{marker}"\nenv | sort > "{marker}.env"\nprintf \'{{"type":"hello"}}\\n\'\n',
        encoding="utf-8",
    )
    world.launcher.chmod(0o755)
    return marker


def _guard(
    world: World, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [require_tool("sh"), str(world.guard_source), *args],
        capture_output=True,
        text=True,
        env={"PATH": os.environ["PATH"], **(env or {})},
        timeout=30,
        check=False,
        stdin=subprocess.DEVNULL,
    )


def test_the_exact_launcher_request_runs_the_launcher(world: World) -> None:
    marker = _launcher_that_records(world)

    done = _guard(world, "-c", str(world.launcher))

    assert done.returncode == 0
    assert done.stdout.strip() == '{"type":"hello"}'
    assert marker.exists()


def test_the_launcher_gets_a_clean_environment_and_no_argument(world: World) -> None:
    marker = _launcher_that_records(world)

    _guard(
        world,
        "-c",
        str(world.launcher),
        env={
            STRAY_VARIABLE: "x",
            "SSH_ORIGINAL_COMMAND": "whoami; cat /etc/passwd",
            "LD_PRELOAD": "/tmp/evil.so",
        },
    )

    seen = (world.root / "ran.env").read_text(encoding="utf-8")
    names = {line.split("=", 1)[0] for line in seen.splitlines()}
    assert {"PATH", "HOME", "USER", "LOGNAME"} <= names
    assert not names & {STRAY_VARIABLE, "SSH_ORIGINAL_COMMAND", "LD_PRELOAD"}
    assert marker.read_text(encoding="utf-8").strip() == ""


@pytest.mark.parametrize(
    "arguments",
    [
        (),
        ("-l",),
        ("-c", "whoami; cat /etc/passwd"),
        ("-c", "id"),
        ("-c", ""),
        ("-c", "{launcher} extra"),
        ("-c", "{launcher}; id"),
        ("-c", "{launcher}\nid"),
        ("-c", "/bin/sh"),
        ("-i",),
        ("-c", "{launcher}", "extra"),
        ("-x", "-c", "{launcher}"),
        ("--", "-c", "{launcher}"),
        ("-c{launcher}",),
        ("-x", "{launcher}"),
        ("{launcher}", "-c"),
    ],
    ids=str,
)
def test_anything_else_is_refused_and_the_launcher_does_not_run(
    world: World, arguments: tuple[str, ...]
) -> None:
    marker = _launcher_that_records(world)
    arguments = tuple(a.replace("{launcher}", str(world.launcher)) for a in arguments)

    done = _guard(world, *arguments)

    assert done.returncode == 1
    assert "only runs the VPS bridge" in done.stderr
    assert done.stdout == ""
    assert not marker.exists()


def test_the_refusal_prints_nothing_on_standard_output_which_is_the_bridges_protocol(
    world: World,
) -> None:
    done = _guard(world)

    assert done.stdout == ""


def test_a_launcher_path_that_differs_by_a_character_is_refused(world: World) -> None:
    marker = _launcher_that_records(world)

    done = _guard(world, "-c", f"{world.launcher}x")

    assert done.returncode == 1
    assert not marker.exists()


def test_the_real_file_names_the_installed_launcher_and_is_plain_posix_sh() -> None:

    text = GUARD_REAL.read_text(encoding="utf-8")
    assert text.startswith("#!/bin/sh\n")
    assert (
        "LAUNCHER=/opt/sew/Sagittarius_Elite_Warrior/deploy/linux/sew-bridge\n" in text
    )
    assert "bash" not in text.replace("sew-bridge-shell", "")
    assert os.access(GUARD_REAL, os.X_OK)
    assert (
        len([line for line in text.splitlines() if line and not line.startswith("#")])
        <= 8
    )
