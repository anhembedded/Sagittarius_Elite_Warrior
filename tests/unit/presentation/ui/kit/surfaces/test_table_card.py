"""Tests for `widgets.surfaces.table_card.TableCard`."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Card,
    Column,
    Pagination,
    TableCard,
)

_COLUMNS = (Column("Thời gian", 25), Column("Giá", 18), Column("KL", 14))


def _table(**kwargs) -> TableCard:
    return TableCard("LỊCH SỬ NẾN", _COLUMNS, **kwargs)


def test_is_a_card_carrying_its_columns(qtbot):
    table = _table()
    qtbot.addWidget(table)

    assert isinstance(table, Card)
    assert table.columns == _COLUMNS
    assert table.row_count == 0


def test_rejects_an_empty_column_spec(qtbot):
    with pytest.raises(ValueError, match="at least one column"):
        TableCard("T", [])


def test_header_shows_one_label_per_column(qtbot):
    table = _table()
    qtbot.addWidget(table)

    header = table.body_layout.itemAt(1).widget()
    texts = [label.text() for label in header.findChildren(QLabel)]

    assert texts == ["Thời gian", "Giá", "KL"]


def test_empty_state_swaps_with_the_rows_area(qtbot):
    table = _table(empty_text="Không có dữ liệu nến nào.")
    qtbot.addWidget(table)

    assert table._empty_label.isVisibleTo(table) is True
    assert table._scroll.isVisibleTo(table) is False

    table.add_row(QLabel("row"))

    assert table.row_count == 1
    assert table._empty_label.isVisibleTo(table) is False
    assert table._scroll.isVisibleTo(table) is True


def test_set_rows_replaces_rather_than_appends(qtbot):
    table = _table()
    qtbot.addWidget(table)

    table.set_rows([QLabel("a"), QLabel("b")])
    table.set_rows([QLabel("c")])

    assert table.row_count == 1


def test_clear_rows_keeps_the_trailing_stretch(qtbot):
    table = _table()
    qtbot.addWidget(table)
    table.set_rows([QLabel("a"), QLabel("b")])

    table.clear_rows()

    assert table.row_count == 0
    # One item left, and it is the stretch — not a widget.
    assert table._rows_layout.count() == 1
    assert table._rows_layout.itemAt(0).widget() is None


# ---------------------------------------------------------------------- #
# pagination
# ---------------------------------------------------------------------- #


def test_none_mode_hides_the_pagination_row_entirely(qtbot):
    table = _table(pagination=Pagination.NONE)
    qtbot.addWidget(table)

    assert table._pagination_row.isVisibleTo(table) is False


def test_simple_mode_hides_itself_on_a_single_page(qtbot):
    """Matching the consumer's trade log, which only shows paging once
    there is somewhere to page to."""
    table = _table(pagination=Pagination.SIMPLE)
    qtbot.addWidget(table)

    assert table._pagination_row.isVisibleTo(table) is False

    table.set_page(1, 4)
    assert table._pagination_row.isVisibleTo(table) is True


def test_full_mode_stays_visible_on_a_single_page(qtbot):
    """Matching the consumer's candle inspector — its page-size buttons
    must stay reachable even when everything fits on one page."""
    table = _table(pagination=Pagination.FULL)
    qtbot.addWidget(table)

    assert table._pagination_row.isVisibleTo(table) is True


def test_simple_mode_has_no_first_or_last_button(qtbot):
    table = _table(pagination=Pagination.SIMPLE)
    qtbot.addWidget(table)

    assert not hasattr(table, "first_button")
    assert not hasattr(table, "last_button")
    assert table._page_size_buttons == []


def test_full_mode_offers_page_sizes(qtbot):
    table = _table(pagination=Pagination.FULL, page_sizes=(50, 100))
    qtbot.addWidget(table)

    assert [b.text() for b in table._page_size_buttons] == ["50", "100"]


def test_page_label_defaults_to_a_language_neutral_form(qtbot):
    table = _table(pagination=Pagination.SIMPLE)
    qtbot.addWidget(table)

    table.set_page(2, 7)

    assert table._page_label.text() == "2 / 7"


def test_page_label_can_be_overridden_by_the_consumer(qtbot):
    table = _table(pagination=Pagination.SIMPLE)
    qtbot.addWidget(table)
    table.set_page(2, 7)

    table.set_page_label("Trang 2 / 7")

    assert table._page_label.text() == "Trang 2 / 7"


def test_nav_buttons_disable_at_the_ends(qtbot):
    table = _table(pagination=Pagination.FULL)
    qtbot.addWidget(table)

    table.set_page(1, 3)
    assert table.previous_button.isEnabled() is False
    assert table.first_button.isEnabled() is False
    assert table.next_button.isEnabled() is True

    table.set_page(3, 3)
    assert table.next_button.isEnabled() is False
    assert table.last_button.isEnabled() is False


@pytest.mark.parametrize(
    ("button_name", "expected"),
    [
        ("previous_button", 2),
        ("next_button", 4),
        ("first_button", 1),
        ("last_button", 9),
    ],
)
def test_nav_buttons_request_the_right_page(qtbot, button_name, expected):
    table = _table(pagination=Pagination.FULL)
    qtbot.addWidget(table)
    table.set_page(3, 9)

    with qtbot.waitSignal(table.page_requested, timeout=1000) as blocker:
        getattr(table, button_name).click()

    assert blocker.args == [expected]


def test_page_requests_are_not_clamped(qtbot):
    """Deliberate: what the last page is belongs to whoever owns the data,
    and the three consumers each answer that differently."""
    table = _table(pagination=Pagination.SIMPLE)
    qtbot.addWidget(table)
    table.set_page(1, 1)

    with qtbot.waitSignal(table.page_requested, timeout=1000) as blocker:
        table.previous_button.clicked.emit()

    assert blocker.args == [0]


def test_page_size_buttons_emit_their_size(qtbot):
    table = _table(pagination=Pagination.FULL, page_sizes=(50, 200))
    qtbot.addWidget(table)

    with qtbot.waitSignal(table.page_size_requested, timeout=1000) as blocker:
        table._page_size_buttons[1].click()

    assert blocker.args == [200]


def test_count_text_is_hidden_until_set(qtbot):
    table = _table(pagination=Pagination.FULL)
    qtbot.addWidget(table)

    assert table._count_label.isVisibleTo(table) is False

    table.set_count_text("Hiển thị 1–50 / 1.204")
    assert table._count_label.isVisibleTo(table) is True
