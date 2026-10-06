from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exit_reason import (
    ExitReason,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.trade_log_row import (
    TradeLogRow,
    build_trade_log_rows,
    trade_details,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.readout_slot import Readout
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    APP_VALUE_FORMATTER,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ReadoutForm,
)

_T0 = datetime(2026, 1, 1, 6, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 1, 18, 0, tzinfo=UTC)


def _make_trade(pnl: float, pnl_percent: float = 1.0) -> Trade:
    return Trade(
        symbol="ETHUSDT",
        entry_time=_T0,
        entry_price=1939.5,
        exit_time=_T1,
        exit_price=1908.5,
        quantity=0.5,
        pnl=pnl,
        pnl_percent=pnl_percent,
        fees_paid=0.5,
        entry_reason="EMA Crossover 3/5 crossed above",
        exit_reason=ExitReason.STRATEGY_SIGNAL,
        metadata={"qml_score": 92},
    )


def test_build_trade_log_rows_indexes_from_1_in_order():
    trades = [_make_trade(10.0), _make_trade(-5.0), _make_trade(20.0)]

    rows = build_trade_log_rows(trades)

    assert [row.index for row in rows] == [1, 2, 3]
    assert rows[1].pnl == -5.0


def test_build_trade_log_rows_carries_the_trades_side_through():
    long_trade = _make_trade(10.0)
    short_trade = Trade(
        symbol="ETHUSDT",
        entry_time=_T0,
        entry_price=1939.5,
        exit_time=_T1,
        exit_price=1908.5,
        quantity=0.5,
        pnl=15.0,
        pnl_percent=1.5,
        fees_paid=0.5,
        side=PositionSide.SHORT,
    )

    rows = build_trade_log_rows([long_trade, short_trade])

    assert rows[0].side is PositionSide.LONG
    assert rows[1].side is PositionSide.SHORT


# ================= BOT-045: Trade Journal Detail =================


def test_build_trade_log_rows_carries_entry_exit_reason_and_metadata():
    trades = [_make_trade(10.0)]

    rows = build_trade_log_rows(trades)

    assert rows[0].entry_reason == "EMA Crossover 3/5 crossed above"
    assert rows[0].exit_reason is ExitReason.STRATEGY_SIGNAL
    assert rows[0].metadata == {"qml_score": 92}


# ================= BOT-106D: MAE/MFE =================


def test_build_trade_log_rows_carries_mae_and_mfe_through():
    trade = Trade(
        symbol="ETHUSDT",
        entry_time=_T0,
        entry_price=1939.5,
        exit_time=_T1,
        exit_price=1908.5,
        quantity=0.5,
        pnl=10.0,
        pnl_percent=1.0,
        fees_paid=0.5,
        mae_percent=-3.21,
        mfe_percent=5.67,
    )

    rows = build_trade_log_rows([trade])

    assert rows[0].mae_percent == -3.21
    assert rows[0].mfe_percent == 5.67


def test_build_trade_log_rows_defaults_mae_mfe_to_zero():
    """0.0 is `Trade`'s own "no excursion observed" convention, not a bug —
    every pre-`BOT-106B` construction site still gets a row."""
    rows = build_trade_log_rows([_make_trade(10.0)])

    assert rows[0].mae_percent == 0.0
    assert rows[0].mfe_percent == 0.0


# ================= BOT-045: the selected trade's journal =================
# A read-out of raw values, written by the application's formatter by each
# row's kind (`EPIC-033N`), as a `ReadoutForm` shows them.


def _shown(row: TradeLogRow) -> dict[str, str]:
    """Title -> text, as the read-out writes each value."""
    readout = trade_details(row)
    form = ReadoutForm(readout.specs, APP_VALUE_FORMATTER)
    form.set_values(readout.values)
    return {spec.title: form.value_text(spec.key) for spec in readout.specs}


def test_a_blank_entry_reason_is_an_empty_value(qapp):
    """Unknown reads as nothing, never a glyph (`EPIC-033N`)."""
    row = TradeLogRow(1, _T0, 100.0, _T1, 110.0, 1.0, 10.0, 10.0, entry_reason="")

    assert _shown(row)["Entry reason"] == ""


def test_the_exit_reason_reads_as_words(qapp):
    row = TradeLogRow(
        1,
        _T0,
        100.0,
        _T1,
        110.0,
        1.0,
        10.0,
        10.0,
        exit_reason=ExitReason.END_OF_BACKTEST,
    )

    assert _shown(row)["Exit reason"] == "End of backtest"


def test_the_duration_is_a_duration_the_formatter_writes(qapp):
    row = TradeLogRow(1, _T0, 100.0, _T1, 110.0, 1.0, 10.0, 10.0)  # 06:00 to 18:00
    readout = trade_details(row)

    assert readout.values["duration"] == timedelta(hours=12)
    assert _kind(readout, "duration") is ColumnKind.DURATION
    assert _shown(row)["Duration"] == "12:00:00"


def test_a_duration_never_reads_negative():
    row = TradeLogRow(1, _T1, 100.0, _T0, 110.0, 1.0, 10.0, 10.0)

    assert trade_details(row).values["duration"] == timedelta(0)


def test_excursions_are_percentages_the_formatter_writes(qapp):
    row = TradeLogRow(
        1, _T0, 100.0, _T1, 110.0, 1.0, 10.0, 10.0, mae_percent=-3.21, mfe_percent=5.67
    )
    readout = trade_details(row)

    assert _kind(readout, "mae") is ColumnKind.PERCENT
    assert _shown(row)["Worst excursion (MAE)"] == "-3.21%"
    assert _shown(row)["Best excursion (MFE)"] == "5.67%"


def test_a_strategys_metadata_follows_with_readable_labels_in_its_order(qapp):
    row = TradeLogRow(
        1,
        _T0,
        100.0,
        _T1,
        110.0,
        1.0,
        10.0,
        10.0,
        metadata={"qml_score": 92.5, "zone": "demand & supply"},
    )
    readout = trade_details(row)

    titles = [spec.title for spec in readout.specs]
    assert titles[-2:] == ["Qml Score", "Zone"]
    assert [spec.kind for spec in readout.specs[-2:]] == [
        ColumnKind.QUANTITY,
        ColumnKind.TEXT,
    ]
    assert _shown(row)["Qml Score"] == "92.5"
    assert _shown(row)["Zone"] == "demand & supply"


def test_an_ampersand_in_a_metadata_key_is_text_not_an_access_key():
    row = TradeLogRow(1, _T0, 100.0, _T1, 110.0, 1.0, 10.0, 10.0, metadata={"r&d": "x"})

    assert trade_details(row).specs[-1].title == "R&&D"


def test_no_metadata_adds_no_line():
    row = TradeLogRow(1, _T0, 100.0, _T1, 110.0, 1.0, 10.0, 10.0, metadata={})

    assert [spec.title for spec in trade_details(row).specs] == [
        "Entry reason",
        "Exit reason",
        "Duration",
        "Worst excursion (MAE)",
        "Best excursion (MFE)",
    ]


def _kind(readout: Readout, key: str) -> ColumnKind:
    return next(spec.kind for spec in readout.specs if spec.key == key)
