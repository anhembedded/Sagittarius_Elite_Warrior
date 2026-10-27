"""`BOT-176` - `PlanFileWriter`: one writer for `bot export` and the desktop, never over an existing file."""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.bots.adapters.plan_file import (
    PlanFileWriter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.plan_file import (
    PlanFileRefused,
    PlanFileWritten,
)


def test_a_new_path_is_written(tmp_path: Path) -> None:
    target = tmp_path / "plan.json"

    result = PlanFileWriter().write_new(target, '{"bots": []}\n')

    assert result == PlanFileWritten(target)
    assert target.read_text(encoding="utf-8") == '{"bots": []}\n'


def test_an_existing_file_is_refused_and_untouched(tmp_path: Path) -> None:
    target = tmp_path / "plan.json"
    target.write_text("keep me", encoding="utf-8")

    result = PlanFileWriter().write_new(target, "new")

    assert result == PlanFileRefused(target, "exists")
    assert target.read_text(encoding="utf-8") == "keep me"


def test_an_os_error_comes_back_as_a_value_with_its_reason(tmp_path: Path) -> None:
    target = tmp_path / "no_such_folder" / "plan.json"

    result = PlanFileWriter().write_new(target, "x")

    assert isinstance(result, PlanFileRefused)
    assert result.reason == "os_error" and result.detail
    assert not target.parent.exists()
