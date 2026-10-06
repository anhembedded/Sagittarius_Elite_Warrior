"""`EPIC-028K` — a desk's strategy card, wired to its own venue's strategy.

@details The card's behaviour is `StrategyArmingCoordinator`'s, the same one
the Trading screen and the Dev Board drove (both since deleted); what differs
is the arming it is
given. A desk passes its venue's own (`VenueStrategyControls`), so the Spot
desk arms Spot, and the summary line and the chart's strategy lines follow
that venue's armed state. Signals reach the card from the desk's own
`SignalFeed`, which forwards only its venue's (`SignalGeneratedEvent.venue`).
"""

from __future__ import annotations

from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    SUPPORTED_LIVE_INTERVALS,
    ArmedStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_catalog_reader import (
    IStrategyCatalogReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_strategy_controls import (
    VenueStrategyControls,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_chart import (
    DeskChart,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_view_model import (
    DeskViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.signal_feed import SignalFeed
from Sagittarius_Elite_Warrior.src.modules.trading.ui.strategy_arming_coordinator import (
    StrategyArmingCoordinator,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOwnershipTracker,
)

_ARM = "arm_strategy"


class DeskStrategy(QObject):
    """@brief The card's coordinator, bound to one venue's strategy."""

    def __init__(
        self,
        desk: DeskViewModel,
        controls: VenueStrategyControls,
        catalog: IStrategyCatalogReader,
        chart: DeskChart,
    ) -> None:
        """@param chart The desk's chart: what is armed applies to its symbol,
        and its strategy lines follow what is armed. Given at construction,
        so the first restore already draws them (the PR 308 review, D14)."""
        super().__init__(desk)
        self._desk = desk
        self._armed = controls.armed
        self._chart = chart
        self._coordinator = StrategyArmingCoordinator(
            # The card's `@Property`s read as the Qt descriptor to `mypy`,
            # not as the values the coordinator's Protocol names: the same
            # documented false positive as `presenter_factory_trading.py`.
            view_model=desk.strategy_card,  # type: ignore[arg-type]
            catalog=catalog,
            arming=controls.arming,
            get_active_symbol=lambda: chart.shown_symbol,
            get_armed_config=lambda: self._armed.armed().config,
            tracker=ActionOwnershipTracker(),
            arm_action_kind=_ARM,
            set_status=desk.set_status,
            append_log=lambda line: desk.log_model.append(line, level="info"),
            on_armed_changed=self._armed_changed,
        )
        strategy = desk.strategy_card
        strategy.armRequested.connect(self._coordinator.on_arm_clicked)
        strategy.disarmRequested.connect(self._coordinator.on_disarm_clicked)
        strategy.botParamsSaveRequested.connect(self._save_params)
        strategy.strategyConfigChanged.connect(
            self._coordinator.on_strategy_selection_changed
        )
        self._coordinator.restore_into_view_model(list(SUPPORTED_LIVE_INTERVALS))

    def listen(self, signals: SignalFeed) -> None:
        """Shows this venue's strategy signals on the card."""
        signals.signalGenerated.connect(self._coordinator.on_signal_generated)

    def refresh(self) -> None:
        """Shows the venue's armed state as it is now."""
        self._armed_changed(self._armed.armed().config, False)

    def _armed_changed(self, config: ArmedStrategyConfig | None, busy: bool) -> None:
        self._desk.strategy_card.set_armed_summary(
            self._coordinator.armed_summary(config), busy
        )
        self._chart.set_armed_config(config)

    def _save_params(self, values: dict) -> None:
        if self._coordinator.apply_params(values):
            self._desk.set_status("Strategy Parameters saved.", False)
