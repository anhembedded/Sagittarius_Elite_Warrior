"""`BOT-233` — draws the stored candles of the period the workbench is set to, and says what they are.

Owns the preview (`CandlePreview`) and decides what the chart and the line under the commands show from
it. The presenter asks it to `follow` on every refresh; it draws only when the window changed or an
answer came, and never over a result, which holds the chart until the next run replaces it.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_stored_candles import (
    StoredCandles,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench import (
    workbench_words as words,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench_view import (
    BacktestWorkbenchView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.candle_preview import (
    CandlePreview,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.candle_preview_words import (
    preview_text,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.candle_window import (
    CandleWindow,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.sandbox_editing import (
    SandboxEditing,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.workbench_failure import (
    failure_notice,
)


class CandleDrawing(QObject):
    """@brief The chart's candles before a result, from one `CandlePreview`."""

    def __init__(
        self,
        view: BacktestWorkbenchView,
        preview: CandlePreview,
        sandbox: SandboxEditing,
        notifier: INotifier,
        result_shown: Callable[[], bool],
        changed: Callable[[], None],
    ) -> None:
        super().__init__(view)
        self._view = view
        self._preview = preview
        self._sandbox = sandbox
        self._notifier = notifier
        self._result_shown = result_shown
        self._changed = changed
        preview.loaded.connect(self._on_candles_read)

    @property
    def wanted(self) -> CandleWindow | None:
        return self._preview.wanted

    @property
    def found(self) -> StoredCandles | None:
        return self._preview.found

    @property
    def stored_line(self) -> str:
        """What the stored candles are, said under the commands."""
        return preview_text(
            self._preview.wanted, self._preview.found, loading=self._preview.is_reading
        ).line

    def follow(self) -> None:
        """Offers the intervals the bot's market loads, reads the window the page is now set to and
        draws what is known of it."""
        plan = self._sandbox.plan
        if plan is not None:
            self._view.offer_intervals_of(plan.venue)
        if self._preview.want(self.window()):
            self.draw()

    def forget(self) -> None:
        self._preview.forget()

    def reload(self) -> None:
        self._preview.reload()

    def close(self) -> None:
        self._preview.close()

    def draw(self) -> None:
        """The stored candles on the chart, unless a result holds it."""
        if self._result_shown():
            return
        found, window = self._preview.found, self._preview.wanted
        text = preview_text(window, found, loading=self._preview.is_reading).chart
        if window is None and self._sandbox.plan is not None:
            text = words.PERIOD_ORDER
        self._view.show_candles(found.candles if found is not None else (), text)

    def window(self) -> CandleWindow | None:
        """The sandbox's symbol and venue, the chosen interval and period; `None` with no bot or a
        period that does not end after it starts."""
        plan = self._sandbox.plan
        start, end = self._view.chosen_period()
        if plan is None or end <= start:
            return None
        return CandleWindow(
            plan.symbol, plan.venue, self._view.chosen_interval(), start, end
        )

    def _on_candles_read(
        self, window: CandleWindow, found: object, detail: str
    ) -> None:
        if detail:
            self._notifier.report_failure(failure_notice("candles", detail))
        self.draw()
        self._changed()
