"""Tools → Indicator parameters… (`BOT-063`, moved from the Dev Board before
`EPIC-033P` deletes it): edits the parameters of the indicator script
selected in the Market mode's Indicators panel.

Presenter-owned (`async-ui-action-rule.md` §2), never registered. The dialog
is the Dev Board's (`StrategyParamsDialog` over an
`IndicatorScriptParamsSink`, one sink per opening, as that sink's docstring
explains); this object decides only when the command may run (a script
selected, declaring at least one input, and a store to save to) and tells
the presenter once the dialog closes, so the open charts redraw the script
with what was saved.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_catalog import (
    IndicatorScriptCatalog,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_params_store import (
    IndicatorScriptParamsStore,
)
from Sagittarius_Elite_Warrior.src.support.indicators.ui.script_params_sink import (
    IndicatorScriptParamsSink,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)

from .market_commands import INDICATOR_PARAMS
from .market_view import MarketView

logger = logging.getLogger("App.Trading.Market")


class IndicatorParamsCommand(QObject):
    """@brief Tools → Indicator parameters…, for the selected script."""

    #: Whether the command may run now.
    enabledChanged = Signal(bool)
    #: The dialog for this script key closed having saved new values.
    edited = Signal(str)

    def __init__(
        self,
        view: MarketView,
        catalog: IndicatorScriptCatalog,
        store: IndicatorScriptParamsStore | None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._catalog = catalog
        self._store = store
        view.indicator_selected.connect(lambda _key: self.refresh())

    def bind_commands(self, binder: ICommandBinder) -> None:
        binder.bind(
            INDICATOR_PARAMS,
            self._on_triggered,
            enabled=self.enabledChanged,
            initially_enabled=self._ready(),
        )

    def refresh(self) -> None:
        self.enabledChanged.emit(self._ready())

    def open(self) -> None:
        """Opens the dialog for the selected script; nothing when the
        command could not run (no store, no script, no input). Says
        `edited` only when the stored values changed: a Cancel, or a Save
        of the same values, redraws nothing (a redraw replays the whole
        history on the UI thread)."""
        key = self._view.selected_indicator
        store = self._store
        if store is None or not self._has_inputs(key):
            return
        logger.info("[market] indicator parameters of %s opened", key)
        saved = store.load_all().get(key)
        sink = IndicatorScriptParamsSink(self._catalog, store, key, parent=self)
        try:
            self._view.edit_indicator_params(sink)
        finally:
            sink.deleteLater()
        if store.load_all().get(key) != saved:
            self.edited.emit(key)

    def _on_triggered(self, _checked: bool) -> None:
        self.open()

    def _ready(self) -> bool:
        return self._store is not None and self._has_inputs(
            self._view.selected_indicator
        )

    def _has_inputs(self, key: str) -> bool:
        """Whether the script declares an input; an unknown key has none."""
        if not key:
            return False
        try:
            return bool(self._catalog.params_form(key, {}))
        except KeyError:
            return False
