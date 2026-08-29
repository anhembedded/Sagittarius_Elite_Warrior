"""State and filtering rules for the standalone symbol-picker component."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import Property, QObject, Signal, Slot

from ..abstract.abstract_symbol_picker_vm import AbstractSymbolPickerVM
from ..interfaces.i_symbol_picker_source import ISymbolPickerSource
from .symbol_picker_list_model import SymbolListModel

_QUOTE_ASSETS = (
    "USDT",
    "USDC",
    "FDUSD",
    "TUSD",
    "BUSD",
    "DAI",
    "BTC",
    "ETH",
    "BNB",
    "XRP",
    "SOL",
    "DOGE",
    "TRX",
)
_FIAT_ASSETS = (
    "TRY",
    "EUR",
    "BRL",
    "ARS",
    "IDR",
    "JPY",
    "MXN",
    "PLN",
    "RON",
    "ZAR",
    "CZK",
    "UAH",
    "NGN",
    "COP",
    "AUD",
    "GBP",
    "RUB",
)
_KNOWN_QUOTES = tuple(sorted(set(_QUOTE_ASSETS + _FIAT_ASSETS), key=len, reverse=True))
_FIAT_SET = frozenset(_FIAT_ASSETS)
_ANY_QUOTE = "*"
_FIAT_QUOTE = "FIAT"
_MAX_QUOTE_TABS = 3


class Scope(str, Enum):
    ALL = "all"
    FAVOURITES = "favourites"
    RECENT = "recent"


@dataclass
class _Entry:
    symbol: str
    base: str
    quote: str
    favourite: bool
    recent: bool
    current: bool

    @property
    def is_fiat(self) -> bool:
        return self.quote in _FIAT_SET


def _split_symbol(symbol: str) -> tuple[str, str]:
    upper = symbol.upper()
    for quote in _KNOWN_QUOTES:
        if upper.endswith(quote) and len(upper) > len(quote):
            return upper[: -len(quote)], quote
    return upper, ""


class SymbolPickerVM(AbstractSymbolPickerVM):
    """Pure-QObject state model for ``SymbolPicker.qml``.

    The source is an explicit interface rather than a screen ViewModel. This
    keeps the widget reusable in another Qt application and makes its rules
    testable without a QApplication.
    """

    queryChanged = Signal()
    scopeChanged = Signal()
    quoteChanged = Signal()
    rowsChanged = Signal()
    sectionsChanged = Signal()
    tabsChanged = Signal()
    resultCountChanged = Signal()
    statusChanged = Signal()
    currentChanged = Signal()
    focusChanged = Signal()

    def __init__(
        self,
        source: ISymbolPickerSource,
        parent=None,
    ) -> None:
        super().__init__(parent)
        if not isinstance(source, ISymbolPickerSource):
            raise TypeError("source must implement ISymbolPickerSource")
        self._source = source
        self._query = ""
        self._scope = Scope.ALL
        self._quote = _ANY_QUOTE
        self._favourite_model = SymbolListModel(self)
        self._result_model = SymbolListModel(self)
        self._entries: list[_Entry] = []
        self._rows: list[dict[str, object]] = []
        self._favourite_rows: list[dict[str, object]] = []
        self._result_rows: list[dict[str, object]] = []
        self._scope_tabs: list[dict[str, object]] = []
        self._quote_tabs: list[dict[str, object]] = []
        self._result_count = 0
        self._status = ""
        self._focus_index = -1
        self._current = ""

    @Property(str, notify=queryChanged)
    def query(self) -> str:
        return self._query

    @Property(str, notify=scopeChanged)
    def scope(self) -> str:
        return self._scope.value

    @Property(str, notify=quoteChanged)
    def quote(self) -> str:
        return self._quote

    @Property("QVariantList", notify=rowsChanged)
    def rows(self) -> list[dict[str, object]]:
        return self._rows

    @Property("QVariantList", notify=sectionsChanged)
    def favouriteRows(self) -> list[dict[str, object]]:
        return self._favourite_rows

    @Property("QVariantList", notify=sectionsChanged)
    def resultRows(self) -> list[dict[str, object]]:
        return self._result_rows

    @Property(QObject, constant=True)
    def favouriteModel(self) -> SymbolListModel:
        return self._favourite_model

    @Property(QObject, constant=True)
    def resultModel(self) -> SymbolListModel:
        return self._result_model

    @Property("QVariantList", notify=tabsChanged)
    def scopeTabs(self) -> list[dict[str, object]]:
        return self._scope_tabs

    @Property("QVariantList", notify=tabsChanged)
    def quoteTabs(self) -> list[dict[str, object]]:
        return self._quote_tabs

    @Property(int, notify=resultCountChanged)
    def resultCount(self) -> int:
        return self._result_count

    @Property(str, notify=statusChanged)
    def statusMessage(self) -> str:
        return self._status

    @Property(str, notify=currentChanged)
    def currentSymbol(self) -> str:
        return self._current

    @Property(bool, notify=statusChanged)
    def hasSymbols(self) -> bool:
        return bool(self._entries)

    @Property(bool, notify=statusChanged)
    def hasResults(self) -> bool:
        return bool(self._rows)

    @Property(bool, notify=sectionsChanged)
    def showSplit(self) -> bool:
        return bool(self._favourite_rows) and self._scope is not Scope.FAVOURITES

    @Property(int, notify=focusChanged)
    def focusIndex(self) -> int:
        return self._focus_index

    def refresh(self) -> None:
        favourites = {value.strip().upper() for value in self._source.get_favourites()}
        recents = {value.strip().upper() for value in self._source.get_recents()}
        current = self._source.get_current().strip().upper()
        self._current = current
        self._entries = []
        for raw_symbol in self._source.get_symbols():
            symbol = str(raw_symbol).strip()
            if not symbol:
                continue
            base, quote = _split_symbol(symbol)
            upper = symbol.upper()
            self._entries.append(
                _Entry(
                    symbol=symbol,
                    base=base,
                    quote=quote,
                    favourite=upper in favourites,
                    recent=upper in recents,
                    current=upper == current,
                )
            )
        self._rebuild()
        self.currentChanged.emit()

    @Slot(str)
    def setQuery(self, value: str) -> None:
        value = str(value)
        if value == self._query:
            return
        self._query = value
        self.queryChanged.emit()
        self._rebuild()

    @Slot(str)
    def setScope(self, value: str) -> None:
        try:
            scope = Scope(value)
        except ValueError:
            return
        if scope is self._scope:
            return
        self._scope = scope
        self._focus_index = -1
        self.scopeChanged.emit()
        self._rebuild()

    @Slot(str)
    def setQuote(self, value: str) -> None:
        if value != _ANY_QUOTE and value != _FIAT_QUOTE:
            available = {str(tab["id"]) for tab in self._quote_tabs}
            if value not in available:
                return
        if value == self._quote:
            return
        self._quote = value
        self._focus_index = -1
        self.quoteChanged.emit()
        self._rebuild()

    @Slot(int)
    def moveFocus(self, step: int) -> None:
        if not self._rows:
            return
        self._focus_index = (self._focus_index + int(step)) % len(self._rows)
        for index, row in enumerate(self._rows):
            row["focused"] = index == self._focus_index
        self._favourite_rows = [row for row in self._rows if row["favourite"]]
        self._result_rows = [row for row in self._rows if not row["favourite"]]
        self._sync_models()
        self.rowsChanged.emit()
        self.sectionsChanged.emit()
        self.focusChanged.emit()

    @Slot()
    def chooseFocused(self) -> None:
        if self._rows:
            self.choose(str(self._rows[max(self._focus_index, 0)]["symbol"]))

    @Slot(str)
    def choose(self, symbol: str) -> None:
        if symbol:
            self.symbolChosen.emit(symbol)

    @Slot(str)
    def toggleFavourite(self, symbol: str) -> None:
        normalized = str(symbol).strip().upper()
        entry = next(
            (
                candidate
                for candidate in self._entries
                if candidate.symbol.upper() == normalized
            ),
            None,
        )
        if entry is None:
            return
        entry.favourite = not entry.favourite
        self._source.set_favourite(entry.symbol, entry.favourite)
        self._rebuild()
        self.favouriteToggled.emit(entry.symbol)
        self.favouriteChanged.emit(entry.symbol, entry.favourite)

    @Slot()
    def reset(self) -> None:
        self._query = ""
        self._scope = Scope.ALL
        self._quote = _ANY_QUOTE
        self._focus_index = -1
        self.refresh()
        self.queryChanged.emit()
        self.scopeChanged.emit()
        self.quoteChanged.emit()

    def _rebuild(self) -> None:
        needle = self._query.strip().upper()
        visible = [entry for entry in self._entries if self._matches(entry, needle)]
        self._rows = [self._row(entry) for entry in visible]
        self._favourite_rows = [row for row in self._rows if row["favourite"]]
        self._result_rows = [row for row in self._rows if not row["favourite"]]
        self._sync_models()
        self._result_count = len(self._rows)
        self._status = (
            "Đang tải danh sách symbol từ sàn..."
            if not self._entries
            else "Không có symbol nào khớp bộ lọc hiện tại."
            if not self._rows
            else ""
        )
        self._scope_tabs = self._build_scope_tabs()
        self._quote_tabs = self._build_quote_tabs()
        self.rowsChanged.emit()
        self.sectionsChanged.emit()
        self.tabsChanged.emit()
        self.resultCountChanged.emit()
        self.statusChanged.emit()
        self.focusChanged.emit()

    def _sync_models(self) -> None:
        self._favourite_model.set_rows(self._favourite_rows)
        result_rows = (
            self._result_rows
            if self._favourite_rows and self._scope is not Scope.FAVOURITES
            else self._rows
        )
        self._result_model.set_rows(result_rows)

    def _matches(self, entry: _Entry, needle: str) -> bool:
        if self._scope is Scope.FAVOURITES and not entry.favourite:
            return False
        if self._scope is Scope.RECENT and not entry.recent:
            return False
        if self._quote != _ANY_QUOTE:
            if self._quote == _FIAT_QUOTE and not entry.is_fiat:
                return False
            if self._quote != _FIAT_QUOTE and entry.quote != self._quote:
                return False
        return not needle or needle in entry.symbol.upper()

    def _row(self, entry: _Entry) -> dict[str, object]:
        if entry.current:
            subtitle = "Đang dùng"
        elif entry.recent:
            subtitle = "Gần đây"
        elif entry.quote:
            subtitle = f"Quote {entry.quote}"
        else:
            subtitle = "—"
        return {
            "symbol": entry.symbol,
            "base": entry.base,
            "quote": entry.quote,
            "subtitle": subtitle,
            "favourite": entry.favourite,
            "current": entry.current,
            "focused": False,
        }

    def _build_scope_tabs(self) -> list[dict[str, object]]:
        favourite_count = sum(entry.favourite for entry in self._entries)
        return [
            {
                "id": scope.value,
                "label": label,
                "badge": str(favourite_count)
                if scope is Scope.FAVOURITES and favourite_count
                else "",
                "selected": scope is self._scope,
            }
            for scope, label in (
                (Scope.ALL, "Tất cả"),
                (Scope.FAVOURITES, "Yêu thích"),
                (Scope.RECENT, "Gần đây"),
            )
        ]

    def _build_quote_tabs(self) -> list[dict[str, object]]:
        counts: dict[str, int] = {}
        has_fiat = False
        for entry in self._entries:
            if entry.is_fiat:
                has_fiat = True
            elif entry.quote:
                counts[entry.quote] = counts.get(entry.quote, 0) + 1
        quotes = sorted(counts, key=lambda item: (-counts[item], item))[
            :_MAX_QUOTE_TABS
        ]
        if has_fiat:
            quotes.append(_FIAT_QUOTE)
        values = [_ANY_QUOTE] + quotes
        if self._quote not in values:
            self._quote = _ANY_QUOTE
        return [
            {
                "id": value,
                "label": "Tất cả" if value == _ANY_QUOTE else value,
                "selected": value == self._quote,
            }
            for value in values
        ]
