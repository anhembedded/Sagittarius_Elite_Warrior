"""No-GUI tests for the standalone SymbolPickerVM."""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101, PLR2004

from __future__ import annotations

from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.presentation.ui.qml.interfaces.i_symbol_picker_source import (
    ISymbolPickerSource,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.SymbolPicker.symbol_picker_vm import (
    SymbolPickerVM,
)


class _Source(ISymbolPickerSource):
    def __init__(
        self,
        symbols: Sequence[str] = ("ETHUSDT", "ETHBTC", "ETHEUR", "AAVEETH"),
        favourites: Sequence[str] = ("ETHBTC",),
        recents: Sequence[str] = ("ETHEUR",),
        current: str = "ETHUSDT",
    ) -> None:
        self.symbols = list(symbols)
        self.favourites = list(favourites)
        self.recents = list(recents)
        self.current = current

    def get_symbols(self) -> Sequence[str]:
        return self.symbols

    def get_favourites(self) -> Sequence[str]:
        return self.favourites

    def get_recents(self) -> Sequence[str]:
        return self.recents

    def get_current(self) -> str:
        return self.current

    def set_favourite(self, symbol: str, favourite: bool) -> None:
        normalized = symbol.strip().upper()
        if favourite:
            if normalized not in self.favourites:
                self.favourites.append(normalized)
        elif normalized in self.favourites:
            self.favourites.remove(normalized)


def _vm(source: _Source | None = None) -> SymbolPickerVM:
    vm = SymbolPickerVM(source or _Source())
    vm.refresh()
    return vm


def test_the_abstract_vm_cannot_be_instantiated():
    from Sagittarius_Elite_Warrior.src.presentation.ui.qml.abstract.abstract_symbol_picker_vm import (
        AbstractSymbolPickerVM,
    )

    try:
        AbstractSymbolPickerVM()
    except TypeError as error:
        assert "abstract" in str(error)
    else:  # pragma: no cover - protects the abstract contract
        raise AssertionError("abstract VM was instantiated")


def test_refresh_builds_split_symbol_rows_and_status():
    vm = _vm()

    assert [row["symbol"] for row in vm.rows] == [
        "ETHUSDT",
        "ETHBTC",
        "ETHEUR",
        "AAVEETH",
    ]
    assert vm.rows[0]["base"] == "ETH"
    assert vm.rows[0]["quote"] == "USDT"
    assert vm.rows[0]["subtitle"] == "Đang dùng"
    assert vm.rows[2]["subtitle"] == "Gần đây"
    assert vm.resultCount == 4
    assert vm.statusMessage == ""


def test_search_is_case_insensitive_and_updates_count():
    vm = _vm()
    vm.setQuery("eth")

    assert [row["symbol"] for row in vm.rows] == [
        "ETHUSDT",
        "ETHBTC",
        "ETHEUR",
        "AAVEETH",
    ]
    vm.setQuery("btc")
    assert [row["symbol"] for row in vm.rows] == ["ETHBTC"]
    assert vm.resultCount == 1


def test_scope_and_quote_filters_are_anded():
    vm = _vm()
    vm.setScope("favourites")
    vm.setQuote("BTC")

    assert [row["symbol"] for row in vm.rows] == ["ETHBTC"]
    assert vm.scopeTabs[1]["selected"] is True
    assert next(tab for tab in vm.quoteTabs if tab["id"] == "BTC")["selected"] is True


def test_favourites_are_split_from_other_results():
    vm = _vm()

    assert [row["symbol"] for row in vm.favouriteRows] == ["ETHBTC"]
    assert [row["symbol"] for row in vm.resultRows] == [
        "ETHUSDT",
        "ETHEUR",
        "AAVEETH",
    ]
    assert vm.showSplit is True


def test_no_symbols_and_no_match_have_distinct_statuses():
    empty = _vm(_Source(symbols=()))
    assert empty.hasSymbols is False
    assert "Đang tải" in empty.statusMessage

    no_match = _vm()
    no_match.setQuery("ZZZ")
    assert no_match.hasSymbols is True
    assert no_match.hasResults is False
    assert "Không có symbol" in no_match.statusMessage


def test_choice_and_favourite_emit_host_commands_and_update_local_state():
    source = _Source()
    vm = _vm(source)
    chosen: list[str] = []
    starred: list[str] = []
    states: list[tuple[str, bool]] = []
    vm.symbolChosen.connect(chosen.append)
    vm.favouriteToggled.connect(starred.append)
    vm.favouriteChanged.connect(lambda symbol, state: states.append((symbol, state)))

    vm.choose("ETHBTC")
    vm.toggleFavourite("ETHBTC")

    assert chosen == ["ETHBTC"]
    assert starred == ["ETHBTC"]
    assert states == [("ETHBTC", False)]
    assert vm.favouriteRows == []
    assert vm.resultRows[1]["symbol"] == "ETHBTC"
    assert source.favourites == []  # the toggle wrote back to the source too


def test_favourite_toggle_writes_through_to_the_source():
    source = _Source(favourites=())
    vm = _vm(source)

    vm.toggleFavourite("ETHEUR")

    assert source.favourites == ["ETHEUR"]

    vm.toggleFavourite("ETHEUR")

    assert source.favourites == []


def test_keyboard_focus_wraps_and_choose_uses_the_focused_row():
    vm = _vm()
    chosen: list[str] = []
    vm.symbolChosen.connect(chosen.append)

    vm.moveFocus(1)
    vm.moveFocus(1)
    vm.chooseFocused()

    assert vm.focusIndex == 1
    assert chosen == ["ETHBTC"]
    assert vm.rows[1]["focused"] is True


def test_reset_restores_the_initial_filters():
    vm = _vm()
    vm.setQuery("btc")
    vm.setScope("favourites")
    vm.setQuote("BTC")
    vm.reset()

    assert vm.query == ""
    assert vm.scope == "all"
    assert vm.quote == "*"
    assert vm.resultCount == 4


def test_models_handle_1000_symbols_without_copying_into_qml_lists():
    symbols = tuple(f"COIN{index}USDT" for index in range(1000))
    vm = _vm(_Source(symbols=symbols, favourites=symbols[:3]))

    assert vm.resultCount == 1000
    assert vm.favouriteModel is not vm.resultModel
    assert vm.favouriteModel.rowCount() == 3
    assert vm.resultModel.rowCount() == 997

    vm.setQuery("COIN999")
    assert vm.resultCount == 1
    assert vm.resultModel.rowCount() == 1
