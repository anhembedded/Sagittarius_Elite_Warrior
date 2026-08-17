"""Business-facing local validation for the Backtest toolbar (BOT-095E)."""

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.pre_backtest_assertions import (
    BacktestInputField,
    PreBacktestAssertionPipeline,
    PreBacktestInput,
)


def _validate(**changes: object):
    baseline = {
        "capital_text": "10000",
        "is_custom_range": False,
        "custom_start_text": "",
        "custom_end_text": "",
    }
    baseline.update(changes)
    return PreBacktestAssertionPipeline.default().validate(PreBacktestInput(**baseline))


def test_rejects_non_numeric_capital_with_the_capital_field_targeted():
    issues = _validate(capital_text="not-a-number")

    assert len(issues) == 1
    assert issues[0].field is BacktestInputField.INITIAL_CAPITAL
    assert "không hợp lệ" in issues[0].message


def test_rejects_non_finite_capital_instead_of_accepting_float_nan_or_inf():
    for raw_value in ("nan", "inf", "-inf"):
        issues = _validate(capital_text=raw_value)

        assert len(issues) == 1
        assert issues[0].field is BacktestInputField.INITIAL_CAPITAL


def test_rejects_non_positive_capital():
    issues = _validate(capital_text="0")

    assert issues[0].field is BacktestInputField.INITIAL_CAPITAL
    assert issues[0].message == "Vốn ban đầu phải lớn hơn 0."


def test_accepts_a_finite_positive_capital():
    assert _validate(capital_text="10000.50") == ()


def test_rejects_an_invalid_custom_start_date_without_checking_market_metadata():
    issues = _validate(
        is_custom_range=True,
        custom_start_text="2026/08/17",
        custom_end_text="2026-08-18 00:00",
    )

    assert issues[0].field is BacktestInputField.CUSTOM_START
    assert "định dạng" in issues[0].message


def test_rejects_a_custom_range_whose_end_is_not_after_its_start():
    issues = _validate(
        is_custom_range=True,
        custom_start_text="2026-08-17 10:00",
        custom_end_text="2026-08-17 10:00",
    )

    assert issues[0].field is BacktestInputField.CUSTOM_END
    assert issues[0].message == "Ngày bắt đầu phải trước ngày kết thúc."


def test_empty_custom_end_remains_an_unbounded_range_not_a_false_validation_error():
    assert (
        _validate(
            is_custom_range=True,
            custom_start_text="2026-08-17 10:00",
            custom_end_text="",
        )
        == ()
    )
