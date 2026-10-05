"""What this app believes about the live trading session, on Dev Board.

**The first widget a bounded context owns** (`EPIC-025` PR 1.4c-4). Every
screen in the app is still a legacy `View` the shell carries; this panel is not
a screen — it is a `DEV_PROBE` the `trading` module *contributes* to the Dev
Board surface, which is the mechanism the whole epic exists to build, rendering
in a real run for the first time.

@par Why a probe, and why this one
A `dev_probe` answers *what does the engine actually think right now*, next to
the screen where a developer is provoking it. The trading session's three
fields are exactly the state that has been wrong in a way nobody could see: the
session's own `enabled` flag is the gate `EPIC-021G` requires the user to set
every run, `orders_sent_this_session` is the counter a session limit is checked
against, and `known_open_symbols` is the conservative set that blocks a second
order on a symbol — added when an order is *sent*, not when it fills, so a
stale entry silently refuses trades. Three labels answer all three.

@par What it deliberately does not do
It does not touch the network. `ITradingSession.snapshot()` takes the session's
own lock and returns a frozen value — no I/O, safe to call from the UI thread —
while pinging the venue would need a background action, an action identity and
a cancellation path (`async-ui-action-rule.md`). The Exchange API *tester*,
which does ping, is PR 1.5's, with that machinery.

A `QWidget` and nothing more: no `Panel`, no style; the dock the workbench
puts it in supplies the title and the frame. Since `EPIC-033N` its three
fields are the Engine's `ReadoutForm`, written by the application's formatter
like every other read-out.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    APP_VALUE_FORMATTER,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    ReadoutForm,
)

_NO_SYMBOLS = "—"

_FIELDS = (
    ColumnSpec("live_submission", "Live submission", ColumnKind.STATUS),
    ColumnSpec("orders_sent", "Orders sent this session", ColumnKind.QUANTITY),
    ColumnSpec("open_symbols", "Symbols believed open", ColumnKind.TEXT),
)


class TradingSessionProbe(QWidget):  # base-exempt: a container, not a surface
    """@brief The live trading session's three fields, refreshed on request."""

    def __init__(self, session: ITradingSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session = session

        self._fields = ReadoutForm(_FIELDS, APP_VALUE_FORMATTER)
        self._fields.setObjectName("roTradingSessionProbe")

        # A button, not a timer: a probe answers a question the developer just
        # asked, and a panel polling the session forever is a panel whose
        # numbers change while they are being read.
        self._refresh_button = QPushButton("Refresh")
        self._refresh_button.setObjectName("btnProbeRefresh")
        self._refresh_button.clicked.connect(self.refresh)

        layout = QVBoxLayout(self)
        layout.addWidget(self._fields)
        layout.addWidget(self._refresh_button)
        layout.addStretch(1)

        self.refresh()

    def refresh(self) -> None:
        """Reads one snapshot and shows all three fields from it.

        One read, not three: `snapshot()` takes the session's lock once, so the
        three values on screen are a combination that actually existed. Three
        separate reads could show a count from before an order and a symbol set
        from after it (`domain-truth-rule.md`).
        """
        snapshot = self._session.snapshot()
        self._fields.set_values(
            {
                "live_submission": "ON" if snapshot.enabled else "OFF",
                "orders_sent": snapshot.orders_sent_this_session,
                "open_symbols": ", ".join(sorted(snapshot.known_open_symbols))
                or _NO_SYMBOLS,
            }
        )

    def value_text(self, key: str) -> str:
        """What the field `key` shows."""
        return self._fields.value_text(key)
