"""`bot apply` and `bot export` (`EPIC-038I`): the verbs over the plan code, through the real report printer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_plan_verbs import (
    ApplyBotPlanVerb,
    ExportBotPlanVerb,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    AppliedBot,
    AppliedPlan,
    DesiredState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.shell.report_printer import ReportPrinter
from Sagittarius_Elite_Warrior.src.support.cli_host.report_formats import ReportFormats
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.helpers import seed
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.plan.plan_world import (
    CommandWorld,
    MemoryAppliedPlanStore,
    save_bot,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.cli.verb_world import verb_world

_PRINTER = ReportPrinter(ReportFormats.default())
_SECRET = "SECRET-SENTINEL-6d2f81c4-never-print-me"  # noqa: S105 - a fake, planted to prove it is never printed
_APPLY_KEYS = {"dry_run", "has_changes", "changes", "summary", "notes", "all_applied"}
_CHANGE_KEYS = {
    "action", "name", "venue", "bot_id", "state", "desired_state", "detail", "done",
}  # fmt: skip


def _plan_file(tmp_path: Path, *bots: dict[str, object], **top: object) -> Path:
    path = tmp_path / "plan.json"
    path.write_text(
        json.dumps({"schema": "sew.bot-plan/1", "bots": list(bots), **top}),
        encoding="utf-8",
    )
    return path


def _bot(name: str = "BTC grid", **overrides: object) -> dict[str, object]:
    return {
        "name": name,
        "kind": "grid",
        "venue": "spot_testnet",
        "symbol": "BTCUSDT",
        "params": {"lower": "60000", "upper": "70000"},
        "desired_state": "running",
        **overrides,
    }


def _apply_args(path: Path, **values: object) -> argparse.Namespace:
    return argparse.Namespace(
        **{
            "plan": str(path),
            "dry_run": False,
            "prune": False,
            "json": True,
            "format": None,
            **values,
        }
    )


def _document(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    return json.loads(capsys.readouterr().out)


def test_a_dry_run_prints_the_diff_and_changes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    world, store = CommandWorld(), MemoryAppliedPlanStore()
    path = _plan_file(tmp_path, _bot())

    outcome = ApplyBotPlanVerb().run(
        _apply_args(path, dry_run=True), verb_world(world, _PRINTER, plans=store)
    )

    document = _document(capsys)
    assert outcome is None
    assert document["schema"] == "sew.bot-apply/1"
    data = document["data"]
    assert set(data) == _APPLY_KEYS
    assert data["dry_run"] is True and data["has_changes"] is True
    (change,) = data["changes"]
    assert set(change) == _CHANGE_KEYS
    assert (change["action"], change["name"], change["done"]) == (
        "create",
        "BTC grid",
        False,
    )
    assert world.commands() == [] and store.writes == 0
    assert world.store.load_all().bots == ()


def test_apply_creates_the_bot_then_a_second_apply_says_no_changes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    world, store = CommandWorld(), MemoryAppliedPlanStore()
    path = _plan_file(tmp_path, _bot())
    verb_world_ = verb_world(world, _PRINTER, plans=store)

    first = ApplyBotPlanVerb().run(_apply_args(path), verb_world_)
    first_document = _document(capsys)
    second = ApplyBotPlanVerb().run(_apply_args(path), verb_world_)
    second_document = _document(capsys)

    assert first is None and second is None
    assert first_document["data"]["summary"]["create"] == 1
    assert first_document["data"]["changes"][0]["done"] is True
    (only_bot,) = world.store.load_all().bots
    created = only_bot.bot.bot_id.value
    assert first_document["data"]["changes"][0]["bot_id"] == created, (
        "a script learns the id of the bot that was created"
    )
    assert second_document["data"]["has_changes"] is False
    assert len(world.store.load_all().bots) == 1


def test_the_text_report_of_a_second_apply_says_no_changes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    world, store = CommandWorld(), MemoryAppliedPlanStore()
    path = _plan_file(tmp_path, _bot())
    plain = verb_world(world, _PRINTER, plans=store)
    ApplyBotPlanVerb().run(_apply_args(path, json=False), plain)
    capsys.readouterr()

    ApplyBotPlanVerb().run(_apply_args(path, json=False), plain)

    assert "No changes" in capsys.readouterr().out


def test_a_blocked_entry_exits_two_names_stop_first_and_still_applies_the_rest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    world, store = CommandWorld(), MemoryAppliedPlanStore()
    seed(world.store, "aaaaaa", BotLifecycleState.RUNNING, {"lower": "1", "upper": "2"})
    path = _plan_file(tmp_path, _bot("grid one"), _bot("fresh"))

    outcome = ApplyBotPlanVerb().run(
        _apply_args(path), verb_world(world, _PRINTER, plans=store)
    )

    document = _document(capsys)
    assert outcome is not None and outcome.code is ExitCode.USAGE
    assert "stop" in outcome.message.lower()
    by_name = {c["name"]: c for c in document["data"]["changes"]}
    assert (
        by_name["grid one"]["action"] == "blocked"
        and by_name["grid one"]["done"] is False
    )
    assert by_name["fresh"]["done"] is True


def test_a_dry_run_with_a_blocked_entry_also_exits_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    world = CommandWorld()
    seed(world.store, "aaaaaa", BotLifecycleState.RUNNING, {"lower": "1", "upper": "2"})
    path = _plan_file(tmp_path, _bot("grid one"))

    outcome = ApplyBotPlanVerb().run(
        _apply_args(path, dry_run=True), verb_world(world, _PRINTER)
    )

    assert outcome is not None and outcome.code is ExitCode.USAGE


def test_a_second_copy_exits_three_on_apply_and_changes_nothing(
    tmp_path: Path,
) -> None:
    world, store = CommandWorld(), MemoryAppliedPlanStore()
    path = _plan_file(tmp_path, _bot())
    reader = InstanceAccess.declined("Another copy holds the data root.")

    outcome = ApplyBotPlanVerb().run(
        _apply_args(path), verb_world(world, _PRINTER, plans=store, instance=reader)
    )

    assert outcome is not None and outcome.code is ExitCode.LOCK_HELD
    assert world.commands() == [] and store.writes == 0


def test_a_dry_run_works_on_a_read_only_copy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _plan_file(tmp_path, _bot())
    reader = InstanceAccess.declined("Another copy holds the data root.")

    outcome = ApplyBotPlanVerb().run(
        _apply_args(path, dry_run=True),
        verb_world(CommandWorld(), _PRINTER, instance=reader),
    )

    assert outcome is None and _document(capsys)["data"]["has_changes"] is True


def test_a_plan_with_a_key_field_exits_two_and_repeats_no_secret(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _plan_file(tmp_path, _bot(api_key=_SECRET))
    world = CommandWorld()

    outcome = ApplyBotPlanVerb().run(_apply_args(path), verb_world(world, _PRINTER))

    captured = capsys.readouterr()
    assert outcome is not None and outcome.code is ExitCode.USAGE
    assert "bots[0]" in outcome.message and "unknown field" in outcome.message
    assert "api_key" not in outcome.message + captured.out + captured.err
    assert _SECRET not in outcome.message + captured.out + captured.err
    assert world.commands() == []


def test_a_missing_plan_file_exits_two(tmp_path: Path) -> None:
    outcome = ApplyBotPlanVerb().run(
        _apply_args(tmp_path / "nope.json"), verb_world(CommandWorld(), _PRINTER)
    )

    assert outcome is not None and outcome.code is ExitCode.USAGE
    assert "nope.json" in outcome.message


def test_prune_deletes_only_a_bot_at_rest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    world = CommandWorld()
    seed(world.store, "aaaaaa", BotLifecycleState.STOPPED)
    seed(world.store, "bbbbbb", BotLifecycleState.RUNNING)
    path = _plan_file(tmp_path)

    outcome = ApplyBotPlanVerb().run(
        _apply_args(path, prune=True), verb_world(world, _PRINTER)
    )

    assert outcome is not None and outcome.code is ExitCode.USAGE, "bbbbbb needs a stop"
    remaining = {s.bot.bot_id.value for s in world.store.load_all().bots}
    assert remaining == {"bbbbbb"}


def test_export_writes_a_plan_that_a_dry_run_finds_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    world, store = CommandWorld(), MemoryAppliedPlanStore()
    save_bot(world.store, "aaaaaa", BotLifecycleState.RUNNING, "one", {"lower": "1"})
    save_bot(world.store, "bbbbbb", BotLifecycleState.STOPPED, "two", {"lower": "3"})
    out = tmp_path / "exported.json"
    plain = verb_world(world, _PRINTER, plans=store)

    exported = ExportBotPlanVerb().run(
        argparse.Namespace(
            all=True, bot_id=None, output=str(out), json=True, format=None
        ),
        plain,
    )
    capsys.readouterr()
    outcome = ApplyBotPlanVerb().run(_apply_args(out, dry_run=True, prune=True), plain)

    assert exported is None and outcome is None
    document = _document(capsys)
    assert document["data"]["has_changes"] is False, document["data"]["changes"]
    text = out.read_text(encoding="utf-8")
    assert json.loads(text)["schema"] == "sew.bot-plan/1"
    assert world.commands() == [] and store.writes == 0


def test_export_refuses_to_overwrite_a_file_and_an_unknown_id_and_no_choice(
    tmp_path: Path,
) -> None:
    world = CommandWorld()
    seed(world.store, "aaaaaa", BotLifecycleState.STOPPED)
    plain = verb_world(world, _PRINTER)
    existing = tmp_path / "plan.json"
    existing.write_text("keep me", encoding="utf-8")

    def export(**values: object) -> object:
        return ExportBotPlanVerb().run(
            argparse.Namespace(
                **{
                    "all": False,
                    "bot_id": None,
                    "output": str(tmp_path / "new.json"),
                    "json": True,
                    "format": None,
                    **values,
                }
            ),
            plain,
        )

    overwrite = export(all=True, output=str(existing))
    unknown = export(bot_id="zzzzzz")
    neither = export()

    for outcome in (overwrite, unknown, neither):
        assert outcome is not None and outcome.code is ExitCode.USAGE
    assert existing.read_text(encoding="utf-8") == "keep me"
    assert not (tmp_path / "new.json").exists()


def test_the_desired_state_an_exported_bot_gets_follows_the_record(
    tmp_path: Path,
) -> None:
    world = CommandWorld()
    seed(world.store, "aaaaaa", BotLifecycleState.STOPPED)
    store = MemoryAppliedPlanStore(
        AppliedPlan(
            (AppliedBot("aaaaaa", "grid one", "spot_testnet", DesiredState.RUNNING),)
        )
    )
    out = tmp_path / "exported.json"

    ExportBotPlanVerb().run(
        argparse.Namespace(
            all=True, bot_id=None, output=str(out), json=True, format=None
        ),
        verb_world(world, _PRINTER, plans=store),
    )

    (bot,) = json.loads(out.read_text(encoding="utf-8"))["bots"]
    assert bot["desired_state"] == "running"


def test_a_dry_run_carries_the_same_notes_as_a_real_apply(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unreadable bot file and an unreadable record change what the diff can see; the
    operator must be told in a dry run exactly as in the apply that follows it."""

    def notes(*, dry_run: bool) -> list[str]:
        world, store = CommandWorld(), MemoryAppliedPlanStore()
        world.store.refuse_file(BotId("dddddd"), "not valid JSON")
        store.unreadable = True
        ApplyBotPlanVerb().run(
            _apply_args(_plan_file(tmp_path, _bot()), dry_run=dry_run),
            verb_world(world, _PRINTER, plans=store),
        )
        return _document(capsys)["data"]["notes"]  # type: ignore[no-any-return, index]

    dry, real = notes(dry_run=True), notes(dry_run=False)

    assert dry == real
    assert any("bot file" in n and "dddddd" in n for n in dry), dry
    assert any("record" in n and "applied plan" in n for n in dry), dry


def test_the_text_report_of_a_dry_run_prints_the_notes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    world = CommandWorld()
    world.store.refuse_file(BotId("dddddd"), "not valid JSON")

    ApplyBotPlanVerb().run(
        _apply_args(_plan_file(tmp_path, _bot()), dry_run=True, json=False),
        verb_world(world, _PRINTER),
    )

    assert "dddddd" in capsys.readouterr().out


def test_an_unknown_id_is_a_usage_error_that_never_reaches_the_export_query(
    tmp_path: Path,
) -> None:
    """The engine's dispatcher logs a raising handler at ERROR, so a mistyped id would add a
    stderr record `bot export` never had: the id is checked before the query is dispatched."""
    world = CommandWorld()
    seed(world.store, "aaaaaa", BotLifecycleState.STOPPED)
    plain = verb_world(world, _PRINTER)

    outcome = ExportBotPlanVerb().run(
        argparse.Namespace(
            all=False,
            bot_id="zzzzzz",
            output=str(tmp_path / "new.json"),
            json=True,
            format=None,
        ),
        plain,
    )

    assert outcome is not None and outcome.code is ExitCode.USAGE
    assert "zzzzzz" in outcome.message
    assert plain.dispatcher.exports == []  # type: ignore[attr-defined]
