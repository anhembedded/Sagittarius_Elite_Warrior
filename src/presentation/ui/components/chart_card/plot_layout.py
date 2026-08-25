import logging
from datetime import UTC, datetime
from enum import Enum

import pyqtgraph as pg
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from Sagittarius_Elite_Warrior.src.presentation.ui.common.qt_platform import (
    is_headless_qt_platform,
    qt_platform_name,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.services.display_timezone_service import (
    DEFAULT_TIMEZONE,
    get_utc_offset_seconds,
)

# Under "App" so StdLogger's handlers apply — see cached_frame_interaction.
logger = logging.getLogger("App.ChartPlotLayout")


class ChartAntialiasMode(str, Enum):
    """Controls whether smoothing is paid globally or only by line layers."""

    GLOBAL = "global"
    LAYERED = "layered"


class ChartPlotLayout:
    """
    @brief Owns the pyqtgraph GraphicsLayoutWidget and all row/stretch bookkeeping.
    @details Single Responsibility: plot construction & layout only — no candlestick data,
    no indicator state, no mouse/crosshair handling.
    """

    MAIN_PLOT_ROW = 1
    MAIN_PLOT_STRETCH = 3

    def __init__(
        self,
        *,
        use_opengl: bool = False,
        antialias_mode: ChartAntialiasMode = ChartAntialiasMode.LAYERED,
    ) -> None:
        self.antialias_mode = antialias_mode
        self.opengl_requested = bool(use_opengl)
        self.uses_opengl = False
        self.backend_fallback_reason: str | None = None
        self._display_timezone = DEFAULT_TIMEZONE
        self.widget = pg.GraphicsLayoutWidget()
        self.widget.setAntialiasing(antialias_mode is ChartAntialiasMode.GLOBAL)
        self._configure_render_backend()
        self.widget.setBackground("default")

        self.crosshair_label = self.widget.addLabel(
            f"<span style=f'color: {Palette.MUTED}; font-size: 11px;'>Hover to see data</span>",
            row=0,
            col=0,
            justify="right",
        )

        # A second header-row label for custom indicator scripts' status
        # panels (BOT-032 — Pine's `table.cell`). Its own column rather than
        # sharing crosshair_label's, so script status and hover data never
        # overwrite each other; empty by default, so it takes no visible
        # space until a script actually calls self.info(...). Every plot row
        # below it uses colspan=2 (see main_plot/add_subplot) so this extra
        # column's own width never narrows the chart.
        self.script_info_label = self.widget.addLabel("", row=0, col=1, justify="left")

        utc_offset = get_utc_offset_seconds(
            datetime.now(UTC).timestamp(), self._display_timezone
        )
        date_axis = pg.DateAxisItem(orientation="bottom", utcOffset=utc_offset)
        self.main_plot = self.widget.addPlot(
            row=self.MAIN_PLOT_ROW,
            col=0,
            colspan=2,
            axisItems={"bottom": date_axis},
        )
        self.main_plot.showGrid(x=True, y=True, alpha=0.2)

        # Enable TradingView style: Scroll zooms X, Y auto-scales to visible X
        self.main_plot.setMouseEnabled(x=True, y=True)
        self.main_plot.vb.setAutoVisible(y=True)
        self.main_plot.vb.enableAutoRange(axis="y", enable=True)
        self.widget.ci.layout.setRowStretchFactor(
            self.MAIN_PLOT_ROW, self.MAIN_PLOT_STRETCH
        )

        self.sub_plots: list[pg.PlotItem] = []
        self.plots: list[pg.PlotItem] = [self.main_plot]
        self._next_row = self.MAIN_PLOT_ROW + 1

    @property
    def render_backend(self) -> str:
        return "opengl" if self.uses_opengl else "cpu"

    def _configure_render_backend(self) -> None:
        if not self.opengl_requested:
            return
        if is_headless_qt_platform():
            self.backend_fallback_reason = (
                f"unsupported Qt platform: {qt_platform_name()}"
            )
            return
        try:
            # Per-widget switch: Dashboard and every existing ChartCard stay
            # on their CPU viewport unless their owner explicitly requests GL.
            self.widget.useOpenGL(True)
        except (RuntimeError, TypeError, ValueError) as exc:
            self.backend_fallback_reason = f"OpenGL setup failed: {exc}"
            logger.warning("Chart OpenGL unavailable; falling back to CPU: %s", exc)
            return
        self.uses_opengl = True

    def validate_render_backend(self) -> bool:
        """Falls back after show when Qt created a GL viewport without a context."""
        if not self.uses_opengl:
            return True
        viewport = self.widget.viewport()
        context_getter = getattr(viewport, "context", None)
        context = context_getter() if callable(context_getter) else None
        is_valid = bool(
            context is not None
            and (not hasattr(context, "isValid") or context.isValid())
        )
        if is_valid:
            return True

        self.widget.useOpenGL(False)
        self.uses_opengl = False
        self.backend_fallback_reason = "OpenGL context unavailable after show"
        logger.warning(
            "Chart OpenGL viewport has no valid context; falling back to CPU"
        )
        return False

    def set_display_timezone(self, tz_name: str) -> None:
        """Updates display timezone and UTC offset for all date axis items."""
        self._display_timezone = tz_name
        offset = get_utc_offset_seconds(datetime.now(UTC).timestamp(), tz_name)
        for plot in self.plots:
            axis = plot.getAxis("bottom")
            if isinstance(axis, pg.DateAxisItem):
                axis.utcOffset = offset
                axis.picture = None
                axis.update()

    def _update_x_axes(self) -> None:
        """Ensures only the bottom-most plot shows X-axis text labels."""
        for plot in self.plots[:-1]:
            plot.getAxis("bottom").setStyle(showValues=False)
        if self.plots:
            self.plots[-1].getAxis("bottom").setStyle(showValues=True)

    def add_subplot(self, height_ratio: int = 1) -> pg.PlotItem:
        """
        Adds a new subplot row below existing plots (e.g. Volume, RSI, MACD),
        X-linked to the main plot, with its own independent Y auto-scale/zoom
        — same "TradingView style" setup as main_plot (see its __init__
        comment). Without this, a subplot's Y-axis auto-ranges to the FULL
        loaded history instead of the currently visible X window, so a
        single outlier (e.g. one huge volume spike) squashes every other bar
        flat — and mouse-wheel Y-zoom on the subplot silently does nothing.
        """
        utc_offset = get_utc_offset_seconds(
            datetime.now(UTC).timestamp(), self._display_timezone
        )
        date_axis = pg.DateAxisItem(orientation="bottom", utcOffset=utc_offset)
        sub_plot = self.widget.addPlot(
            row=self._next_row,
            col=0,
            colspan=2,
            axisItems={"bottom": date_axis},
        )
        sub_plot.showGrid(x=True, y=True, alpha=0.2)
        sub_plot.setXLink(self.main_plot)
        sub_plot.setMouseEnabled(x=True, y=True)
        sub_plot.vb.setAutoVisible(y=True)
        sub_plot.vb.enableAutoRange(axis="y", enable=True)

        self.widget.ci.layout.setRowStretchFactor(self._next_row, height_ratio)

        self.sub_plots.append(sub_plot)
        self.plots.append(sub_plot)
        self._next_row += 1

        self._update_x_axes()

        return sub_plot

    def remove_subplot(self, sub_plot: pg.PlotItem) -> None:
        """
        @brief Removes a previously-added subplot row entirely, not just the
        curve drawn on it.
        @details add_subplot() always appends a brand new row; without a
        matching removal, repeatedly deregistering and re-registering an
        indicator (e.g. clicking Load History/Start Stream again) leaves the
        old, now-empty subplot row stacked in the layout underneath the new
        one instead of freeing it — the panel duplication itself, distinct
        from (and in addition to) any duplicate curve.
        """
        if sub_plot not in self.sub_plots:
            return
        self.sub_plots.remove(sub_plot)
        self.plots.remove(sub_plot)
        self.widget.removeItem(sub_plot)

        self._update_x_axes()

    def clear(self) -> None:
        self.sub_plots.clear()
        self.plots.clear()
        self.widget.clear()
        self.plots.append(self.main_plot)
        self._update_x_axes()
