from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_PROCESS_EXIT_TIMEOUT_SECONDS = 30


@pytest.mark.parametrize("mode", ["single_sync", "bulk_sync", "repair_gap"])
def test_desktop_process_exits_when_closed_during_data_management_sync(
    mode: str,
) -> None:
    workspace_root = Path(__file__).resolve().parents[4]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "Sagittarius_Elite_Warrior.scripts.shutdown_database_sync_probe",
            mode,
        ],
        cwd=workspace_root,
        capture_output=True,
        text=True,
        timeout=_PROCESS_EXIT_TIMEOUT_SECONDS,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"SHUTDOWN_DB_SYNC_PROBE_OK_{mode.upper()}" in result.stdout
