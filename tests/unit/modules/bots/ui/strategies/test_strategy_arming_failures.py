"""`BOT-169` — arming and removing a strategy that did not happen is told as a
command failure (a message box): the refusal's authored sentence is the
headline, and a port's own text or an exception is only its detail."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import FailureKind
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.arm_strategy_result import (
    ArmStrategyBlockReason,
    ArmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.disarm_strategy_result import (
    DisarmStrategyBlockReason,
    DisarmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.testing import (
    FakeStrategyArming,
)

from .arming_coordinator_fakes import coordinator_for

_INTERVALS = ["1m", "5m", "1h"]


class _Raising(FakeStrategyArming):
    def arm(self, config):
        raise RuntimeError("session broke")

    def disarm(self):
        raise RuntimeError("session broke")


def test_a_refused_arm_the_user_pressed_is_a_command_failure_with_the_ports_text(
    view_model, catalog, arming
):
    """`BOT-169`: the refusal's authored sentence is the headline, the port's
    own `error_message` is only the detail."""
    arming.script_arm(
        ArmStrategyResult(
            armed=False,
            block_reason=ArmStrategyBlockReason.TRADING_IS_ENABLED,
            error_message="session said no",
        )
    )
    notifier = RecordingNotifier()
    coordinator = coordinator_for(view_model, catalog, arming, notifier=notifier)
    coordinator.restore_into_view_model(_INTERVALS)

    coordinator.on_arm_clicked()

    notice = notifier.last
    assert notice.kind is FailureKind.COMMAND
    assert "turn off trading" in notice.headline
    assert "session said no" not in notice.headline
    assert notice.detail == "session said no"


def test_an_arm_that_raised_is_a_command_failure_whose_headline_has_no_exception(
    view_model, catalog
):
    notifier = RecordingNotifier()
    coordinator = coordinator_for(view_model, catalog, _Raising(), notifier=notifier)
    coordinator.restore_into_view_model(_INTERVALS)

    coordinator.on_arm_clicked()

    notice = notifier.last
    assert (notice.kind, notice.cause) == (FailureKind.COMMAND, "bots.strategy.arm")
    assert "session broke" not in notice.headline
    assert notice.detail == "session broke"


def test_a_disarm_that_raised_or_was_blocked_is_a_command_failure(
    view_model, catalog, arming
):
    raised, blocked = RecordingNotifier(), RecordingNotifier()
    coordinator_for(
        view_model, catalog, _Raising(), notifier=raised
    ).on_disarm_clicked()
    arming.script_disarm(
        DisarmStrategyResult(
            disarmed=False, block_reason=DisarmStrategyBlockReason.TRADING_IS_ENABLED
        )
    )
    coordinator_for(view_model, catalog, arming, notifier=blocked).on_disarm_clicked()

    assert raised.last.kind is FailureKind.COMMAND
    assert raised.last.detail == "session broke"
    assert "session broke" not in raised.last.headline
    assert blocked.last.kind is FailureKind.COMMAND
    assert "turn off trading" in blocked.last.headline
    assert blocked.last.cause == "bots.strategy.disarm"
