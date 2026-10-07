"""`BOT-169` — an indicator whose saved parameters are refused is built from its
defaults and the user is told through the notifier, never in the chart's log.

A script's declared bounds can tighten in a later release while an old saved
value is still on disk: params are validated at Save time
(`IndicatorScriptParamsSink`), never on load, and this must not take Load
History down over one script's stale config (`BOT-063`).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import FailureKind
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts import (
    MacdFullScript,
)
from Sagittarius_Elite_Warrior.src.support.indicators.ui.runner import (
    IndicatorScriptRunner,
)

_SCOPE = "market"
_CAUSE = "indicators.saved_params.macd_full"


def _runner(
    notifier: RecordingNotifier, errors: list[str], params: dict
) -> IndicatorScriptRunner:
    registry = IndicatorScriptRegistry()
    registry.register("macd_full", MacdFullScript)
    return IndicatorScriptRunner(
        registry=registry,
        emit_line=lambda name, x, y: None,
        emit_region=lambda key, spans: None,
        emit_info=lambda key, fields: None,
        emit_markers=lambda key, points: None,
        on_error=errors.append,
        notifier=notifier,
        scope=_SCOPE,
        get_params=lambda _key: params,
    )


def test_a_refused_saved_param_falls_back_to_defaults_and_tells_the_user() -> None:
    notifier = RecordingNotifier()
    errors: list[str] = []
    runner = _runner(notifier, errors, {"fast_period": -1})

    runner.rebuild(["macd_full"])

    assert "macd_full" in runner.active
    notice = notifier.last
    assert notice.kind is FailureKind.BACKGROUND
    assert notice.cause == _CAUSE
    assert notice.scope == _SCOPE
    assert notice.headline == (
        "Saved parameters for macd_full were ignored; the defaults are used."
    )
    assert notice.detail
    assert notice.detail not in notice.headline
    assert errors == [], "the failure is the notifier's, not the chart log's"


def test_add_script_tells_the_user_the_same_way() -> None:
    notifier = RecordingNotifier()
    runner = _runner(notifier, [], {"fast_period": -1})

    runner.add_script("macd_full")

    assert "macd_full" in runner.active
    assert [n.cause for n in notifier.failures] == [_CAUSE]


def test_params_that_load_again_clear_the_message_once() -> None:
    notifier = RecordingNotifier()
    params = {"fast_period": -1}
    runner = _runner(notifier, [], params)
    runner.rebuild(["macd_full"])

    params.clear()
    runner.rebuild(["macd_full"])
    runner.rebuild(["macd_full"])

    assert notifier.cleared == [_CAUSE]
