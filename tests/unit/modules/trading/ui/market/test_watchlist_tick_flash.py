"""`EPIC-043D` — a ticking price takes its direction's tone for a moment, only when asked, and
no timer outlives the table that started it."""

from __future__ import annotations

import shiboken6
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.watchlist_table_model import (
    FLASH_MILLISECONDS,
    WatchlistTableModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.watchlist_tick_flash import (
    follow_tick_flash,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    tone_colour,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.tick_flash_preference import (
    TickFlashPreference,
)

_FOREGROUND = Qt.ItemDataRole.ForegroundRole


class _Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now

    def pass_ms(self, milliseconds: int) -> None:
        self.now += milliseconds / 1000


def _model(qapp, clock: _Clock, *, flash: bool = True) -> WatchlistTableModel:
    model = WatchlistTableModel(clock=clock)
    model.set_symbols(["BTCUSDT", "ETHUSDT"])
    model.set_tick_flash(flash)
    return model


def _price_colour(model: WatchlistTableModel, row: int = 0):
    return model.data(model.index(row, WatchlistTableModel.PRICE_COLUMN), _FOREGROUND)


def _tone(tone: Tone):
    return tone_colour(tone, QGuiApplication.palette())


def test_the_flash_is_off_by_default_and_a_price_never_changes_colour(qapp) -> None:
    clock = _Clock()
    model = _model(qapp, clock, flash=False)

    model.update_tick("BTCUSDT", 100.0, 1.0, 1.0)
    model.update_tick("BTCUSDT", 101.0, 1.0, 1.0)
    model.update_tick("BTCUSDT", 99.0, 1.0, 1.0)

    assert _price_colour(model) is None
    assert not model._flash_timer.isActive()


def test_a_price_that_rises_takes_the_profit_tone_and_one_that_falls_the_loss_tone(
    qapp,
) -> None:
    model = _model(qapp, _Clock())
    model.update_tick("BTCUSDT", 100.0, 0.0, 1.0)
    model.update_tick("ETHUSDT", 100.0, 0.0, 1.0)

    model.update_tick("BTCUSDT", 101.0, 0.0, 1.0)
    model.update_tick("ETHUSDT", 99.0, 0.0, 1.0)

    assert _price_colour(model, 0) == _tone(Tone.POSITIVE)
    assert _price_colour(model, 1) == _tone(Tone.NEGATIVE)


def test_the_first_price_and_an_unchanged_price_say_nothing(qapp) -> None:
    model = _model(qapp, _Clock())

    model.update_tick("BTCUSDT", 100.0, 0.0, 1.0)
    assert _price_colour(model) is None

    model.update_tick("BTCUSDT", 100.0, 0.0, 1.0)
    assert _price_colour(model) is None


def test_the_price_returns_to_the_platform_colour_when_the_flash_is_over(qapp) -> None:
    clock = _Clock()
    model = _model(qapp, clock)
    model.update_tick("BTCUSDT", 100.0, 0.0, 1.0)
    model.update_tick("BTCUSDT", 101.0, 0.0, 1.0)

    clock.pass_ms(FLASH_MILLISECONDS - 1)
    assert _price_colour(model) == _tone(Tone.POSITIVE)

    clock.pass_ms(1)
    assert _price_colour(model) is None


def test_ending_a_flash_repaints_the_price_and_stops_the_timer(qapp) -> None:
    clock = _Clock()
    model = _model(qapp, clock)
    model.update_tick("BTCUSDT", 100.0, 0.0, 1.0)
    model.update_tick("BTCUSDT", 101.0, 0.0, 1.0)
    repainted: list[int] = []
    model.dataChanged.connect(lambda top, _bottom: repainted.append(top.column()))
    assert model._flash_timer.isActive()

    clock.pass_ms(FLASH_MILLISECONDS)
    model._end_flashes()

    assert repainted == [WatchlistTableModel.PRICE_COLUMN]
    assert not model._flash_timer.isActive()


def test_a_second_tick_extends_the_flash_from_that_tick(qapp) -> None:
    clock = _Clock()
    model = _model(qapp, clock)
    model.update_tick("BTCUSDT", 100.0, 0.0, 1.0)
    model.update_tick("BTCUSDT", 101.0, 0.0, 1.0)
    clock.pass_ms(FLASH_MILLISECONDS // 2)

    model.update_tick("BTCUSDT", 99.0, 0.0, 1.0)
    clock.pass_ms(FLASH_MILLISECONDS - 1)

    assert _price_colour(model) == _tone(Tone.NEGATIVE)


def test_turning_the_flash_off_ends_every_flash_and_the_timer_at_once(qapp) -> None:
    model = _model(qapp, _Clock())
    model.update_tick("BTCUSDT", 100.0, 0.0, 1.0)
    model.update_tick("BTCUSDT", 101.0, 0.0, 1.0)
    assert _price_colour(model) == _tone(Tone.POSITIVE)

    model.set_tick_flash(False)

    assert _price_colour(model) is None
    assert not model._flash_timer.isActive()


def test_a_symbol_that_leaves_the_table_takes_its_flash_with_it(qapp) -> None:
    model = _model(qapp, _Clock())
    model.update_tick("BTCUSDT", 100.0, 0.0, 1.0)
    model.update_tick("BTCUSDT", 101.0, 0.0, 1.0)

    model.track(["ETHUSDT"])
    model.track(["BTCUSDT", "ETHUSDT"])

    assert _price_colour(model, 0) is None
    assert not model._flash_timer.isActive()


def test_the_percent_change_column_keeps_its_arrow_beside_a_flashing_price(
    qapp,
) -> None:
    """Colour is never the only signal: the direction is in the text of the next column."""
    model = _model(qapp, _Clock())
    model.update_tick("BTCUSDT", 100.0, 0.0, 1.0)
    model.update_tick("BTCUSDT", 101.0, 1.5, 1.0)

    change = model.data(
        model.index(0, WatchlistTableModel.PERCENT_CHANGE_COLUMN),
        Qt.ItemDataRole.DisplayRole,
    )

    assert change == 1.5
    assert model.data(
        model.index(0, WatchlistTableModel.PERCENT_CHANGE_COLUMN), _FOREGROUND
    ) == _tone(Tone.POSITIVE)


def test_the_timer_is_the_models_child_and_is_gone_with_it(qapp) -> None:
    model = _model(qapp, _Clock())
    model.update_tick("BTCUSDT", 100.0, 0.0, 1.0)
    model.update_tick("BTCUSDT", 101.0, 0.0, 1.0)
    timer = model._flash_timer
    assert timer.parent() is model
    assert timer.isActive()

    shiboken6.delete(model)

    assert not shiboken6.isValid(timer)
    assert isinstance(timer, QTimer)


# -- the mode's wiring: the person's choice reaches the table the presenter built ----------


def _ticked(presenter) -> None:
    watchlist = presenter.view.watchlist
    watchlist.update_tick("BTCUSDT", 100.0, 0.0, 1.0)
    watchlist.update_tick("BTCUSDT", 101.0, 0.0, 1.0)


def test_the_option_turns_the_modes_watchlist_flash_on_and_off(build) -> None:
    preference = TickFlashPreference()
    presenter = build(tick_flash=preference)
    watchlist = presenter.view.watchlist
    _ticked(presenter)
    assert _price_colour(watchlist) is None

    preference.set_enabled(True)
    _ticked(presenter)
    assert _price_colour(watchlist) == _tone(Tone.POSITIVE)

    preference.set_enabled(False)
    assert _price_colour(watchlist) is None


def test_a_mode_built_with_the_option_already_on_flashes_from_the_first_tick(
    build,
) -> None:
    preference = TickFlashPreference()
    preference.set_enabled(True)
    presenter = build(tick_flash=preference)

    _ticked(presenter)

    assert _price_colour(presenter.view.watchlist) == _tone(Tone.POSITIVE)


def test_a_mode_with_no_option_in_its_container_keeps_its_prices_still(build) -> None:
    presenter = build(tick_flash=None)

    _ticked(presenter)

    assert _price_colour(presenter.view.watchlist) is None


def test_a_table_that_is_gone_no_longer_listens_to_the_option(qapp) -> None:
    preference = TickFlashPreference()
    model = WatchlistTableModel()
    follow_tick_flash(model, preference)
    assert len(preference._listeners) == 1

    shiboken6.delete(model)

    assert preference._listeners == []


def test_the_real_timer_ends_a_flash_without_anyone_calling_it(qapp, qtbot) -> None:
    model = WatchlistTableModel()
    model.set_symbols(["BTCUSDT"])
    model.set_tick_flash(True)
    model.update_tick("BTCUSDT", 100.0, 0.0, 1.0)
    model.update_tick("BTCUSDT", 101.0, 0.0, 1.0)
    assert _price_colour(model) == _tone(Tone.POSITIVE)

    qtbot.waitUntil(lambda: not model._flash_timer.isActive(), timeout=3000)

    assert _price_colour(model) is None
    assert model._flashes == {}
