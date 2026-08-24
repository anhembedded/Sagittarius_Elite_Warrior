from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_PROCESS_EXIT_TIMEOUT_SECONDS = 5
_SUCCESS_MARKER = "SHUTDOWN_DATABASE_SCAN_PROBE_OK"
_CANCELLATION_LOG = "Database scan observed cancellation and skipped queued pairs."


def test_process_exits_after_cancelling_inflight_database_scan() -> None:
    """BUG-041: CPython must not wait for every queued database scan pair."""
    workspace_root = Path(__file__).resolve().parents[4]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "Sagittarius_Elite_Warrior.scripts.shutdown_database_scan_probe",
        ],
        cwd=workspace_root,
        capture_output=True,
        text=True,
        timeout=_PROCESS_EXIT_TIMEOUT_SECONDS,
        check=False,
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert _SUCCESS_MARKER in result.stdout
    assert _CANCELLATION_LOG in output
