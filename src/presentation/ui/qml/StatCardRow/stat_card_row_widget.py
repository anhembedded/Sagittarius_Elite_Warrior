"""Embeds `StatCardRow.qml` inline in `BackTestTopPanel`'s own layout — the
dynamic row of primary performance stat cards
(`BackTestViewModel.primaryStatCards`), replacing per-run construction/
teardown of the QtWidgets `StatCard` (`kit/surfaces/stat_card.py`).

@par Why a bare `QQuickWidget`, not `QmlOverlay`
Same reasoning `qml/kit/progress_banner_widget.py` documents for its own
host: this row is not a dialog, it sits inside `BackTestTopPanel`'s own
`QVBoxLayout` in the exact spot the old `QHBoxLayout` of `StatCard` widgets
occupied — `qml-rule.md` §0's two "Modal QML" host shapes both assume a
`QDialog`, which nothing here needs.

@par Why this needs a widget VM, unlike `ProgressBannerWidget`
`ProgressBannerWidget` has no VM because every value it sets is already the
exact value the screen ViewModel computed. This host cannot make the same
claim: `BackTestViewModel.primaryStatCards` carries raw `Tone` enum members
(`valueTone`/`badgeTone`), and QML reads plain data, not a Python `Enum` —
see `stat_card_row_vm.py` for the one conversion this widget needs.

@par Why callback-constructed
Same pattern `qml-rule.md` §1.1 documents for every widget ViewModel in
this rollout (`SelectListVM(get_options=..., ...)`) — the constructor takes
a `get_cards` callback rather than a `BackTestViewModel` reference, so this
widget stays testable and reusable without importing anything from
`screens/backtest/` (`qml/` must not depend on `screens/` — the reverse
dependency `backtest_top_panel.py` already has is the one direction this
rollout uses throughout, enforced since `EPIC-021L`/`BUG-082` by
`test_qml_library_does_not_import_screens.py`, not merely a convention
stated here).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import StyleRole

from ..embed import QuickSurface
from .stat_card_row_vm import StatCardRowVM

_QML_FILE = Path(__file__).with_name("StatCardRow.qml")


class StatCardRowWidget(QuickSurface):
    """@brief Inline (non-modal) host for `StatCardRow.qml`.

    @details `refresh()` re-pulls `get_cards()` and re-converts every card
    into QML-ready data (`StatCardRowVM.refresh()`). Callers decide *when*
    to call it (`BackTestTopPanel._sync_stat_cards()` calls it once per
    `statCardsChanged` emission) — this class does not also subscribe to
    anything on its own, so there is exactly one place that decides the
    refresh cadence.
    """

    def __init__(
        self,
        get_cards: Callable[[], Sequence[Mapping[str, object]]],
        parent: QWidget | None = None,
    ) -> None:
        # Built before the scene loads — the context is handed to
        # `QuickSurface` at construction; parented right after, so its
        # lifetime is this widget's (BUG-115: the gaps between cards used to
        # render black on a real screen — the row now clears to the SURFACE
        # token `BackTestTopPanel`'s card paints).
        vm = StatCardRowVM(get_cards)
        super().__init__(
            _QML_FILE,
            surface=StyleRole.SURFACE,
            context={"vm": vm},
            object_name="statCardRowQuick",
            parent=parent,
        )
        self.setObjectName("statCardRowWidget")
        vm.setParent(self)
        self._vm = vm
        self._root = self.root_object
        self.refresh()

    def refresh(self) -> None:
        """Re-pulls `get_cards()` and rebuilds every `StatCard` delegate.

        `qml-rule.md` §4.2: a `Repeater` over a list-of-dicts model
        destroys and recreates every delegate on any change — see
        `NOTES.md` for how often this actually fires during a live
        Backtest run (an event, not a per-tick rebuild)."""
        self._vm.refresh()
