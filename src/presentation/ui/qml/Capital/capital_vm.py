"""State and rules behind `Capital.qml`. No Qt GUI, no QML import."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import Property, QObject, Signal, Slot


class CapitalVM(QObject):
    """
    @brief The initial-capital form: an amount, a currency, and whether the
    pair is currently applicable.

    @details Deliberately the pilot for the *form* shape, because this is the
    exact shape `BUG-064` was about — a field whose value has to reach the
    screen, and a validation result that has to reach a button's enabled
    state. In QML both directions are declarations; the widget version needed
    `textChanged`/`capitalValidationMessageChanged` wired by hand and a
    `_sync_validation` method to keep them consistent.

    Validation itself is **not** here: it belongs to the presenter, which
    already owns it. This holds the *answer* and derives `canApply` from it,
    which is the part a test can pin without a running backtest engine.
    """

    textChanged = Signal()
    currencyChanged = Signal()
    validationChanged = Signal()
    #: (amount text, currency) — the screen decides what applying means.
    applied = Signal(str, str)
    #: Emitted whenever the amount changes, so the screen can re-validate.
    validationRequested = Signal(str)

    def __init__(
        self,
        currencies: Sequence[str],
        get_text: Callable[[], str],
        get_currency: Callable[[], str],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._currencies = [str(c) for c in currencies]
        self._get_text = get_text
        self._get_currency = get_currency
        self._text = ""
        self._currency = ""
        self._message = ""

    # -- Reading ---------------------------------------------------------- #

    @Property("QStringList", constant=True)
    def currencies(self) -> list[str]:
        return list(self._currencies)

    def _get_text_prop(self) -> str:
        return self._text

    def _set_text(self, value: str) -> None:
        if value != self._text:
            self._text = value
            self.textChanged.emit()
            self.validationRequested.emit(value)

    text = Property(str, _get_text_prop, _set_text, notify=textChanged)

    def _get_currency_prop(self) -> str:
        return self._currency

    def _set_currency(self, value: str) -> None:
        if value != self._currency:
            self._currency = value
            self.currencyChanged.emit()

    currency = Property(str, _get_currency_prop, _set_currency, notify=currencyChanged)

    @Property(str, notify=validationChanged)
    def validationMessage(self) -> str:
        return self._message

    @Property(bool, notify=validationChanged)
    def canApply(self) -> bool:
        """Derived, not stored. The widget version kept this in
        `_btn_apply.setEnabled(not message)` inside a sync method — one more
        place for the two to disagree."""
        return not self._message

    # -- Writing ---------------------------------------------------------- #

    @Slot(str)
    def setValidationMessage(self, message: str) -> None:
        """The presenter's verdict, arriving asynchronously."""
        if message != self._message:
            self._message = message
            self.validationChanged.emit()

    def refresh(self) -> None:
        """Re-reads the screen's current values. Called on every open: the
        dialog is built once and reused."""
        self._set_text(self._get_text())
        self._set_currency(self._get_currency())

    @Slot()
    def apply(self) -> None:
        """No-ops while invalid rather than trusting QML to have disabled the
        button — a rule enforced only by a `enabled:` binding is a rule that
        stops existing the moment someone edits the `.qml`."""
        if self.canApply:
            self.applied.emit(self._text, self._currency)
