"""Tests for `widgets.surfaces.tab_bar.TabBar`."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Panel,
    Surface,
    Tab,
    TabBar,
)


def test_is_not_a_surface_and_selects_the_first_tab(qtbot):
    """It used to be a `Panel`, which gave every tab row a card background,
    a border and a radius of its own.

    That contradicted the reasoning already written one level down, where
    `_TabButton` carries `base-exempt: a tab is a button, not a surface` — a
    row of those buttons is not a surface either. An app wanting the row
    framed puts it inside a `Panel`; an app that does not cannot un-frame
    one."""
    bar = TabBar([Tab("trades", "DANH SÁCH LỆNH"), Tab("logs", "NHẬT KÝ")])
    qtbot.addWidget(bar)

    assert not isinstance(bar, Surface)
    assert not isinstance(bar, Panel)
    assert bar.styleSheet() == "", "a tab row must not paint chrome of its own"
    assert bar.current_id == "trades"
    assert bar.current_index == 0


def test_an_empty_bar_has_no_current_tab(qtbot):
    bar = TabBar()
    qtbot.addWidget(bar)

    assert bar.current_id is None
    assert bar.current_index == -1


def test_clicking_emits_index_and_id(qtbot):
    bar = TabBar([Tab("trades", "Lệnh"), Tab("logs", "Nhật ký")])
    qtbot.addWidget(bar)

    with qtbot.waitSignal(bar.tab_selected, timeout=1000) as blocker:
        bar._buttons[1].click()

    assert blocker.args == [1, "logs"]
    assert bar.current_id == "logs"


def test_set_current_id_does_not_emit(qtbot):
    """A programmatic set that emitted would loop straight back through a
    consumer's own sync handler — and the filter row this class also has to
    serve is exactly that shape."""
    bar = TabBar([Tab("a", "A"), Tab("b", "B")])
    qtbot.addWidget(bar)

    with qtbot.assertNotEmitted(bar.tab_selected):
        bar.set_current_id("b")

    assert bar.current_id == "b"
    assert bar.current_index == 1


def test_badges_update_in_place_without_rebuilding(qtbot):
    """The consumer rebuilds every button on every `set_tabs_model` call,
    and calls it on every arriving log line — so a running backtest
    rebuilds the row hundreds of times to change one number."""
    bar = TabBar([Tab("trades", "Lệnh", "0 LỆNH"), Tab("logs", "Nhật ký", "0 EVENTS")])
    qtbot.addWidget(bar)
    buttons_before = list(bar._buttons)

    bar.set_tabs(
        [Tab("trades", "Lệnh", "12 LỆNH"), Tab("logs", "Nhật ký", "340 EVENTS")]
    )

    assert bar._buttons == buttons_before
    assert bar._buttons[1]._badge.text() == "340 EVENTS"


def test_changing_the_ids_does_rebuild(qtbot):
    bar = TabBar([Tab("a", "A")])
    qtbot.addWidget(bar)
    buttons_before = list(bar._buttons)

    bar.set_tabs([Tab("x", "X"), Tab("y", "Y")])

    assert bar._buttons != buttons_before
    assert len(bar._buttons) == 2


def test_selection_survives_an_in_place_badge_refresh(qtbot):
    bar = TabBar([Tab("a", "A", "1"), Tab("b", "B", "2")])
    qtbot.addWidget(bar)
    bar.set_current_id("b")

    bar.set_tabs([Tab("a", "A", "9"), Tab("b", "B", "8")])

    assert bar.current_id == "b"


def test_selection_falls_back_when_its_tab_disappears(qtbot):
    bar = TabBar([Tab("a", "A"), Tab("b", "B")])
    qtbot.addWidget(bar)
    bar.set_current_id("b")

    bar.set_tabs([Tab("a", "A"), Tab("c", "C")])

    assert bar.current_id == "a"


def test_an_empty_badge_is_hidden(qtbot):
    bar = TabBar([Tab("a", "A"), Tab("b", "B", "7")])
    qtbot.addWidget(bar)

    assert bar._buttons[0]._badge.isVisibleTo(bar._buttons[0]) is False
    assert bar._buttons[1]._badge.isVisibleTo(bar._buttons[1]) is True


def test_the_active_tab_renders_differently(qtbot, fake_theme_bridge):
    bar = TabBar([Tab("a", "A"), Tab("b", "B")])
    qtbot.addWidget(bar)

    assert bar._buttons[0].styleSheet() != bar._buttons[1].styleSheet()


def test_a_tab_is_wide_enough_for_its_own_label(qtbot, fake_theme_bridge):
    """BUG-012 regression.

    `QPushButton` sizes itself from its own text and icon. A `_TabButton`
    has neither -- its content is a label and a badge in a child layout,
    which the base class never looks at. It therefore asked for 59x24 while
    its content needed 195x34, and every tab rendered with its label
    clipped to about two characters.

    Asserted against the layout rather than a fixed number, so the check
    still means something when the font or the padding changes.
    """
    bar = TabBar([Tab("trades", "DANH SÁCH LỆNH", "12 LỆNH")])
    qtbot.addWidget(bar)
    button = bar._buttons[0]

    content = button.layout().sizeHint()
    assert button.sizeHint().width() >= content.width()
    assert button.sizeHint().height() >= content.height()
