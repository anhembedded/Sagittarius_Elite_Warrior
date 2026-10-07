"""`EPIC-034E` — Bots → Mainnet account: the owner's real account, read only.

A window that reads the account once when it opens, off the UI thread, and
says what it found: the key's permissions, what can be spent, the fees, the
open orders and every balance, or why it could not. It has no button that
changes anything, because nothing it reads can be changed from here: the source
behind it is not a trading venue (`EPIC-034E`, D4). Opening it again reads again.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    INotifier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_mainnet_account import (
    GetMainnetAccountQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.connect_words import (
    ACCOUNT_UNREADABLE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.fenced_reads import (
    FencedReads,
    ReadKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.mainnet_account_text import (
    MainnetAccountText,
    account_text,
    error_text,
    failure_text,
    reading_text,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

_LABEL = "mainnet"


class MainnetAccountDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        threads: IThreadManager,
        dispatcher: ICommandDispatcher,
        notifier: INotifier,
    ) -> None:
        super().__init__(parent)
        self._notifier = notifier
        self.setObjectName("dlgMainnetAccount")
        self.setWindowTitle("Mainnet account")
        self._dispatcher = dispatcher
        self.headline = plain_label()
        self.headline.setObjectName("lblMainnetHeadline")
        self.headline.setWordWrap(True)
        self.body = QPlainTextEdit()
        self.body.setObjectName("txtMainnetAccount")
        self.body.setReadOnly(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        column = QVBoxLayout(self)
        column.addWidget(self.headline)
        column.addWidget(self.body, 1)
        column.addWidget(buttons)
        self._reads = FencedReads(threads, {ReadKind.MAINNET: ActionOwnershipTracker()})
        self._reads.answered.connect(self._on_account_read)
        self._reads.failed.connect(self._on_failed)
        self.finished.connect(lambda _result: self._reads.drop_all())
        self._write(reading_text())

    def read(self) -> None:
        """Asks the account; the answer replaces the text when it arrives."""
        dispatcher = self._dispatcher
        query = GetMainnetAccountQuery()
        self._reads.read(
            ReadKind.MAINNET, _LABEL, lambda: dispatcher.dispatch(type(query), query)
        )

    def _on_account_read(self, _kind: ReadKind, _label: str, answer: object) -> None:
        if isinstance(answer, VenueAccountSnapshot):
            self._write(account_text(answer))
        elif isinstance(answer, ConnectFailure):
            self._write(failure_text(answer))
        else:
            raise TypeError(
                f"the mainnet read answers a snapshot or a failure: {answer!r}"
            )

    def _on_failed(self, _kind: ReadKind, _label: str, detail: str) -> None:
        self._write(error_text())
        self._notifier.report_failure(
            FailureNotice(
                FailureKind.COMMAND,
                "bots.mainnet_account",
                ACCOUNT_UNREADABLE,
                detail=detail,
            )
        )

    def _write(self, text: MainnetAccountText) -> None:
        self.headline.setText(text.headline)
        self.body.setPlainText("\n".join(text.lines))


def show_mainnet_account(
    parent: QWidget,
    threads: IThreadManager,
    dispatcher: ICommandDispatcher,
    notifier: INotifier,
) -> None:
    """Opens the window, reading the account as it opens, and waits for Close."""
    dialog = MainnetAccountDialog(parent, threads, dispatcher, notifier)
    dialog.read()
    dialog.exec()
