"""`EPIC-029F` — Stop keeps the base unless told otherwise (O3); New bot needs
a typed symbol and an enabled Spot venue, and nothing more (`BOT-150`)."""

from __future__ import annotations

import concurrent.futures
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from PySide6.QtWidgets import QLineEdit, QPushButton
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import FailureKind
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.persistence.json_bot_store import (
    JsonBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot.handler import (
    CreateBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
    BotProgress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FakeBotClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotIdGenerator
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_screen import (
    BOTS_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.new_bot_dialog import (
    CREATE_BUTTON_TEXT,
    NewBotDialog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.new_bot_symbols import (
    NewBotSymbols,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.stop_bot_dialog import (
    STOP_BUTTON_TEXT,
    StopBotDialog,
    stop_question,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_kind_panel import (
    BotKindPanel,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_symbol_catalog import (
    FakeSymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.symbol_picker import (
    SymbolPickerOverlay,
    SymbolPreferences,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

from .bots_screen_fixtures import VENUE, stored

_RUNNING = BotSnapshot.of(stored("a00001", BotLifecycleState.RUNNING).bot)


def test_stop_preselects_keeping_the_base_and_says_orders_are_cancelled(qtbot) -> None:
    dialog = StopBotDialog(_RUNNING)
    qtbot.addWidget(dialog)

    assert dialog.choice() is BaseHandling.KEEP
    assert "cancelled at the exchange" in stop_question(_RUNNING)
    dialog.sell.setChecked(True)
    assert dialog.choice() is BaseHandling.SELL_AT_MARKET
    assert dialog.findChild(QPushButton, "btnConfirmStop").text() == STOP_BUTTON_TEXT


def test_stop_names_the_base_the_run_holds(qtbot) -> None:
    progress = BotProgress(Decimal(0), 0, 0, Decimal("0.0031"), Decimal(64000), "", "")
    holding = replace(_RUNNING, progress=progress)

    assert "It holds 0.0031 BTCUSDT base." in stop_question(holding)
    assert "no base" in stop_question(_RUNNING)


def _symbols(*names: str) -> NewBotSymbols:
    """The picker's list, read by the same coordinator the other screens use,
    on a pool that runs a task where it is submitted."""
    return NewBotSymbols(
        FakeSymbolCatalog(names),
        _InlinePool(),
        SymbolPreferences(),
        RecordingNotifier(),
    )


class _InlinePool(IThreadManager):
    def submit(self, task, *args, **kwargs):  # type: ignore[no-untyped-def]
        task(*args, **kwargs)
        return concurrent.futures.Future()

    def shutdown(self, wait: bool = True) -> None:
        return None


def _pick(dialog: NewBotDialog, symbol: str) -> None:
    """Chooses `symbol` in the shared picker the Symbol button opens."""
    dialog.symbol.click()
    picker = dialog.findChild(SymbolPickerOverlay)
    assert picker is not None, "the Symbol button opens the shared symbol picker"
    picker.symbol_chosen.emit(symbol)


def test_create_waits_for_a_picked_symbol_and_names_what_it_does(qtbot) -> None:
    dialog = NewBotDialog(["grid"], [VENUE], _symbols("BTCUSDT", "ETHUSDT"))
    qtbot.addWidget(dialog)

    assert dialog.create_button.text() == CREATE_BUTTON_TEXT
    assert not dialog.create_button.isEnabled()
    _pick(dialog, "ethusdt")
    assert dialog.create_button.isEnabled()

    command = dialog.command()
    assert (command.kind, command.venue, command.symbol) == ("grid", VENUE, "ETHUSDT")
    assert command.name == "ETHUSDT grid"


def test_the_new_bot_dialog_offers_venue_titles_and_hands_back_the_venue(qtbot) -> None:
    """`EPIC-034A`: the combo reads "Spot Testnet", the command carries the enum."""
    dialog = NewBotDialog(["grid"], [VENUE], _symbols("BTCUSDT"))
    qtbot.addWidget(dialog)

    assert dialog.venue.itemText(0) == VENUE.display_name
    assert TradingVenue(dialog.venue.itemData(0)) is VENUE


def test_new_bot_asks_only_the_minimum_and_saves_no_parameters(qtbot) -> None:
    """`BOT-150` — the user's rule (2026-10-04): creating a bot asks the least;
    its parameters are set afterwards, while it is a draft or stopped."""
    dialog = NewBotDialog(["grid"], [VENUE], _symbols("BTCUSDT"))
    qtbot.addWidget(dialog)
    _pick(dialog, "btcusdt")

    assert dialog.findChild(BotKindPanel) is None
    assert dialog.command().config == {}
    assert "not running" in dialog.parameters_hint.text()


def test_the_new_bot_command_carries_the_venue_enum_and_saves(
    qtbot, tmp_path: Path
) -> None:
    """`BUG-144`. A `str`-based enum stored as a combo's item data comes back
    from Qt as a plain `str`, which compares equal to the member, so the test
    above stayed green while saving the bot crashed on `venue.value`. The
    command is saved through the real handler and store here."""
    dialog = NewBotDialog(["grid"], [VENUE], _symbols("BTCUSDT"))
    qtbot.addWidget(dialog)
    _pick(dialog, "btcusdt")

    command = dialog.command()
    result = CreateBotCommandHandler(
        JsonBotStore(tmp_path), FakeBotClock(), BotIdGenerator()
    ).execute(command)

    assert type(command.venue) is TradingVenue
    assert result.accepted, result.message


def test_the_symbol_is_chosen_in_the_picker_never_typed(qtbot) -> None:
    """`BUG-155` — Symbol was a free-text field ("e.g. BTCUSDT"); it is the
    shared picker the other screens use, listing the Spot catalog."""
    symbols = _symbols("BTCUSDT", "ETHUSDT")
    dialog = NewBotDialog(["grid"], [VENUE], symbols)
    qtbot.addWidget(dialog)

    assert dialog.findChild(QLineEdit, "editNewBotSymbol") is None
    dialog.symbol.click()
    assert dialog.findChild(SymbolPickerOverlay) is not None
    assert list(symbols.catalog_symbols()) == ["BTCUSDT", "ETHUSDT"]
    _pick(dialog, "ETHUSDT")
    assert dialog.symbol.text() == "ETHUSDT"


def test_a_symbol_list_that_cannot_be_read_is_said_not_left_empty(qtbot) -> None:
    """`BOT-169`: the dialog says it in one constant sentence; the bar of the
    Bots mode carries the failure with Retry, and the exception only as detail."""

    class _Down(FakeSymbolCatalog):
        def list_symbols(self, market, *, force_refresh=False):  # type: ignore[no-untyped-def]
            raise ConnectionError("exchange unreachable")

    notifier = RecordingNotifier()
    symbols = NewBotSymbols(_Down(), _InlinePool(), SymbolPreferences(), notifier)
    dialog = NewBotDialog(["grid"], [VENUE], symbols)
    qtbot.addWidget(dialog)
    dialog.show()

    dialog.symbol.click()

    assert not dialog.problem.isHidden()
    assert "unreachable" not in dialog.problem.text()
    notice = notifier.last
    assert notice.kind is FailureKind.BACKGROUND
    assert (notice.scope, notice.cause) == (BOTS_ROUTE, "bots.read.symbols")
    assert "unreachable" not in notice.headline
    assert notice.detail == "exchange unreachable"
    assert notice.retry is not None


def test_the_symbol_list_read_again_from_the_bar_clears_the_failure(qtbot) -> None:
    class _Flaky(FakeSymbolCatalog):
        down = True

        def list_symbols(self, market, *, force_refresh=False):  # type: ignore[no-untyped-def]
            if self.down:
                raise ConnectionError("exchange unreachable")
            return super().list_symbols(market, force_refresh=force_refresh)

    catalog = _Flaky(["BTCUSDT"])
    notifier = RecordingNotifier()
    symbols = NewBotSymbols(catalog, _InlinePool(), SymbolPreferences(), notifier)
    symbols.load_catalog()
    retry = notifier.last.retry
    assert retry is not None
    catalog.down = False

    retry()

    assert list(symbols.catalog_symbols()) == ["BTCUSDT"]
    assert notifier.cleared == ["bots.read.symbols"]
