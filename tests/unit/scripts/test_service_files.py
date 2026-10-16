"""`EPIC-038H` — the shipped service files cannot drift from the code they supervise.

`deploy/linux/sew-run.service` and `deploy/windows/nssm-install.ps1` are rendered by
`scripts/render_service_files.py` from the host's own constants. These tests pin the
files twice: against the render (so a hand edit or a changed constant fails until the files
are regenerated) and against the code independently of the render (so a wrong formula in
the renderer fails too).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.scripts.render_service_files import (
    NSSM_FILE,
    UNIT_FILE,
    UnitPaths,
    host_arguments,
    mainnet_credential_names,
    render_unit,
    supervisor_stop_wait_seconds,
)
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.host_signals import (
    NOTIFY_SOCKET_VARIABLE,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.run_host_parts import (
    LEAVE_PUBLISH_SECONDS,
    STOP_GRACE_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.operations.cli.run_options import (
    DEFAULT_STOP_TIMEOUT_SECONDS,
    RunOptions,
    run_options_of,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.cli_parser import build_parser
from Sagittarius_Elite_Warrior.src.support.cli_host.exit_code_table import (
    EXIT_CODE_TABLE,
    SupervisorAction,
    non_restarting_codes,
)
from Sagittarius_Elite_Warrior.src.support.secrets.adapters.systemd_credential_store import (
    CREDENTIALS_DIRECTORY_ENV,
    SystemdCredentialStore,
)
from Sagittarius_Elite_Warrior.tests.unit.scripts.service_files_world import (
    FORBIDDEN_IN_A_SERVICE,
    one,
    require_tool,
    sections,
    service,
)
from sagittarius_engine.interfaces.i_config import IConfig

_ROOT = Path(__file__).resolve().parents[3]
_PLACEHOLDER = "placeholder-not-a-secret"


def _environment() -> dict[str, str]:
    return dict(entry.split("=", 1) for entry in service()["Environment"])


def _flag(words: list[str], name: str) -> str:
    return words[words.index(name) + 1]


# --- the files are the render ------------------------------------------------


def test_the_unit_file_is_what_the_generator_renders() -> None:
    """Regenerate with `python3 scripts/render_service_files.py --write`."""
    assert UNIT_FILE.read_text(encoding="utf-8") == render_unit()


# --- the unit's restart policy ----------------------------------------------


def test_the_unit_restarts_on_failure_without_a_start_limit_and_never_on_a_configuration_exit() -> (
    None
):
    parsed = sections(UNIT_FILE.read_text(encoding="utf-8"))
    settings = parsed["Service"]

    assert one(settings, "Restart") == "on-failure"
    assert one(settings, "RestartSec") == "10"
    assert one(parsed["Unit"], "StartLimitIntervalSec") == "0"

    prevented = {
        int(code) for code in one(settings, "RestartPreventExitStatus").split()
    }
    assert prevented == set(non_restarting_codes())
    # The meaning, not only the numbers: every refusal and configuration code is in it,
    # and the two a restart can fix (an unexpected error, an exchange outage) are not.
    for code in (
        ExitCode.USAGE,
        ExitCode.LOCK_HELD,
        ExitCode.PREFLIGHT_FAILED,
        ExitCode.CONFIGURATION,
    ):
        assert int(code) in prevented, code.name
    for code in (ExitCode.SUCCESS, ExitCode.ERROR, ExitCode.EXCHANGE):
        assert int(code) not in prevented, code.name
    assert prevented == {
        int(code)
        for code, row in EXIT_CODE_TABLE.items()
        if row.supervisor is SupervisorAction.DO_NOT_RESTART
    }


def test_the_unit_stop_timeout_exceeds_the_hosts_drain() -> None:
    settings = service()
    words = one(settings, "ExecStart").split()
    stop_timeout = float(_flag(words, "--stop-timeout"))
    host_worst_case = stop_timeout + STOP_GRACE_SECONDS + LEAVE_PUBLISH_SECONDS

    timeout_stop = float(one(settings, "TimeoutStopSec"))

    assert timeout_stop > host_worst_case
    assert timeout_stop == supervisor_stop_wait_seconds(stop_timeout)
    assert stop_timeout == DEFAULT_STOP_TIMEOUT_SECONDS


def test_the_unit_states_its_stop_timeout_formula() -> None:
    text = UNIT_FILE.read_text(encoding="utf-8")
    assert "TimeoutStopSec = ceil(--stop-timeout + STOP_GRACE_SECONDS" in text
    assert str(int(one(service(), "TimeoutStopSec"))) in text


# --- the unit's arguments are the CLI's --------------------------------------


def _run_arguments(exec_start: str) -> list[str]:
    words = exec_start.split()
    return words[words.index("run") :]


def test_the_units_arguments_are_accepted_by_the_real_parser_and_mean_what_the_runbook_says() -> (
    None
):
    commands = json.loads(
        (_ROOT / "src" / "config" / "cli_commands.json").read_text(encoding="utf-8")
    )["CLI_COMMANDS"]
    config = Mock(spec=IConfig)
    config.get.return_value = commands
    parser = build_parser(config)

    args = parser.parse_args(_run_arguments(one(service(), "ExecStart")))
    options = run_options_of(args)

    assert isinstance(options, RunOptions)
    assert options.stop_timeout_s == DEFAULT_STOP_TIMEOUT_SECONDS
    assert options.on_stop.value == "leave-orders"
    assert options.host_signal.value == "sdnotify"
    # The unattended defaults a service must not weaken.
    assert not options.skip_preflight
    assert not options.resume_recovering
    assert not options.accept_silent_failures
    assert options.confirm_venue is None


def test_the_unit_and_the_wrapper_start_the_host_with_the_same_arguments() -> None:
    unit = one(service(), "ExecStart")
    script = NSSM_FILE.read_text(encoding="utf-8")
    assert host_arguments(DEFAULT_STOP_TIMEOUT_SECONDS) in unit
    assert host_arguments(DEFAULT_STOP_TIMEOUT_SECONDS) in script


def test_the_unit_sets_no_log_file() -> None:
    text = UNIT_FILE.read_text(encoding="utf-8")
    executable_lines = [
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    ]
    for forbidden in FORBIDDEN_IN_A_SERVICE:
        assert not any(forbidden in line for line in executable_lines), forbidden


# --- the unit's secrets and data root ----------------------------------------


def test_the_unit_loads_every_mainnet_credential_under_the_name_the_store_reads(
    tmp_path: Path,
) -> None:
    loaded = dict(value.split(":", 1) for value in service()["LoadCredential"])
    assert set(loaded) == set(mainnet_credential_names())
    for name, source in loaded.items():
        assert source.endswith(f"/credentials/{name}")
        (tmp_path / name).write_text(f"{_PLACEHOLDER}\n", encoding="utf-8")

    store = SystemdCredentialStore({CREDENTIALS_DIRECTORY_ENV: str(tmp_path)})

    for name in loaded:
        assert store.read(name) == _PLACEHOLDER


def test_a_credential_file_left_empty_for_an_unused_venue_reads_as_no_key(
    tmp_path: Path,
) -> None:
    """The runbook tells the operator to create an empty file for a venue they do not use."""
    for name in mainnet_credential_names():
        (tmp_path / name).write_bytes(b"")
    store = SystemdCredentialStore({CREDENTIALS_DIRECTORY_ENV: str(tmp_path)})

    assert [store.read(name) for name in mainnet_credential_names()] == [None] * 4


def test_the_unit_runs_as_a_dedicated_account_and_keeps_its_data_outside_the_checkout() -> (
    None
):
    settings = service()
    environment = _environment()
    checkout = UnitPaths().checkout
    data_root = environment["SEW_DATA_ROOT"]

    assert one(settings, "User") not in {"root", ""}
    assert one(settings, "Group") == one(settings, "User")
    assert one(settings, "WorkingDirectory") == data_root
    assert not data_root.startswith(checkout)
    assert not data_root.startswith(environment["PYTHONPATH"])
    assert one(settings, "MemoryMax")


def test_the_hardening_still_lets_the_host_write_its_data_root() -> None:
    """`ProtectSystem=strict` makes everything read-only except what is opened again.

    The host writes `$SEW_DATA_ROOT` (state/, logs/, the bots' files). The unit opens it
    with `StateDirectory=`, which also creates it owned by `User=`; a hardening line that
    closes it again, or a data root that `StateDirectory=` does not cover, fails here.
    """
    settings = service()
    data_root = _environment()["SEW_DATA_ROOT"]
    state_directories = [f"/var/lib/{name}" for name in settings["StateDirectory"]]

    assert one(settings, "ProtectSystem") == "strict"
    assert data_root in state_directories
    assert one(settings, "StateDirectoryMode") == "0700"
    for closing in ("InaccessiblePaths", "TemporaryFileSystem", "ReadOnlyPaths"):
        assert closing not in settings, f"{closing} could close the data root"
    # ProtectHome would hide a data root under /home; the checkout must not be there either.
    assert not data_root.startswith("/home")
    assert not UnitPaths().checkout.startswith("/home")


def test_the_hardening_leaves_the_notify_socket_and_the_exchange_reachable() -> None:
    settings = service()
    families = one(settings, "RestrictAddressFamilies").split()
    assert {"AF_UNIX", "AF_INET", "AF_INET6"} <= set(families)
    assert NOTIFY_SOCKET_VARIABLE == "NOTIFY_SOCKET"
    assert one(settings, "Type") == "notify"
    assert "--host-signal sdnotify" in one(settings, "ExecStart")


# --- systemd's own check -----------------------------------------------------


def test_systemd_accepts_the_unit(tmp_path: Path) -> None:
    """`systemd-analyze verify` on the unit, with the install paths bound to real files.

    The unit names `/opt/sew/...`, which only exists on a server; the render takes the paths
    as arguments so the same text can be checked against files that do exist here.
    """
    checkout = tmp_path / "Sagittarius_Elite_Warrior"
    (checkout / "src").mkdir(parents=True)
    (checkout / "src" / "main.py").write_text("", encoding="utf-8")
    unit = tmp_path / "sew-run.service"
    unit.write_text(
        render_unit(
            UnitPaths(
                checkout=str(checkout),
                python=sys.executable,
                import_root=str(tmp_path),
                config_dir=str(tmp_path),
            )
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [require_tool("systemd-analyze"), "verify", str(unit)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={**os.environ, "SYSTEMD_LOG_LEVEL": "info"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert not re.search(
        r"(?i)unknown (key|section)|invalid|ignoring", result.stderr
    ), result.stderr
