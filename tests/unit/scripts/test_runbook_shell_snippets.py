"""`EPIC-038H` - the shell the runbook tells an operator to type has to work in their shell.

Review of PR #478 found a step that did `sudo sh -c 'read -rs ...'`: on Debian and Ubuntu
`sh` is dash, which has no `read -s`, so the step would have written an empty credential
file and the service would have exited 5. These tests run the provisioning snippet for real
(with a stand-in `sudo` and the credentials directory moved into `tmp_path`, and a
placeholder value that is not a key) and keep the whole class of bug out: every bash block
parses, and no step hands bash-only code to a bare `sh`.
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.scripts.render_service_files import (
    mainnet_credential_names,
)
from Sagittarius_Elite_Warrior.tests.unit.scripts.service_files_world import (
    require_tool,
)

_RUNBOOK = (
    Path(__file__).resolve().parents[3] / "Docs" / "OPERATIONS" / "headless_runbook.md"
)
_BLOCK = re.compile(r"^```bash\n(.*?)^```$", re.MULTILINE | re.DOTALL)
_PLACEHOLDER = "placeholder-not-a-secret"
_CREDENTIALS_DIRECTORY = "/etc/sew/credentials"


def _bash_blocks() -> list[str]:
    return _BLOCK.findall(_RUNBOOK.read_text(encoding="utf-8"))


def _provisioning_block() -> str:
    [block] = [b for b in _bash_blocks() if "read -rsp" in b]
    return block


@pytest.mark.parametrize("block", _bash_blocks(), ids=lambda b: b.splitlines()[0][:40])
def test_every_bash_block_in_the_runbook_parses(block: str) -> None:
    result = subprocess.run(
        [require_tool("bash"), "-n"],
        input=block,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_no_step_hands_code_to_a_bare_sh() -> None:
    """`sh` is dash on Debian and Ubuntu: a `sh -c` step must not be written in bash."""
    text = _RUNBOOK.read_text(encoding="utf-8")
    assert re.findall(r"\b(?:sh|dash) -c\b", text) == []
    assert "read -rs" not in "\n".join(
        line for line in text.splitlines() if "sh -c" in line
    )


def _stand_ins(directory: Path, log: Path) -> None:
    sudo = directory / "sudo"
    sudo.write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{log}"\nexec "$@"\n', encoding="utf-8"
    )
    # `install -o root -g root` needs root; the snippet's mode is what is under test.
    install = directory / "install"
    install.write_text(
        "#!/bin/sh\n"
        'args=""\n'
        'while [ "$#" -gt 0 ]; do\n'
        '  case "$1" in -o|-g) shift 2 ;; *) args="$args $1"; shift ;; esac\n'
        "done\n"
        "exec /usr/bin/install $args\n",
        encoding="utf-8",
    )
    for tool in (sudo, install):
        tool.chmod(tool.stat().st_mode | stat.S_IXUSR)


def test_the_provisioning_snippet_writes_the_typed_value_to_a_mode_600_file(
    tmp_path: Path,
) -> None:
    bash = require_tool("bash")
    credentials = tmp_path / "credentials"
    credentials.mkdir()
    calls = tmp_path / "sudo-calls.log"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _stand_ins(bin_dir, calls)
    snippet = _provisioning_block().replace(_CREDENTIALS_DIRECTORY, str(credentials))
    environment = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}

    result = subprocess.run(
        [bash, "-c", snippet],
        input=f"{_PLACEHOLDER}\n",
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    written = credentials / "futures_mainnet_api_key"
    assert written.read_text(encoding="utf-8") == _PLACEHOLDER
    for name in mainnet_credential_names():
        assert stat.S_IMODE((credentials / name).stat().st_mode) == 0o600, name
    for unused in set(mainnet_credential_names()) - {"futures_mainnet_api_key"}:
        assert (credentials / unused).read_bytes() == b""
    # The value never reached an argument list: sudo only ever saw paths.
    assert _PLACEHOLDER not in calls.read_text(encoding="utf-8")
