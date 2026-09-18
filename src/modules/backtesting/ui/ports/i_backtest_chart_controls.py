"""The chart-toolbar contract the Presenter side programs against.

@details `EPIC-013B`. `BacktestChartControls` is a dumb component — it
emits signals and decides nothing — so the Presenter needs exactly four
signals and three methods from it. Declaring those seven keeps
`IBacktestView.chart_controls` from having to be typed `object | None`,
which would have re-introduced the implicit contract this epic exists to
remove.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from PySide6.QtCore import SignalInstance


@runtime_checkable
class IBacktestChartControls(Protocol):
    """
    @brief Chart-area toolbar: the 3-mode switch plus overlay toggles.

    @details **`Protocol`, not an ABC**, under `architecture-rule.md` §2.1
    reason **(a)**: the implementation is a `QWidget`, and `ABCMeta`
    collides with Shiboken's metaclass.

    `is_trade_flags_checked()` exists on the concrete widget but is **not**
    declared here — no Presenter-side caller uses it. Per §1 (I), a port
    states what its consumer needs, not everything its implementation
    happens to offer.
    """

    #: Emits the selected `ChartDisplayMode`'s **value** (a `str`), not the
    #: enum member — `QtCore.Signal(str)` cannot carry a Python enum.
    sig_mode_changed: SignalInstance
    sig_ema_toggled: SignalInstance
    sig_volume_toggled: SignalInstance
    sig_trade_flags_toggled: SignalInstance

    def set_trade_flags_enabled(self, enabled: bool) -> None:
        """Greys the toggle out when the current mode has no price scale."""
        ...

    def set_ema_enabled(self, enabled: bool) -> None: ...

    def is_ema_checked(self) -> bool: ...
