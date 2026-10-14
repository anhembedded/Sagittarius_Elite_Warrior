"""`BUG-208` — New bot names one kind, "Grid", and lists every venue a kind runs on.

@details The business promise: the kind is "Grid" whatever venue is chosen (the venue says
Spot or Futures, the table's Venue column too), and the Venue list never silently drops a
venue the app trades on: Futures Mainnet is listed, greyed out, with the reason it is closed.
"""

from __future__ import annotations

import concurrent.futures

from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    IBotExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    PROFILE_MARKETS,
    bot_closed_reason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import BotOverlay
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.new_bot_dialog import (
    NewBotDialog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.new_bot_symbols import (
    NewBotSymbols,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.venue_choice import (
    NOT_ENABLED,
    VenueChoice,
    venue_choices,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.kind_panels import kind_title
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_symbol_catalog import (
    FakeSymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_context import (
    VenueContext,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.symbol_picker import SymbolPreferences
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


class _NothingEnabled(IVenueContexts):
    def enabled(self) -> tuple[TradingVenue, ...]:
        return ()

    def get(self, venue: TradingVenue) -> VenueContext:
        raise AssertionError("a venue that is not enabled is not read")

    def primary(self) -> VenueContext:
        raise AssertionError("not used")


class _GridLikeKind(IBotKind):
    @property
    def kind_id(self) -> str:
        return "grid"

    def supported_profiles(self) -> frozenset[MarketType]:
        return PROFILE_MARKETS

    def validate(self, inputs: BotKindInputs) -> tuple[Verdict, ...]:
        raise AssertionError("not judged here")

    def overlay(self, inputs: BotKindInputs) -> BotOverlay:
        raise AssertionError("not drawn here")

    def executor_factory(self) -> IBotExecutorFactory:
        raise AssertionError("not run here")


class _InlinePool(IThreadManager):
    def submit(self, task, *args, **kwargs):  # type: ignore[no-untyped-def]
        task(*args, **kwargs)
        return concurrent.futures.Future()

    def shutdown(self, wait: bool = True) -> None:
        return None


def _choices() -> tuple[VenueChoice, ...]:
    return venue_choices(_NothingEnabled(), [_GridLikeKind()])


def _dialog(qtbot, choices: tuple[VenueChoice, ...]) -> NewBotDialog:
    catalog = FakeSymbolCatalog(["BTCUSDT"], MarketType.SPOT)
    catalog.seed(["BTCUSDT"], MarketType.FUTURES_USD_M)
    symbols = NewBotSymbols(
        catalog, _InlinePool(), SymbolPreferences(), RecordingNotifier()
    )
    dialog = NewBotDialog(["grid"], choices, symbols)
    qtbot.addWidget(dialog)
    return dialog


def test_the_kind_is_grid_whatever_venue_is_chosen(qtbot) -> None:
    dialog = _dialog(qtbot, _choices())

    seen = set()
    for index in range(dialog.venue.count()):
        if dialog.venue.model().flags(dialog.venue.model().index(index, 0)) & (
            Qt.ItemFlag.ItemIsEnabled
        ):
            dialog.venue.setCurrentIndex(index)
            seen.add(dialog.kind.itemText(0))

    assert seen == {"Grid"}
    assert kind_title("grid") == "Grid"


def test_futures_mainnet_is_listed_closed_with_the_reason() -> None:
    by_venue = {choice.venue: choice for choice in _choices()}

    closed = by_venue[TradingVenue.FUTURES_MAINNET]
    assert closed.closed_reason == bot_closed_reason(TradingVenue.FUTURES_MAINNET)
    assert closed.closed_reason
    assert "closed" in closed.option_text
    for venue in (
        TradingVenue.FUTURES_TESTNET,
        TradingVenue.SPOT_TESTNET,
        TradingVenue.SPOT_MAINNET,
    ):
        assert by_venue[venue].closed_reason is None
        assert by_venue[venue].connection == NOT_ENABLED


def test_a_closed_venue_is_listed_last_so_the_preselected_one_can_start() -> None:
    venues = [choice.venue for choice in _choices()]

    assert venues[-1] is TradingVenue.FUTURES_MAINNET


def test_the_dialog_shows_a_closed_venue_greyed_out_with_its_reason(qtbot) -> None:
    dialog = _dialog(qtbot, _choices())

    index = dialog.venue.findData(TradingVenue.FUTURES_MAINNET)
    assert index >= 0
    model = dialog.venue.model()
    item = model.index(index, 0)
    assert not model.flags(item) & Qt.ItemFlag.ItemIsEnabled
    assert model.data(item, Qt.ItemDataRole.ToolTipRole) == bot_closed_reason(
        TradingVenue.FUTURES_MAINNET
    )
    assert dialog.venue.currentIndex() != index
