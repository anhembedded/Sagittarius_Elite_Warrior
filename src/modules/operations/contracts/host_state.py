"""The states of the `run` host (`DESIGN_2026-10-09_headless_operation.md` §6).

Lives in `contracts/` because the health line, the snapshot file and `status`
all name a state and must agree on the spelling.
"""

from __future__ import annotations

from enum import StrEnum


class HostState(StrEnum):
    """`BOOTING → SERVING → DRAINING → STOPPED`, plus `FAILED` from any state."""

    BOOTING = "BOOTING"
    SERVING = "SERVING"
    DRAINING = "DRAINING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
