"""`EPIC-047C` - the forced command: one exec of the bridge, whatever the client asked for."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

LAUNCHER = Path(__file__).resolve().parents[3] / "deploy" / "linux" / "sew-bridge"

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="a POSIX shell script and its exec"
)


def _fake_python(home: Path) -> None:
    python = home / "venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text(
        "#!/bin/sh\n"
        'printf "%s\\n" "$@"\n'
        'printf "PYTHONPATH=%s\\nSEW_DATA_ROOT=%s\\n" "$PYTHONPATH" "$SEW_DATA_ROOT"\n',
        encoding="utf-8",
    )
    python.chmod(0o755)


def _run(home: Path, data: Path, original_command: str) -> list[str]:
    result = subprocess.run(
        ["/bin/sh", str(LAUNCHER)],
        env={
            "PATH": os.environ["PATH"],
            "SEW_HOME": str(home),
            "SEW_DATA": str(data),
            "SSH_ORIGINAL_COMMAND": original_command,
        },
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    return result.stdout.splitlines()


def test_the_launcher_runs_the_bridge_module_in_the_sew_environment(
    tmp_path: Path,
) -> None:
    _fake_python(tmp_path / "home")

    lines = _run(tmp_path / "home", tmp_path / "data", "")

    assert lines == [
        "-m",
        "Sagittarius_Elite_Warrior.src.shell.link_bridge_main",
        f"PYTHONPATH={tmp_path / 'home'}",
        f"SEW_DATA_ROOT={tmp_path / 'data'}",
    ]


@pytest.mark.parametrize(
    "asked",
    ["whoami; cat /etc/passwd", "bash -i", "scp -t /etc", "sftp"],
    ids=["two-commands", "shell", "scp", "sftp"],
)
def test_what_the_client_asked_for_never_reaches_the_command(
    tmp_path: Path, asked: str
) -> None:
    """R2: a request for `whoami; cat /etc/passwd` got the bridge's hello. The key's `command=` decides;
    the script ignores `SSH_ORIGINAL_COMMAND` too, so even a misconfigured key would run only this."""
    _fake_python(tmp_path / "home")

    lines = _run(tmp_path / "home", tmp_path / "data", asked)

    assert lines[:2] == ["-m", "Sagittarius_Elite_Warrior.src.shell.link_bridge_main"]
    assert all(asked not in line for line in lines)


def test_the_launcher_does_not_read_the_clients_request() -> None:
    assert "SSH_ORIGINAL_COMMAND" not in "\n".join(
        line
        for line in LAUNCHER.read_text(encoding="utf-8").splitlines()
        if not line.startswith("#")
    )
