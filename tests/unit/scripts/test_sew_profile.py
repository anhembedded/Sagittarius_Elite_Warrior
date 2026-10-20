"""`BOT-204` - `deploy/linux/sew-profile.sh`, the content of `/etc/profile.d/sew.sh`.

It is sourced by login shells, so these tests source it for real under bash and, where it is
installed, dash (`/bin/sh` on Ubuntu), with `sudo` and `id` stood in for and a stand-in for the
venv's python that writes down its argv and the environment it was given.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.tests.unit.scripts.deploy_world import DEPLOY
from Sagittarius_Elite_Warrior.tests.unit.scripts.service_files_world import (
    require_tool,
)

PROFILE = DEPLOY / "sew-profile.sh"

_PYTHON = """#!/bin/sh
{
  printf 'argv=%s\\n' "$*"
  for name in COLUMNS TERM NO_COLOR COLORTERM PYTHONPATH SEW_DATA_ROOT; do
    eval "value=\\${$name-<unset>}"
    printf '%s=%s\\n' "$name" "$value"
  done
  printf 'stdin=%s\\n' "$(cat)"
} > "$STUB_OUT"
"""


class Shell:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.home = tmp / "opt" / "sew"
        (self.home / "venv" / "bin").mkdir(parents=True)
        self.out = tmp / "python.out"
        self.sudo_log = tmp / "sudo.log"
        python = self.home / "venv" / "bin" / "python"
        python.write_text(_PYTHON, encoding="utf-8")
        python.chmod(0o755)
        self.bin = tmp / "bin"
        self.bin.mkdir()
        self._tool(
            "sudo",
            f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{self.sudo_log}"\n'
            'if [ "$1" = "-u" ]; then shift 2; fi\nexec "$@"\n',
        )
        self._tool("tput", "#!/bin/sh\necho 91\n")
        self._tool(
            "journalctl",
            "#!/bin/sh\necho '2026-10-20 - WARNING - [bot] halted'\necho 'a plain line'\n",
        )

    def _tool(self, name: str, text: str) -> None:
        path = self.bin / name
        path.write_text(text, encoding="utf-8")
        path.chmod(0o755)

    def user(self, name: str, uid: str) -> None:
        self._tool(
            "id", f'#!/bin/sh\ncase "$1" in -un) echo {name};; -u) echo {uid};; esac\n'
        )

    def run(
        self, shell: str, script: str, extra_env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        env = {
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "HOME": str(self.tmp),
            "SEW_HOME": str(self.home),
            "SEW_DATA": str(self.tmp / "var" / "lib" / "sew"),
            "STUB_OUT": str(self.out),
        }
        env.update(extra_env or {})
        return subprocess.run(
            [shell, "-c", f". {PROFILE}\n{script}"],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            check=False,
        )

    def seen(self) -> dict[str, str]:
        return dict(
            line.split("=", 1)
            for line in self.out.read_text(encoding="utf-8").splitlines()
            if "=" in line
        )


@pytest.fixture
def shell(tmp_path: Path) -> Shell:
    made = Shell(tmp_path)
    made.user("operator", "1000")
    return made


def _shells() -> list[str]:
    found = [require_tool("bash")]
    dash = shutil.which("dash")
    if dash:
        found.append(dash)
    return found


@pytest.mark.parametrize("interpreter", _shells(), ids=lambda path: Path(path).name)
def test_it_is_sourced_by_every_login_shell_without_output_or_a_global_pythonpath(
    shell: Shell, interpreter: str
) -> None:
    done = shell.run(
        interpreter, 'printf "%s|%s" "${PYTHONPATH-<unset>}" "${SEW_DATA_ROOT-<unset>}"'
    )

    assert done.returncode == 0, done.stderr
    assert done.stdout == "<unset>|<unset>"
    assert done.stderr == ""


def test_it_exports_the_commonly_used_paths_and_can_be_sourced_twice(
    shell: Shell,
) -> None:
    done = shell.run(
        require_tool("bash"),
        '. "$0"\nenv | grep "^SEW_" | sort',
        {},
    )

    assert done.returncode == 0, done.stderr
    assert f"SEW_CHECKOUT={shell.home}/Sagittarius_Elite_Warrior" in done.stdout
    assert f"SEW_HOME={shell.home}" in done.stdout
    assert "SEW_DATA=" in done.stdout
    assert "SEW_DATA_ROOT" not in done.stdout


@pytest.mark.parametrize("interpreter", _shells(), ids=lambda path: Path(path).name)
def test_m_runs_main_py_as_sew_with_the_services_environment_and_the_terminal(
    shell: Shell, interpreter: str
) -> None:
    done = shell.run(
        interpreter,
        "M bot list --json",
        {"COLUMNS": "137", "TERM": "xterm-256color", "COLORTERM": "truecolor"},
    )

    assert done.returncode == 0, done.stderr
    seen = shell.seen()
    assert (
        seen["argv"]
        == f"{shell.home}/Sagittarius_Elite_Warrior/src/main.py bot list --json"
    )
    assert seen["PYTHONPATH"] == str(shell.home)
    assert seen["SEW_DATA_ROOT"].endswith("var/lib/sew")
    assert seen["COLUMNS"] == "137"
    assert seen["TERM"] == "xterm-256color"
    assert seen["COLORTERM"] == "truecolor"
    assert seen["NO_COLOR"] == "<unset>"
    assert "-u sew env " in shell.sudo_log.read_text(encoding="utf-8")


def test_m_asks_the_terminal_for_its_width_when_the_shell_has_not_exported_it(
    shell: Shell,
) -> None:
    shell.run(require_tool("bash"), "M status")

    assert shell.seen()["COLUMNS"] == "91"


def test_m_passes_no_color_only_when_it_is_set(shell: Shell) -> None:
    shell.run(require_tool("bash"), "M status", {"NO_COLOR": "1"})
    assert shell.seen()["NO_COLOR"] == "1"
    shell.run(require_tool("bash"), "M status")
    assert shell.seen()["NO_COLOR"] == "<unset>"


def test_m_keeps_the_exit_status_of_the_app(shell: Shell) -> None:
    python = shell.home / "venv" / "bin" / "python"
    python.write_text("#!/bin/sh\nexit 10\n", encoding="utf-8")

    done = shell.run(require_tool("bash"), 'M status; echo "rc=$?"')

    assert done.stdout.strip().endswith("rc=10")


def test_m_does_not_leave_its_scratch_variable_in_the_shell(shell: Shell) -> None:
    done = shell.run(require_tool("bash"), 'M status; echo "[${_sew_cols-<unset>}]"')

    assert done.stdout.strip().endswith("[<unset>]")


def test_m_does_not_use_sudo_when_you_already_are_the_service_account(
    shell: Shell,
) -> None:
    shell.user("sew", "999")

    done = shell.run(require_tool("bash"), "M status", {"COLUMNS": "100"})

    assert done.returncode == 0, done.stderr
    assert not shell.sudo_log.exists()
    assert shell.seen()["PYTHONPATH"] == str(shell.home)


def test_the_helpers_are_the_commands_the_runbook_names(shell: Shell) -> None:
    shell.run(require_tool("bash"), "sewbots --json")
    assert shell.seen()["argv"].endswith("main.py bot list --json")
    shell.run(require_tool("bash"), "sewstatus")
    assert shell.seen()["argv"].endswith("main.py status")


def test_sewlog_pipes_the_journal_into_the_apps_log_viewer(shell: Shell) -> None:
    done = shell.run(require_tool("bash"), "sewlog --level warning")

    assert done.returncode == 0, done.stderr
    seen = shell.seen()
    assert seen["argv"].endswith("main.py logs --level warning")
    assert "[bot] halted" in seen["stdin"]


def test_sewproblems_keeps_only_warning_error_and_critical_records(
    shell: Shell,
) -> None:
    done = shell.run(require_tool("bash"), "sewproblems")

    assert done.stdout.strip() == "2026-10-20 - WARNING - [bot] halted"


def test_sewhelp_lists_every_helper(shell: Shell) -> None:
    done = shell.run(require_tool("bash"), "sewhelp")

    for word in (
        "M <args>",
        "sewlog",
        "sewstatus",
        "sewbots",
        "sewproblems",
        "sew-key",
        "sew-update",
    ):
        assert word in done.stdout, word


def test_sourcing_it_under_nounset_does_not_fail(shell: Shell) -> None:
    done = shell.run(require_tool("bash"), "set -u; M status; echo ok")

    assert done.returncode == 0, done.stderr
    assert done.stdout.strip().endswith("ok")
