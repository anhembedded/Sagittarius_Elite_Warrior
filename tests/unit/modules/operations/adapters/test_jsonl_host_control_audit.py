"""`EPIC-038J` - the audit is a file: remembered by a second reader and by a restart, private, tolerant of a bad line."""

from __future__ import annotations

import stat
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.operations.adapters.jsonl_host_control_audit import (
    JsonlHostControlAudit,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_command import (
    ControlAuditEntry,
    ControlVerdict,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.adapters.host_control_files_world import (
    posix_only,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.control_world import (
    BOT,
    ID_A,
    ID_B,
    NOW,
)

# --- the audit --------------------------------------------------------------


def test_the_audit_is_remembered_by_a_second_reader_and_by_a_restart(
    tmp_path: Path,
) -> None:
    path = tmp_path / "audit.jsonl"
    JsonlHostControlAudit(path).record(
        ControlAuditEntry(ID_A, NOW, ControlVerdict.RECEIVED, "stop", BOT)
    )
    writer = JsonlHostControlAudit(path)
    writer.record(
        ControlAuditEntry(ID_A, NOW, ControlVerdict.EXECUTED, "stop", BOT, "ok")
    )

    reader = JsonlHostControlAudit(path)

    assert reader.has_seen(ID_A) and not reader.has_seen(ID_B)
    settled = reader.final_entry_of(ID_A)
    assert settled is not None and (settled.verdict, settled.message) == (
        ControlVerdict.EXECUTED,
        "ok",
    )


def test_a_received_line_is_not_a_final_answer(tmp_path: Path) -> None:
    audit = JsonlHostControlAudit(tmp_path / "audit.jsonl")
    audit.record(ControlAuditEntry(ID_A, NOW, ControlVerdict.RECEIVED))

    assert audit.final_entry_of(ID_A) is None


@posix_only
def test_the_audit_file_is_private_and_an_unreadable_line_is_skipped(
    tmp_path: Path,
) -> None:
    path = tmp_path / "audit.jsonl"
    audit = JsonlHostControlAudit(path)
    audit.record(ControlAuditEntry(ID_A, NOW, ControlVerdict.EXECUTED))
    with path.open("a", encoding="utf-8") as appended:
        appended.write("not json\n")

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert JsonlHostControlAudit(path).has_seen(ID_A)
