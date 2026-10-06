"""The environment banner and the stock dialogs, pictured for a reviewer
(`pr-review` SKILL §5.1), beside the modes `test_workbench_screenshots.py`
pictures.

The booted window in that harness registers no banner factory and opens no
dialog, so `EPIC-033M`'s rebuilt banner (icon, wrapped text, weight by
severity, a platform frame) and its stock dialogs were in no picture (review
of PR #383). Each is built here as its screen builds it, shown at its own
size hint (a banner at the narrowest window's width) and saved under
`SEW_UI_SCREENSHOTS`, named `dialog~<what>.png`.
The assertions keep each picture worth opening: none is blank, and none
hides content behind a scrolling tab row or a sideways scroll bar.

Retire when: a reviewer no longer judges the UI from pictures of it.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QTabBar,
    QToolButton,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.contracts.param_field import (
    ParamField,
    ParamGroup,
    ParamKind,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.critical_error_dialog import (
    CriticalErrorDialog,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.venue_alignment import (
    VenueAlignment,
)
from Sagittarius_Elite_Warrior.src.support.charting.timeframe_picker import (
    PinnedTimeframes,
    TimeframePickerDialog,
    TimeframeSelection,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.environment_banner.environment_banner import (
    EnvironmentBanner,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.environment_banner.environment_banner_content import (
    venue_alignment_banner_content,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.param_form.strategy_params_dialog import (
    StrategyParamsDialog,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.symbol_picker import (
    SymbolPickerOverlay,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.time_range_picker import (
    TimeRangePickerDialog,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_screenshots import (
    SCREENSHOT_DIR_ENV,
    is_blank,
)


class _ParamsSink(QWidget):
    """`BotParamsSink` as a screen's view model offers it: a real `QObject`
    with the change signal, the groups, and the save and step calls."""

    botParamsChanged = Signal()  # noqa: N815 - BotParamsSink's own Qt spelling

    def __init__(self, groups: tuple[ParamGroup, ...]) -> None:
        super().__init__()
        self.botParamsGroups = groups
        self.botParamsError = ""

    def requestBotParamsSave(self, values: dict) -> None:  # noqa: N802 - see above
        """Nothing to save in a picture."""

    def step_bot_param_value(
        self, field_name: str, raw_value: str, direction: int
    ) -> str:
        return raw_value


def _banner(alignment: VenueAlignment) -> Callable[[], QWidget]:
    return lambda: EnvironmentBanner(venue_alignment_banner_content(alignment))


def _critical_error(details_shown: bool) -> QWidget:
    dialog = CriticalErrorDialog(
        title="Critical System Error",
        message="An unexpected error occurred in the UI layer.",
        error_details="ZeroDivisionError: division by zero",
        traceback_str='Traceback (most recent call last):\n  File "probe.py", line 1\n',
    )
    dialog.show_details.setChecked(details_shown)
    return dialog


def _strategy_params() -> QWidget:
    fields = (
        ParamField(
            name="fast", label="Fast EMA", kind=ParamKind.INT, default=9, value=9
        ),
        ParamField(
            name="slow", label="Slow EMA", kind=ParamKind.INT, default=21, value=21
        ),
    )
    sink = _ParamsSink((ParamGroup(label="Trend", fields=fields),))
    dialog = StrategyParamsDialog(sink)
    sink.setParent(dialog)
    return dialog


def _time_range() -> QWidget:
    dialog = TimeRangePickerDialog(
        get_from_text=lambda: "2026-07-01 00:00",
        get_to_text=lambda: "2026-07-08 00:00",
        get_timeframe_seconds=lambda: 300,
        get_timeframe_label=lambda: "5m",
    )
    dialog.open_dialog()
    return dialog


def _symbol_picker() -> QWidget:
    return SymbolPickerOverlay(
        get_symbols=lambda: ["BTCUSDT", "ETHUSDT", "ETHBTC", "BNBUSDT", "SOLUSDT"],
        get_favourites=lambda: ["BTCUSDT"],
        get_recents=lambda: ["ETHUSDT"],
        get_current=lambda: "ETHUSDT",
    )


def _timeframe_picker() -> QWidget:
    pinned = PinnedTimeframes(initial=["1m", "1h"])
    selection = TimeframeSelection(
        get_codes=lambda: ["1m", "5m", "15m", "1h", "4h", "1d"],
        get_current=lambda: "1h",
        get_pinned=pinned.get,
        set_pinned=pinned.set,
    )
    selection.refresh()
    dialog = TimeframePickerDialog(selection)
    selection.setParent(dialog)
    dialog.open_dialog()
    return dialog


#: The narrowest window the conformance suite measures (`WINDOW_SIZES`).
_BANNER_WIDTH = 1024

_PICTURED: dict[str, Callable[[], QWidget]] = {
    "banner-trading-off": _banner(VenueAlignment.TRADING_DISABLED),
    "banner-aligned": _banner(VenueAlignment.ALIGNED),
    "banner-market-mismatch": _banner(VenueAlignment.MARKET_MISMATCH),
    "banner-mainnet-data-testnet-orders": _banner(
        VenueAlignment.DATA_MAINNET_ORDERS_TESTNET
    ),
    "critical-error": lambda: _critical_error(details_shown=False),
    "critical-error-details": lambda: _critical_error(details_shown=True),
    "strategy-params": _strategy_params,
    "time-range": _time_range,
    "symbol-picker": _symbol_picker,
    "timeframe-picker": _timeframe_picker,
}


def _clipped(widget: QWidget) -> list[str]:
    """What a window shown at its own size still scrolls to reach: a tab row
    showing its scroll arrows, or a view showing a horizontal scroll bar
    (review of PR #385: both passed a "not blank" picture)."""
    tab_rows = [
        f"tab row {bar.objectName() or type(bar).__name__} scrolls"
        for bar in widget.findChildren(QTabBar)
        if bar.isVisible()
        and any(arrow.isVisible() for arrow in bar.findChildren(QToolButton))
    ]
    views = [
        f"view {view.objectName() or type(view).__name__} scrolls sideways"
        for view in widget.findChildren(QAbstractScrollArea)
        if view.isVisible() and view.horizontalScrollBar().isVisible()
    ]
    return tab_rows + views


@pytest.mark.parametrize("name", list(_PICTURED))
def test_each_dialog_and_banner_is_pictured(qapp, name: str, tmp_path: Path) -> None:
    out_dir = Path(os.environ.get(SCREENSHOT_DIR_ENV) or tmp_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    widget = _PICTURED[name]()
    try:
        size = widget.sizeHint().expandedTo(widget.minimumSizeHint())
        if name.startswith("banner"):
            # A banner spans its mode's width; picture it at the smallest window.
            size.setWidth(_BANNER_WIDTH)
        widget.resize(size)
        widget.show()
        for _ in range(3):
            QApplication.processEvents()
        picture = widget.grab()
        path = out_dir / f"dialog~{name}.png"
        assert picture.save(str(path)), f"could not write {path}"

        assert not is_blank(picture.toImage()), f"{name} is pictured blank"
        assert _clipped(widget) == [], f"{name} hides content at its own size"
    finally:
        widget.close()
        widget.deleteLater()
        QApplication.processEvents()
