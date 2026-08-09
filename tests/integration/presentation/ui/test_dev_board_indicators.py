"""
Automates Section B ("Indicators") of
Tasks/reports/dev_board_user_end_test_cases.md. Each test docstring cites
its TC-IND-## id so the two documents stay traceable to each other.

BOT-030 Phase 4: indicator toggles/periods now live on DashboardQmlViewModel
(view._view_model) instead of IndicatorControlCard widgets, and Load
History is a QML button (DevBoardPanel.qml) driven via `qml_item(...)
.clicked.emit()` — the same pattern already used for the Database/Settings
QML screens.
"""


def _open_dashboard(navigate):
    cfg = navigate("dashboard")
    return cfg["presenter_instance"], cfg["view_instance"]


def _click_load_history(view, qml_item):
    root = view.quick_widget.rootObject()
    qml_item(root, "btnLoadHistory").clicked.emit()


def test_rsi_only_registers_one_subplot(qtbot, main_window, navigate, qml_item):
    """TC-IND-01: enabling RSI then Load History adds exactly one subplot
    row with a legend entry, nothing else."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    view._view_model.rsiEnabled = True

    with qtbot.waitSignal(presenter.ui_indicator_data_signal, timeout=2000):
        _click_load_history(view, qml_item)

    card = view.chart_cards[0]
    assert list(card.indicators._curves.keys()) == ["RSI(14)"]
    # Volume (always present) + RSI = 2 subplot rows, no more.
    assert len(card.plot_layout.sub_plots) == 2


def test_ema_registers_as_overlay_not_subplot(qtbot, main_window, navigate, qml_item):
    """TC-IND-02: EMA must be drawn on the main price plot, not its own
    subplot row."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    view._view_model.emaEnabled = True

    with qtbot.waitSignal(presenter.ui_indicator_data_signal, timeout=2000):
        _click_load_history(view, qml_item)

    card = view.chart_cards[0]
    assert card.indicators._plots["EMA(20)"] is card.plot_layout.main_plot
    # Volume is the only subplot row — EMA did not add one.
    assert len(card.plot_layout.sub_plots) == 1


def test_macd_extracts_macd_field_not_signal_or_histogram(
    qtbot, main_window, navigate, qml_item
):
    """TC-IND-03: the presenter's extract_value for MACD must read
    `reading.macd`, not `.signal`/`.histogram`."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    view._view_model.macdEnabled = True

    with qtbot.waitSignal(presenter.ui_indicator_data_signal, timeout=2000):
        _click_load_history(view, qml_item)

    active = presenter.active_indicators["MACD"]
    assert active.kind == "subplot"

    from Binace_Bot.src.domain.indicators.macd import MACDValue

    fake_reading = MACDValue(macd=1.23, signal=9.99, histogram=-8.76)
    assert active.extract_value(fake_reading) == 1.23


def test_all_three_indicators_together_no_overlap(
    qtbot, main_window, navigate, qml_item
):
    """TC-IND-04: RSI+EMA+MACD together must not collide — EMA overlay on
    main plot, RSI and MACD each on their own subplot row."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    view._view_model.rsiEnabled = True
    view._view_model.emaEnabled = True
    view._view_model.macdEnabled = True

    with qtbot.waitSignals(
        [presenter.ui_indicator_data_signal] * 3, timeout=2000, order="none"
    ):
        _click_load_history(view, qml_item)

    card = view.chart_cards[0]
    assert set(card.indicators._curves.keys()) == {"RSI(14)", "EMA(20)", "MACD"}
    assert card.indicators._plots["EMA(20)"] is card.plot_layout.main_plot
    assert card.indicators._plots["RSI(14)"] is not card.plot_layout.main_plot
    assert card.indicators._plots["MACD"] is not card.plot_layout.main_plot
    assert card.indicators._plots["RSI(14)"] is not card.indicators._plots["MACD"]
    # Volume + RSI + MACD = 3 subplot rows.
    assert len(card.plot_layout.sub_plots) == 3


def test_unchecking_then_reload_removes_subplot_row_entirely(
    qtbot, main_window, navigate, qml_item
):
    """TC-IND-06: unchecking RSI then reloading must remove the subplot ROW
    (not just its curve) — regression test for the "empty panel left
    behind" half of the duplicate-indicator bug fixed this session."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    view._view_model.rsiEnabled = True

    with qtbot.waitSignal(presenter.ui_indicator_data_signal, timeout=2000):
        _click_load_history(view, qml_item)
    card = view.chart_cards[0]
    assert len(card.plot_layout.sub_plots) == 2  # Volume + RSI

    view._view_model.rsiEnabled = False
    with qtbot.waitSignal(presenter.ui_history_reloaded_signal, timeout=2000):
        _click_load_history(view, qml_item)

    assert "RSI(14)" not in card.indicators._curves
    assert len(card.plot_layout.sub_plots) == 1  # only Volume remains


def test_repeated_load_history_does_not_duplicate_indicators(
    qtbot, main_window, navigate, qml_item
):
    """TC-IND-07: clicking "Load History" 3 times in a row with the same
    indicator set must leave exactly one curve/subplot per indicator —
    the exact bug reported by the user this session ("start nhieu lan no
    bi loi nay")."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    view._view_model.rsiEnabled = True
    view._view_model.emaEnabled = True
    view._view_model.macdEnabled = True

    for _ in range(3):
        with qtbot.waitSignal(presenter.ui_history_reloaded_signal, timeout=2000):
            _click_load_history(view, qml_item)

    card = view.chart_cards[0]
    assert sorted(card.indicators._curves.keys()) == ["EMA(20)", "MACD", "RSI(14)"]
    assert len(card.plot_layout.sub_plots) == 3  # Volume + RSI + MACD, never more
    assert len(card.crosshair._plots) == 4  # main + Volume + RSI + MACD


def test_macd_warmup_produces_no_readings_with_too_little_history(
    qtbot, main_window, navigate, qml_item
):
    """TC-IND-11: MACD needs 26+9 closes to warm up; with only 5 mock
    candles (see conftest.MOCK_KLINE_COUNT) every update() call must
    return None — no NaN/garbage point should reach the chart."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    view._view_model.macdEnabled = True

    with qtbot.waitSignal(presenter.ui_indicator_data_signal, timeout=2000):
        _click_load_history(view, qml_item)

    active = presenter.active_indicators["MACD"]
    assert active.x_data == []
    assert active.y_data == []


def test_toggling_period_after_load_has_no_live_effect(
    qtbot, main_window, navigate, qml_item
):
    """TC-IND-05 / TC-GAP-07: changing the period after Load History has
    already run must NOT retroactively change the already-registered
    indicator — the ViewModel's rsiPeriod is only read at click time by
    _build_active_indicators, so the effect only applies on the *next*
    Load History/Start Live click."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    view._view_model.rsiEnabled = True
    view._view_model.rsiPeriod = 14

    with qtbot.waitSignal(presenter.ui_indicator_data_signal, timeout=2000):
        _click_load_history(view, qml_item)
    assert "RSI(14)" in presenter.active_indicators

    view._view_model.rsiPeriod = 7
    qtbot.wait(50)  # give any (nonexistent) signal a chance to fire

    assert "RSI(14)" in presenter.active_indicators
    assert "RSI(7)" not in presenter.active_indicators
