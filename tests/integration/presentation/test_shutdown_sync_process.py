from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_PROCESS_EXIT_TIMEOUT_SECONDS = 15


def test_desktop_process_exits_when_closed_during_backtest_sync() -> None:
    workspace_root = Path(__file__).resolve().parents[4]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "Sagittarius_Elite_Warrior.scripts.shutdown_sync_probe",
        ],
        cwd=workspace_root,
        capture_output=True,
        text=True,
        timeout=_PROCESS_EXIT_TIMEOUT_SECONDS,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "SHUTDOWN_SYNC_PROBE_OK" in result.stdout
