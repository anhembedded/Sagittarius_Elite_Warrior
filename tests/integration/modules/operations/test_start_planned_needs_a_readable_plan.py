"""`run --start-planned` on the composed app: no plan, or one it cannot read, refuses the run (`EPIC-038I`).

The plan is `AppliedBotPlan` over the record `bot apply` wrote, bound by `create_app()`.
A host asked to start the planned bots that has no plan to read must not serve and say
"nothing to start": it exits `5` (decision D9: only the operator can fix it, a restart
cannot) before anything boots, and names `bot apply`.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    AppliedBot,
    AppliedPlan,
    DesiredState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_applied_plan_store import (
    IAppliedPlanStore,
)
from Sagittarius_Elite_Warrior.src.modules.operations.cli.run_command import (
    RunCommand,
)
from Sagittarius_Elite_Warrior.src.modules.operations.cli.run_options import (
    RunOptions,
)
from Sagittarius_Elite_Warrior.tests.integration.modules.operations.run_command_support import (
    Source,
    app_on,
    heard,
)

_SECRET = "SECRET-SENTINEL-6d2f81c4-never-print-me"  # noqa: S105 - a fake, planted to prove it is never printed


def _options() -> RunOptions:
    return RunOptions(start_planned=True, skip_preflight=True)


def test_start_planned_with_no_applied_plan_is_refused_with_five_before_anything_boots(
    data_root: Path,
) -> None:
    source = Source()

    outcome = RunCommand(app_on(data_root), _options(), source).execute()

    assert outcome is not None and outcome.code is ExitCode.CONFIGURATION
    assert "bot apply" in outcome.message, "the refusal says what to do"
    assert source.installed is False, "no host was built, no signal was taken"
    assert not (data_root / "state" / "health.json").exists(), "nothing booted"


def test_start_planned_with_a_record_it_cannot_read_is_refused_and_does_not_echo_it(
    data_root: Path,
) -> None:
    app = app_on(data_root)
    record = app.container.resolve(IAppliedPlanStore)
    path = _record_path(data_root)
    path.write_text('{"schema": "x", "api_key": "' + _SECRET + '"', encoding="utf-8")
    source = Source()

    outcome = RunCommand(app, _options(), source).execute()

    assert record.__class__.__name__ == "FileAppliedPlanStore"
    assert outcome is not None and outcome.code is ExitCode.CONFIGURATION
    assert "record" in outcome.message and _SECRET not in outcome.message
    assert source.installed is False


def test_a_readable_plan_lets_the_host_boot_and_reach_the_step(data_root: Path) -> None:
    """With a record the refusal does not apply: the host builds, boots and stops. (The step
    itself is skipped here because the stop is heard before serving; the step's own lines are
    `test_host_steps.py`, and a real start is `test_run_process.py`.)"""
    app = app_on(data_root)
    app.container.resolve(IAppliedPlanStore).write(
        AppliedPlan(
            (AppliedBot("aaaaaa", "one", "spot_testnet", DesiredState.RUNNING),)
        )
    )
    source = Source()
    original_install = source.install

    def install_then_fire(on_signal):  # type: ignore[no-untyped-def]
        original_install(on_signal)
        source.fire()

    source.install = install_then_fire  # type: ignore[method-assign]

    with heard() as lines:
        outcome = RunCommand(app, _options(), source).execute()

    assert outcome is None
    assert source.installed
    assert "step start-planned skipped" in "\n".join(lines)


def _record_path(data_root: Path) -> Path:
    # `app_config` points the bots folder at `<data root>/bots`; the record sits beside it.
    return data_root / "bot_plan.json"
