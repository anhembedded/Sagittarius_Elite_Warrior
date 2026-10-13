"""`EPIC-038H` - the NSSM install script cannot drift from the code it supervises."""

from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path

from Sagittarius_Elite_Warrior.scripts.render_service_files import (
    NSSM_FILE,
    render_nssm_script,
    supervisor_stop_wait_seconds,
)
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.modules.operations.application.run_host_parts import (
    LEAVE_PUBLISH_SECONDS,
    STOP_GRACE_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.operations.cli.run_options import (
    DEFAULT_STOP_TIMEOUT_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.secret_store_order import (
    SECRET_FILES_DIRECTORY_ENV,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.exit_code_table import (
    non_restarting_codes,
)
from Sagittarius_Elite_Warrior.tests.unit.scripts.service_files_world import (
    FORBIDDEN_IN_A_SERVICE,
    one,
    require_tool,
    service,
)


def test_the_nssm_script_is_what_the_generator_renders() -> None:
    assert NSSM_FILE.read_text(encoding="utf-8") == render_nssm_script()


def test_the_wrapper_stop_wait_exceeds_the_hosts_drain() -> None:
    text = NSSM_FILE.read_text(encoding="utf-8")
    [wait_ms] = re.findall(r"^Set-Nssm AppStopMethodConsole (\d+)$", text, re.MULTILINE)
    host_worst_case_ms = (
        DEFAULT_STOP_TIMEOUT_SECONDS + STOP_GRACE_SECONDS + LEAVE_PUBLISH_SECONDS
    ) * 1000

    assert int(wait_ms) > host_worst_case_ms
    assert (
        int(wait_ms)
        == supervisor_stop_wait_seconds(DEFAULT_STOP_TIMEOUT_SECONDS) * 1000
    )
    assert int(wait_ms) > 1500, "NSSM's default console wait"


def test_the_wrapper_stops_restarting_on_exactly_the_codes_the_unit_does() -> None:
    text = NSSM_FILE.read_text(encoding="utf-8")
    exits = {
        int(code)
        for code in re.findall(r"^Set-Nssm AppExit (\d+) Exit$", text, re.MULTILINE)
    }

    # Exit 0 ends the service too: NSSM restarts on every status it is not told about, while
    # the unit's Restart=on-failure does not restart a clean exit.
    assert exits == {int(ExitCode.SUCCESS), *non_restarting_codes()}
    assert 0 in exits
    assert "Set-Nssm AppExit Default Restart" in text
    unit_codes = {int(c) for c in one(service(), "RestartPreventExitStatus").split()}
    assert exits - {0} == unit_codes


def test_the_wrapper_sets_no_log_file_and_rotates_what_it_captures() -> None:
    text = NSSM_FILE.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        for forbidden in FORBIDDEN_IN_A_SERVICE:
            assert forbidden not in line, line
    assert "Set-Nssm AppRotateFiles 1" in text
    assert "Set-Nssm AppRotateOnline 1" in text
    assert re.search(r"^Set-Nssm AppRotateBytes \d+$", text, re.MULTILINE)
    assert "SEW_DATA_ROOT=" in text


def test_the_wrapper_is_valid_powershell() -> None:
    result = subprocess.run(
        [
            require_tool("pwsh"),
            "-NoProfile",
            "-Command",
            (
                "$e = $null; $t = $null; "
                "[void][System.Management.Automation.Language.Parser]::ParseFile("
                f"'{NSSM_FILE}', [ref]$t, [ref]$e); "
                "$e | ForEach-Object { $_.Message }; exit $e.Count"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _fake_tool(path: Path, log: Path, status_exit: str = "0") -> None:
    path.write_text(
        "#!/bin/sh\n"
        f'echo "$(basename "$0") $*" >> "{log}"\n'
        f'if [ "$1" = "status" ]; then exit {status_exit}; fi\n'
        "exit 0\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_the_wrapper_issues_the_settings_the_runbook_names_and_a_second_run_installs_nothing(
    tmp_path: Path,
) -> None:
    """Run the real script against a stand-in for `nssm` and `icacls` that records its calls."""
    log = tmp_path / "calls.log"
    nssm = tmp_path / "nssm"
    _fake_tool(nssm, log, status_exit="3")
    _fake_tool(tmp_path / "icacls", log)
    arguments = [
        require_tool("pwsh"),
        "-NoProfile",
        "-File",
        str(NSSM_FILE),
        "-Nssm",
        str(nssm),
        "-Python",
        "/sew/venv/python",
        "-Checkout",
        str(tmp_path / "Sagittarius_Elite_Warrior"),
        "-DataRoot",
        str(tmp_path / "data"),
        "-SecretFilesDir",
        str(tmp_path / "secrets"),
    ]
    environment = {**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}"}

    first = subprocess.run(
        arguments,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env=environment,
    )
    calls = log.read_text(encoding="utf-8").splitlines()

    assert first.returncode == 0, first.stdout + first.stderr
    assert any(call.startswith("nssm install sew-run") for call in calls)
    assert "nssm set sew-run AppStopMethodConsole 62000" in calls
    for code in (0, *non_restarting_codes()):
        assert f"nssm set sew-run AppExit {code} Exit" in calls
    assert "nssm set sew-run AppExit Default Restart" in calls
    parameters = next(
        c for c in calls if c.startswith("nssm set sew-run AppParameters")
    )
    assert 'main.py" run --stop-timeout 25' in parameters
    assert not any(word in parameters for word in FORBIDDEN_IN_A_SERVICE)
    environment_call = next(c for c in calls if " AppEnvironmentExtra " in c)
    assert f"SEW_DATA_ROOT={tmp_path / 'data'}" in environment_call
    assert f"{SECRET_FILES_DIRECTORY_ENV}={tmp_path / 'secrets'}" in environment_call

    log.unlink()
    _fake_tool(nssm, log, status_exit="0")
    second = subprocess.run(
        arguments,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env=environment,
    )
    again = log.read_text(encoding="utf-8").splitlines()

    assert second.returncode == 0, second.stdout + second.stderr
    assert not any(call.startswith("nssm install") for call in again)
    assert [c for c in again if c.startswith("nssm set")] == [
        c for c in calls if c.startswith("nssm set")
    ]
