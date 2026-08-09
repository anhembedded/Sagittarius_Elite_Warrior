from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer

#: Live stream connection success/failure is signaled asynchronously (see
#: BinanceWebsocketService — start_stream() returns True as soon as the
#: background task is *spawned*, not once actually connected), so there is
#: no direct "connected" callback to await. The first MarketTickEvent is the
#: only reliable proof a real connection succeeded — this fallback window is
#: how long to wait for one before assuming the connection attempt stalled.
_DEFAULT_FALLBACK_SECONDS = 2.0


class AutoStartController(QObject):
    """
    @brief BOT-034 — when the Dev Board opens, immediately attempt Start
    Live; if no MarketTickEvent arrives within `fallback_seconds`, fall back
    to Load History instead of leaving the user staring at an empty chart.

    @details Deliberately does NOT stop the in-flight Start Live attempt on
    fallback — a slow-but-eventually-successful connection still finishes
    and the chart goes live normally the moment the first tick arrives; the
    fallback only covers the *waiting* experience, not stream lifecycle.
    Also deliberately does not retry Start Live automatically afterward
    (decided with the user): a quiet network hiccup shouldn't turn into a
    retry loop the user can't see or stop.

    `begin()` fires at most once per instance — DashboardPresenter creates
    exactly one of these per Dev Board open, so this is really "at most once
    per screen open," matching the intent (auto-start is a first-look
    convenience, not a standing policy re-applied on every reload).
    """

    def __init__(
        self,
        start_stream: Callable[[], None],
        load_history: Callable[[], None],
        fallback_seconds: float = _DEFAULT_FALLBACK_SECONDS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._start_stream = start_stream
        self._load_history = load_history
        self._fallback_ms = int(fallback_seconds * 1000)
        self._timer: QTimer | None = None
        self._began = False

    def begin(self) -> None:
        """Attempts Start Live and arms the fallback window. No-op if
        already called once."""
        if self._began:
            return
        self._began = True

        self._start_stream()

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_fallback_timeout)
        self._timer.start(self._fallback_ms)

    def on_market_tick(self) -> None:
        """Call from the presenter's tick handler — a real tick is proof of
        connection, so the fallback is no longer needed. Safe to call
        repeatedly (e.g. every live tick): a no-op once already cancelled."""
        self._cancel_pending_fallback()

    def shutdown(self) -> None:
        """Stop the pending fallback timer without treating it as a tick.

        For teardown only (app exit / test fixture teardown), not for
        anything resembling "stop on navigate away". Without this, a fallback
        armed by `begin()` that never sees a tick (e.g. every automated test
        that opens the Dev Board, since the mocked dispatcher never produces
        a real MarketTickEvent) keeps ticking after the screen/test that
        created it is gone. When it eventually fires, `_on_fallback_timeout`
        calls back into `load_history` (bound to a presenter whose chart
        widgets may already be destroyed) — a real, reproduced Windows access
        violation, not a hypothetical one. Safe to call repeatedly."""
        self._cancel_pending_fallback()

    def _cancel_pending_fallback(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def _on_fallback_timeout(self) -> None:
        self._timer = None
        self._load_history()
