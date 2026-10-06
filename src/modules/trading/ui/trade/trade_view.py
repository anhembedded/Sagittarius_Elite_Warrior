"""The Trade mode's view (`EPIC-033I`): one page per enabled venue, one shown.

Each venue's page (`DeskView`) is a workbench surface of its own, laid out as
HLD §11.2.1 lists the mode: the chart central, Order entry and Account
summary right, the account's tables and Equity at the bottom. The view shows
the page of the venue chosen (Trade → Venue, `venue_choice.py`); the mode's
host asks it which surfaces it has and which shows (`ISurfaceStack`), so
View lists the shown venue's panels and each venue's layout is remembered
apart.

The mode's log is one channel of the Output pane, every venue's lines in it,
each naming its venue (`DeskViewModel.write_log`); with no venue enabled there is
no channel.

With no venue enabled the view says so and where to turn one on, and holds
nothing that could send an order. The notice sits on a surface of the mode's
places like a venue's page, so the window's environment banner shows above
it as above every surface; it has no panels and no layout to remember.

Stock controls, no style sheet (`ui-presentation-rule.md` §1); the view only
shows, the presenter decides.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tab_confirmations import (
    AccountTabConfirmations,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    DeskProfile,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_view import (
    TRADE_SURFACE,
    DeskView,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.empty_page import empty_page
from Sagittarius_Elite_Warrior.src.support.ui_kit.output_source_view import (
    OutputSourceView,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.verb_confirmation import (
    VerbQuestion,
    ask_with_verbs,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.workbench_surface import (
    WorkbenchSurface,
)
from sagittarius_engine.extensions.pyside_mvc import LogListModel
from sagittarius_engine.extensions.pyside_mvc.runtime.region_host import RegionHost
from sagittarius_engine.extensions.pyside_mvc.workbench.output_pane import (
    OutputChannel,
)

NO_VENUE_TEXT = (
    "No trading venue is enabled. Turn one on in Tools → Options → Trading, "
    "then restart the app."
)


class TradeView(OutputSourceView):
    """@brief The venues' pages, one shown; an `ISurfaceStack`."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.log = LogListModel(self)
        self._pages: dict[TradingVenue, DeskView] = {}
        self._no_venue = empty_page(NO_VENUE_TEXT, "lblNoVenue")
        self._idle = WorkbenchSurface(TRADE_SURFACE)
        self._idle.place_widget(Place.WORKSPACE, self._no_venue)
        self._stack = QStackedWidget()
        self._stack.setObjectName("stkTradeVenues")
        self._stack.addWidget(self._idle)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._stack)

    def add_venue(
        self,
        profile: DeskProfile,
        confirmations: AccountTabConfirmations | None = None,
    ) -> DeskView:
        """A page for `profile`'s venue, writing to the mode's log; the
        presenter fills it. The first page added shows until another is
        chosen."""
        page = DeskView(profile, log=self.log, confirmations=confirmations)
        self._pages[profile.venue] = page
        # The log is a channel once a venue writes to it; with none enabled
        # the mode offers none, as the desks of a disabled venue did not.
        self._output = OutputChannel("trade", "Trade", self.log)
        self._stack.addWidget(page)
        if len(self._pages) == 1:
            self._stack.setCurrentWidget(page)
        return page

    def show_venue(self, venue: TradingVenue) -> None:
        """Shows `venue`'s page; a venue with no page changes nothing."""
        page = self._pages.get(venue)
        if page is not None:
            self._stack.setCurrentWidget(page)

    def venue_page(self, venue: TradingVenue) -> DeskView:
        return self._pages[venue]

    @property
    def shown_venue(self) -> TradingVenue | None:
        shown = self._stack.currentWidget()
        return next((v for v, page in self._pages.items() if page is shown), None)

    def ask_to_enable(self, venue_title: str) -> bool:
        """Trade → Enable live trading, turning trading on: asked with its
        verbs, Keep it off the default (HLD §11.2.3, `ui-presentation-rule.md`
        §10)."""
        return ask_with_verbs(
            self,
            VerbQuestion(
                title="Enable Live Trading",
                question=f"Turn on live trading on {venue_title} Testnet?",
                act="Enable trading",
                keep="Keep it off",
                details=(
                    "Orders placed from now on, by hand or by an armed "
                    "strategy, are sent to the exchange."
                ),
            ),
        )

    # -- ISurfaceStack (structural) --------------------------------------------

    def surfaces(self) -> Sequence[RegionHost]:
        return tuple(page.surface for page in self._pages.values())

    def shown_surface(self) -> RegionHost | None:
        venue = self.shown_venue
        return self._pages[venue].surface if venue is not None else None
