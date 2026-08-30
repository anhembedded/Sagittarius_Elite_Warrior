"""`EPIC-015`: `TimeframePicker.qml`'s host, rendered for real.

Thin on purpose (`qml-rule.md` §7): `TimeframeVM`'s own rules already have
full coverage with no `QApplication` at all
(`qml/TimeframePicker/tests/test_timeframe_vm.py`), and the standalone
`.qml`'s render/interaction behaviour is already covered with no host at
all (`qml/TimeframePicker/tests/test_timeframe_qml.py`). What only a test
building the real `TimeframePickerDialog` can prove is this app's own
wiring: choosing a card emits `chosen` and closes the dialog with no
separate Apply step, `PinnedTimeframes` round-trips through the VM, a
broken `.qml` fails loudly instead of rendering a blank box, and (`EPIC-015`
Phase 4) the dialog can be built directly around an existing `TimeframeVM`
so it shares state with a sibling `ChartToolbar` instead of building its own.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TimeframePicker.timeframe_picker_dialog import (
    PinnedTimeframes,
    TimeframePickerDialog,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TimeframePicker.timeframe_vm import (
    TimeframeVM,
)


class _Seed:
    """Stand-in for a screen's offered codes + current choice — the two
    `get_*` callables `TimeframePickerDialog` forwards straight into
    `TimeframeVM`."""

    def __init__(self, codes: list[str], current: str) -> None:
        self.codes = codes
        self.current = current


@pytest.fixture
def seed():
    return _Seed(["1m", "5m", "1h", "1d"], "5m")


@pytest.fixture
def pinned():
    return PinnedTimeframes()


@pytest.fixture
def dialog(qapp, seed, pinned):
    built = TimeframePickerDialog.from_callbacks(
        get_codes=lambda: seed.codes,
        get_current=lambda: seed.current,
        get_pinned=pinned.get,
        set_pinned=pinned.set,
    )
    yield built
    built.close()


def test_opening_seeds_the_body_from_the_screens_current_codes(qapp, dialog):
    dialog.open_dialog()
    qapp.processEvents()

    assert dialog._widget_vm.currentCode == "5m"
    codes = {row["code"] for group in dialog._widget_vm.groups for row in group["rows"]}
    assert codes == {"1m", "5m", "1h", "1d"}


def test_choosing_a_code_emits_chosen_and_closes_with_no_apply_step(qapp, dialog):
    received: list[str] = []
    dialog.chosen.connect(received.append)
    dialog.open_dialog()
    qapp.processEvents()

    dialog._widget_vm.choose("1h")
    qapp.processEvents()

    assert received == ["1h"]
    assert not dialog.isVisible()


def test_cancel_closes_without_emitting(qapp, dialog):
    received: list[str] = []
    dialog.chosen.connect(received.append)
    dialog.open_dialog()
    qapp.processEvents()

    dialog.reject()
    qapp.processEvents()

    assert received == []
    assert not dialog.isVisible()


def test_toggling_a_pin_writes_through_pinnedtimeframes(qapp, dialog, pinned):
    dialog.open_dialog()
    qapp.processEvents()

    dialog._widget_vm.togglePinned("1h")
    qapp.processEvents()

    assert pinned.get() == ["1h"]

    dialog._widget_vm.togglePinned("1h")
    qapp.processEvents()

    assert pinned.get() == []


def test_reopening_picks_up_a_changed_current_code(qapp, dialog, seed):
    dialog.open_dialog()
    qapp.processEvents()
    assert dialog._widget_vm.currentCode == "5m"

    seed.current = "1h"
    dialog.open_dialog()
    qapp.processEvents()

    assert dialog._widget_vm.currentCode == "1h"


def test_a_broken_qml_file_raises_instead_of_rendering_a_blank_box(
    qapp, tmp_path, monkeypatch
):
    import Sagittarius_Elite_Warrior.src.presentation.ui.qml.TimeframePicker.timeframe_picker_dialog as host_module

    broken = tmp_path / "Broken.qml"
    broken.write_text("import QtQuick\nItem { this is not qml }\n")
    monkeypatch.setattr(host_module, "_QML", broken)

    with pytest.raises(RuntimeError, match="QML failed to load"):
        host_module.TimeframePickerDialog.from_callbacks(
            get_codes=lambda: ["1m"],
            get_current=lambda: "1m",
            get_pinned=list,
            set_pinned=lambda code, pin: None,
        )


def test_built_around_an_existing_vm_shares_it_verbatim(qapp, seed, pinned):
    """`EPIC-015` Phase 4: `ChartToolbar` builds one `TimeframeVM` for its
    embedded `TimeframeToolbar.qml` and must open this exact dialog on the
    same instance — not a second one wired to the same callbacks, which
    would be two independently-refreshed copies of the pinned set."""
    vm = TimeframeVM(
        get_codes=lambda: seed.codes,
        get_current=lambda: seed.current,
        get_pinned=pinned.get,
        set_pinned=pinned.set,
    )
    vm.refresh()
    built = TimeframePickerDialog(vm)
    try:
        assert built._widget_vm is vm

        vm.togglePinned("1h")

        assert pinned.get() == ["1h"]
    finally:
        built.close()


class TestPinnedTimeframes:
    """Pure logic, no `QApplication` required — the accepted stand-in for a
    real persisted pinned set, see `timeframe_picker_dialog.py`."""

    def test_starts_empty(self) -> None:
        assert PinnedTimeframes().get() == []

    def test_seeds_from_an_initial_iterable(self) -> None:
        """`EPIC-015` Phase 4: `ChartToolbar` seeds this with
        `DEFAULT_TIMEFRAMES` so a freshly-built chart header's pill row is
        not empty on first render."""
        store = PinnedTimeframes(initial=("1h", "1m", "1h"))

        assert store.get() == ["1h", "1m"]

    def test_set_true_pins_and_set_false_unpins(self) -> None:
        store = PinnedTimeframes()
        store.set("1h", True)
        assert store.get() == ["1h"]

        store.set("1h", False)
        assert store.get() == []

    def test_get_is_sorted_and_deduplicated(self) -> None:
        store = PinnedTimeframes()
        store.set("1h", True)
        store.set("1m", True)
        store.set("1h", True)

        assert store.get() == ["1h", "1m"]

    def test_two_instances_do_not_share_state(self) -> None:
        first = PinnedTimeframes()
        second = PinnedTimeframes()

        first.set("1h", True)

        assert second.get() == []
