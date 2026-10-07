import pyqtgraph as pg
from PySide6 import QtCore
from PySide6.QtGui import QAction


class ViewportController(QtCore.QObject):
    """
    @brief Tracks whether the chart should auto-follow the newest candle (the default,
    TradingView-style "live" behavior) or stay frozen wherever the user panned/zoomed to,
    and owns the "Follow latest" action that resumes following (it is not the live stream, `EPIC-034G`).
    @details Single Responsibility: the follow state and the one action that ends a
    frozen view. Uses ViewBox.sigRangeChangedManually — emitted only on user-driven
    pan/zoom, never on the programmatic setXRange() this class itself performs — so it
    never fights the user.

    @par An action since `EPIC-033G`
    It was a "⏩ Live" push button moved over the plot's bottom-right corner, an
    overlay `ui-presentation-rule.md` §3 forbids. As a `QAction` it sits on the chart
    toolbar and in the plot's context menu, and is disabled while the chart already
    follows the live edge — the disabled state says what the hidden button did.
    """

    def __init__(self, plot: pg.PlotItem, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._plot = plot
        self._following = True

        self.follow_latest = QAction("&Follow latest", self)
        self.follow_latest.setObjectName("act_followLatest")
        self.follow_latest.setStatusTip("Follow the newest candle again")
        self.follow_latest.setEnabled(False)
        self.follow_latest.triggered.connect(self.resume_follow)
        plot.vb.menu.addAction(self.follow_latest)

        plot.vb.sigRangeChangedManually.connect(self._on_user_panned)

    @property
    def following(self) -> bool:
        """Whether the view tracks the newest candle."""
        return self._following

    def notify_new_data(self, latest_timestamp: float) -> None:
        """Called after every historical render / live tick to re-center the view."""
        if not self._following:
            return
        (x_min, x_max), _ = self._plot.vb.viewRange()
        span = x_max - x_min
        self._plot.setXRange(latest_timestamp - span, latest_timestamp, padding=0)

    def resume_follow(self) -> None:
        self._following = True
        self.follow_latest.setEnabled(False)

    def _on_user_panned(self, *_args: object) -> None:
        self._following = False
        self.follow_latest.setEnabled(True)

    def dispose(self) -> None:
        self._plot.vb.sigRangeChangedManually.disconnect(self._on_user_panned)
