from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QSplitter, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card import (
    ChartCard,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.timeframe_pin_preferences import (
    TimeframePinPreferences,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView

from .dev_board_panel import DevBoardPanel


class DashboardView(BaseView):
    """
    @brief The View for the Dev Board Screen — a developer testbed, not the
    app's end-user dashboard.

    @details
    Hybrid layout (BOT-030 Phase 4, migrated off QML at EPIC-006D): a
    QSplitter with the dynamic ChartCards (QtWidgets/pyqtgraph — stays that
    way permanently) on the left, and a `DevBoardPanel` (top bar, System
    Controls, Indicators, Monitor log) on the right. FSM state reaches the
    panel through `apply_ui_mode` -> the view model's `uiMode` property,
    same mechanism as before — only the render layer changed.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._view_model = None
        self._panel: DevBoardPanel | None = None
        # Follow-up to `EPIC-015` Phase 4: self-constructed default so a bare
        # DashboardView() still works unpersisted; DashboardPresenter
        # overrides this with the DI-resolved, shared store via
        # set_timeframe_pin_preferences() in production — same shape and
        # reason as BackTestView's own fallback.
        self._timeframe_pin_preferences = TimeframePinPreferences()
        self._setup_ui()

    def _setup_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(20, 20, 20, 20)
        outer_layout.setSpacing(15)

        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        outer_layout.addWidget(self._main_splitter, 1)

        # Left column: QScrollArea for dynamic ChartCards.
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.charts_container = QWidget()
        self.charts_layout = QVBoxLayout(self.charts_container)
        self.charts_layout.setContentsMargins(0, 0, 0, 0)
        self.charts_layout.setSpacing(15)
        # No trailing stretch here: chart cards are added with a stretch factor
        # (see render_symbol_cards) so they expand to fill the available height
        # instead of being squeezed to their minimum size with empty space below.

        self.scroll_area.setWidget(self.charts_container)
        self._main_splitter.addWidget(self.scroll_area)

    def set_view_model(self, view_model, context_name: str = "viewModel") -> None:
        """Builds the right-hand DevBoardPanel against `view_model` — the
        panel takes its ViewModel at construction time (no late-binding
        needed, unlike the old QML context-property registration this
        replaces)."""
        self._view_model = view_model
        self._panel = DevBoardPanel(view_model)
        self._main_splitter.addWidget(self._panel)
        self._main_splitter.setStretchFactor(0, 3)  # Charts get more room initially
        self._main_splitter.setStretchFactor(1, 1)
        self._main_splitter.setSizes([900, 400])

    def set_symbol_preferences(self, preferences) -> None:
        """EPIC-014: DashboardPresenter injects the container-registered
        favourites/recents store here — this view, like BackTestView, has no
        container access. Forwarded to the panel, which owns the picker; a
        no-op before `set_view_model()` has built one."""
        if self._panel is not None:
            self._panel.set_symbol_preferences(preferences)

    def set_timeframe_pin_preferences(
        self, preferences: TimeframePinPreferences
    ) -> None:
        """Follow-up to `EPIC-015` Phase 4: `DashboardPresenter` injects the
        container-registered, per-symbol pinned-timeframe store here. Unlike
        `set_symbol_preferences` above, this View owns `render_symbol_cards`
        itself (it builds `ChartCard`s directly, not through a panel), so
        the store is kept on `self` and handed to every card built from now
        on — including a card rebuilt for a symbol already seen, which is
        exactly how it recovers that symbol's previously pinned set across
        Dev Board's symbol-list rebuilds."""
        self._timeframe_pin_preferences = preferences

    def apply_ui_mode(self, mode, section_key: str = "main") -> None:
        """Receives FSM state changes from BasePresenter (duck-typed fallback
        branch — this view has no `control_card`) and forwards them to the
        ViewModel's `uiMode` property, which DevBoardPanel binds against."""
        if self._view_model is None:
            return
        mode_value = getattr(mode, "value", mode)
        self._view_model.set_ui_mode(str(mode_value))

    def render_symbol_cards(self, symbols: list[str]) -> list:
        """
        @brief Dynamically instantiates ChartCards for given symbols.
        @returns A list of the created ChartCards.
        """
        # Clear existing cards first
        for i in reversed(range(self.charts_layout.count())):
            item = self.charts_layout.itemAt(i)
            widget = item.widget()
            if widget:
                # 1. Clear dữ liệu đồ họa ngầm của pyqtgraph
                if hasattr(widget, "cleanup"):
                    widget.cleanup()

                # 2. Xóa widget khỏi layout
                self.charts_layout.removeItem(item)

                # 3. Ra lệnh hủy hoàn toàn trong bộ nhớ C++
                widget.deleteLater()

        self.chart_cards = []

        for symbol in symbols:
            card = ChartCard(
                symbol, timeframe_pin_preferences=self._timeframe_pin_preferences
            )
            self.chart_cards.append(card)
            # Stretch factor 1: cards share the full available height instead of
            # shrinking to their minimum size (there is no trailing spacer item).
            self.charts_layout.addWidget(card, 1)

        return self.chart_cards
