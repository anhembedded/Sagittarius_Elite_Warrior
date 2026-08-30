"""Thin render tests for `StatCardRow.qml`.

Loads the file directly into a bare `QQuickWidget` with a real
`StatCardRowVM` and a fake `Theme` context, sidestepping
`StatCardRowWidget` (see NOTES.md) — this file only proves the `.qml` loads
and its `Repeater` delegates bind to properties `StatCardRowVM.cards`
actually produces, plus the one `qml-rule.md` §4.2 gotcha worth a real
render check: a `Repeater` over a list-of-dicts model destroys and
recreates every delegate on `cardsChanged`, so a held Python reference to a
delegate goes stale across a `refresh()`.
"""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl
from PySide6.QtGui import QColor
from PySide6.QtQuickWidgets import QQuickWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import Tone
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.StatCardRow.stat_card_row_vm import (
    StatCardRowVM,
)

_QML = Path(__file__).resolve().parents[1] / "StatCardRow.qml"


class _FakeTheme(QObject):
    """Minimal token set this `.qml` (and `kit/StatCard` it composes) reads."""

    @Property(str, constant=True)
    def textPrimary(self) -> str:
        return "#eeeeee"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def muted(self) -> str:
        return "#999999"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def success(self) -> str:
        return "#33cc66"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def danger(self) -> str:
        return "#cc3333"  # token-exempt: fake theme double, not a real Palette value


def _load(qapp, get_cards=None):
    vm = StatCardRowVM(get_cards=get_cards or list)
    vm.refresh()
    theme = _FakeTheme()
    quick = QQuickWidget()
    quick._stat_card_row_vm = vm
    quick._stat_card_row_theme = theme
    quick.rootContext().setContextProperty("vm", vm)
    quick.rootContext().setContextProperty("Theme", theme)
    quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    quick.setSource(QUrl.fromLocalFile(str(_QML)))
    assert quick.status() is QQuickWidget.Status.Ready, quick.errors()
    quick.resize(700, 100)
    quick.show()
    qapp.processEvents()
    return quick, quick.rootObject(), vm


def _cards_data(count: int) -> list[dict[str, object]]:
    return [
        {
            "title": f"Card {i}",
            "value": f"{i}.00",
            "valueTone": Tone.NEUTRAL,
            "suffix": "USD",
            "badgeText": "",
            "badgeTone": Tone.NEUTRAL,
        }
        for i in range(count)
    ]


def test_root_loads_and_names_itself(qapp):
    quick, root, _vm = _load(qapp)

    assert root.objectName() == "statCardRow"
    quick.close()
    quick.deleteLater()


def test_one_delegate_per_card_with_stable_object_names(qapp, qml_item):
    cards = _cards_data(3)
    quick, root, _vm = _load(qapp, get_cards=lambda: cards)

    for index in range(3):
        delegate = qml_item(root, f"cardMetric_{index}")
        assert delegate is not None
        assert delegate.property("value") == f"{index}.00"
    quick.close()
    quick.deleteLater()


def test_delegate_bindings_reach_the_vms_converted_fields(qapp, qml_item):
    cards = [
        {
            "title": "Tổng Lãi/Lỗ (Net PnL)",
            "value": "-8,193.54",
            "valueTone": Tone.NEGATIVE,
            "suffix": "USD",
            "badgeText": "-81.94%",
            "badgeTone": Tone.NEGATIVE,
        }
    ]
    quick, root, _vm = _load(qapp, get_cards=lambda: cards)

    delegate = qml_item(root, "cardMetric_0")
    value_label = qml_item(delegate, "statCardValue")
    badge_label = qml_item(delegate, "statCardBadgeText")

    assert value_label.property("text") == "-8,193.54"
    assert badge_label.property("text") == "-81.94%"
    # The converted `tone`/`badgeTone` strings ("negative", not
    # `Tone.NEGATIVE`) actually drove the colour through to `Theme.danger`
    # — proof the VM's enum-to-string conversion is what `StatCard.qml`
    # reads, not a value it happens to ignore.
    danger = "#cc3333"  # token-exempt: matches _FakeTheme.danger above, not a real Palette value
    assert value_label.property("color") == QColor(danger)
    quick.close()
    quick.deleteLater()


def test_zero_cards_renders_no_delegates(qapp, qml_item):
    quick, root, _vm = _load(qapp, get_cards=list)

    assert qml_item(root, "cardMetric_0") is None
    quick.close()
    quick.deleteLater()


def test_a_refresh_with_new_source_data_reflects_the_new_values(qapp, qml_item):
    """`qml-rule.md` §4.2's guidance ("never hold a delegate reference
    across a refresh, re-look-up after every `cardsChanged`") checked
    against this specific `.qml`: looking the delegate back up by
    `objectName` after `refresh()`, rather than trusting a held reference,
    must see whatever the source now holds — proof `StatCardRowWidget`'s
    own `refresh()` contract (re-pull, don't diff) actually reaches the
    rendered scene."""
    cards = _cards_data(2)
    quick, root, vm = _load(qapp, get_cards=lambda: cards)

    assert qml_item(root, "cardMetric_0").property("value") == "0.00"

    cards[0]["value"] = "999.99"
    vm.refresh()
    qapp.processEvents()

    assert qml_item(root, "cardMetric_0").property("value") == "999.99"
    quick.close()
    quick.deleteLater()
