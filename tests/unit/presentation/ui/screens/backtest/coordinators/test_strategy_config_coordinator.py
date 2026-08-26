"""`StrategyConfigCoordinator` — built with no presenter and no container."""

from __future__ import annotations

from typing import Any

from Sagittarius_Elite_Warrior.src.domain.scripting import InputKind, ScriptInput
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.coordinators import (
    StrategyConfigCoordinator,
)


class _Strategy:
    """Accepts `{"period": int}` and rejects anything else, the same way the
    real strategies validate by construction.

    Declares a real `ScriptInput` rather than a stand-in: `build_bot_params_
    schema` reads `kind`, `group`, `options` and more off it, and a fake with
    only the two fields this test cares about failed on the first of those.
    """

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        params = params or {}
        if "period" in params and int(params["period"]) <= 0:
            raise ValueError("period phải > 0")
        self.inputs = [
            ScriptInput(
                name="period", label="Chu kỳ", kind=InputKind.INT, default=14, minval=1
            )
        ]


class _Registry:
    def __init__(self, strategies: dict[str, type]) -> None:
        self._strategies = strategies

    def available(self) -> dict[str, type]:
        return self._strategies


class _Logger:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []

    def __getattr__(self, name: str):
        def record(*args):
            self.calls.append((name, args))

        return record


class _State:
    """Stands in for the presenter attributes the coordinator reads/writes."""

    def __init__(self, metadata=None, klines=None) -> None:
        self.params: dict[str, Any] | None = None
        self.symbol = "BTCUSDT"
        self.metadata = metadata
        self.klines = klines or []
        self.config_changed = 0


def _build(strategies=None, state=None):
    view_model = BackTestViewModel()
    state = state or _State()
    logger = _Logger()

    def bump() -> None:
        state.config_changed += 1

    coordinator = StrategyConfigCoordinator(
        view_model=view_model,
        strategy_registry=_Registry(
            {"s1": _Strategy} if strategies is None else strategies
        ),
        logger=logger,
        get_strategy_params=lambda: state.params,
        set_strategy_params=lambda p: setattr(state, "params", p),
        get_symbol=lambda: state.symbol,
        get_market_metadata=lambda _symbol: state.metadata,
        get_current_raw_klines=lambda: state.klines,
        notify_config_changed=bump,
    )
    view_model.selectedStrategyKey = "s1"
    return coordinator, view_model, state, logger


def test_changing_strategy_discards_the_previous_params(qtbot) -> None:
    """BOT-047: a different strategy has a different schema, so values saved
    for the old one would be ignored or rejected against the new one."""
    coordinator, _vm, state, _logger = _build()
    state.params = {"period": 20}

    coordinator.on_strategy_selection_changed()

    assert state.params is None
    assert state.config_changed == 1


def test_a_rejected_param_is_not_saved_and_asks_for_no_re_run(qtbot) -> None:
    """An out-of-range value must show an inline error and leave the modal
    open — never silently fall back to a default."""
    coordinator, view_model, state, _logger = _build()

    should_rerun = coordinator.apply_bot_params({"period": "-5"})

    assert should_rerun is False
    assert state.params is None
    assert "period" in view_model.botParamsError


def test_an_accepted_param_is_saved_and_asks_for_a_re_run(qtbot) -> None:
    coordinator, view_model, state, _logger = _build()

    should_rerun = coordinator.apply_bot_params({"period": "21"})

    assert should_rerun is True
    assert state.params == {"period": 21}
    assert view_model.botParamsError == ""


def test_an_unknown_strategy_key_saves_nothing(qtbot) -> None:
    coordinator, _vm, state, _logger = _build(strategies={})

    assert coordinator.apply_bot_params({"period": "21"}) is False
    assert state.params is None


def test_broker_properties_are_applied_with_their_declared_types(qtbot) -> None:
    """The table drives the coercion, so a string from QML must still arrive
    as an int/float/bool on the view model."""
    coordinator, view_model, _state, _logger = _build()

    coordinator.apply_strategy_properties(
        {
            "properties": {
                "initial_capital": 5000,
                "pyramiding": "3",
                "long_leverage": "2.5",
                "take_profit_enabled": 1,
            }
        }
    )

    assert view_model.initialCapitalText == "5000"
    assert view_model.pyramiding == 3
    assert view_model.longLeverage == 2.5
    assert view_model.takeProfitPctEnabled is True


def test_properties_are_left_alone_when_the_inputs_are_rejected(qtbot) -> None:
    """The strategy inputs are validated BEFORE the broker properties are
    written, so a bad input must not half-apply the rest of the payload."""
    coordinator, view_model, _state, _logger = _build()
    before = view_model.pyramiding

    should_rerun = coordinator.apply_strategy_properties(
        {"inputs": {"period": "-5"}, "properties": {"pyramiding": "3"}}
    )

    assert should_rerun is False
    assert view_model.pyramiding == before


def test_no_metadata_clears_any_previous_verdict(qtbot) -> None:
    """Asserting the status is UNVERIFIED_MISSING from a fresh view model
    proves nothing — that is already its default. Seeding a different verdict
    first is what shows the method actually writes one."""
    coordinator, view_model, _state, _logger = _build()
    view_model.set_market_rule_verification("VERIFIED", "đã xác minh")
    assert view_model.marketRuleVerificationStatus == "VERIFIED"

    coordinator.refresh_market_rule_verification()

    assert view_model.marketRuleVerificationStatus == "UNVERIFIED_MISSING"


def test_capital_validation_message_reaches_the_view_model(qtbot) -> None:
    coordinator, view_model, _state, _logger = _build()

    coordinator.set_capital_validation_message("not-a-number")

    assert view_model.capitalValidationMessage != ""
