"""`EPIC-028K`/`028L` — what the two desk screens share: the view and the
presenter factories, built for one venue.

@details One factory pair, two routes: the desks differ only in the
`DeskProfile` they are built with (ADR D5). Each route is its own
`<name>_screen.py` building its own `ScreenContribution(route=...)`
(`futures_desk_screen.py`, `spot_desk_screen.py`) — one screen per file, its
route a constant a reader (and `tests/sanity/screen_files.py`) can find
without running anything.

Both routes are always contributed; a venue that is not enabled opens a desk
that says so and holds nothing that could send an order, rather than a route
that is missing from the menu without a word (`DeskView`). Which venues are
enabled is read when the desk's presenter is built, since
`IVenueTradingPorts.get` refuses a venue that is not served; the view itself
reads no service, as no screen's view does.

The views and presenters are imported only when the desk is opened, like
every screen's (`market_screen.py`): `contribute()` runs on every boot, a
headless `sync` included.

Extension cases, each local: a third venue (one `<venue>_desk_screen.py`
calling `desk_factories` with its venue and one line in `module.py`); a desk
built on a `WorkbenchSurface` (`EPIC-028M`, the view factory here only).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

if TYPE_CHECKING:
    from sagittarius_engine.extensions.pyside_mvc import BasePresenter, BaseView
    from sagittarius_engine.interfaces.i_container import IContainer


@dataclass(frozen=True)
class DeskFactories:
    """The two factories a `ScreenContribution` takes, for one venue's desk."""

    view: Callable[[], BaseView]
    presenter: Callable[[BaseView, IContainer], BasePresenter]


def desk_factories(container: IContainer, venue: TradingVenue) -> DeskFactories:
    """The view and presenter factories of `venue`'s desk."""

    def build_view() -> BaseView:
        from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
            desk_profile_for,
        )
        from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_view import (
            DeskView,
        )

        return DeskView(desk_profile_for(venue))

    return DeskFactories(
        view=build_view,
        presenter=lambda view, c: _build_presenter(view, c, venue),
    )


def _build_presenter(
    view: BaseView, container: IContainer, venue: TradingVenue
) -> BasePresenter:
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
        desk_profile_for,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_dependencies import (
        desk_dependencies_for,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_presenter import (
        DeskPresenter,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_view import (
        DeskView,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.disabled_desk_presenter import (
        DisabledDeskPresenter,
    )

    if not isinstance(view, DeskView):
        raise TypeError(f"a desk's presenter was handed a {type(view).__name__}")
    if venue not in container.resolve(IVenueTradingPorts).enabled():
        # The disabled desk holds nothing to drive (`DeskView`).
        view.show_venue_disabled()
        return DisabledDeskPresenter(view, container, venue)
    return DeskPresenter(
        view,
        container,
        desk_profile_for(venue),
        desk_dependencies_for(container, venue),
    )
