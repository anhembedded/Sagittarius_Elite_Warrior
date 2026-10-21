"""What the Bots screen's questions answer, for the screen tests (`BotsDialogs`).

Split from `bots_screen_fixtures.py` (the 400-line ceiling): each question the
screen asks is answered from a field, and each records that it was asked.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_dialogs import (
    BotsDialogs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.export_plan_dialog import (
    ExportPlanChoice,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.venue_choice import (
    VenueChoice,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.arm_strategy_dialog import (
    ArmQuestion,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.disarm_choice import (
    VenueQuestion,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass
class Answers:
    """What the screen's questions answer; each records that it was asked."""

    new_bot: CreateBotCommand | None = None
    stop: ExposureHandling | None = None
    delete: bool = False
    #: Bots → Arm strategy…: `True` arms what the form holds.
    arm_strategy: bool = False
    #: The real-money question's answer (`EPIC-034` D3, D11).
    real_money: bool = True
    #: Bots → Export plan… (`BOT-176`): the choice, and the path Save… picks (`""` cancels).
    export_plan: ExportPlanChoice | None = None
    plan_path: str = ""
    asked: list[str] = field(default_factory=list)
    offered: list[str] = field(default_factory=list)

    def dialogs(self) -> BotsDialogs:
        return BotsDialogs(
            ask_new_bot=self._ask_new_bot,
            ask_stop=self._ask_stop,
            confirm_delete=self._confirm_delete,
            ask_arm_strategy=self._ask_arm_strategy,
            choose_venue=self._choose_venue,
            allow_real_money=self._allow_real_money,
            ask_export_plan=self._ask_export_plan,
            ask_plan_save_path=self._ask_plan_save_path,
        )

    def _ask_export_plan(
        self, bots: Sequence[BotSnapshot], selected: BotSnapshot | None
    ) -> ExportPlanChoice | None:
        self.asked.append(
            f"export plan {len(bots)} {selected.bot_id if selected else '-'}"
        )
        return self.export_plan

    def _ask_plan_save_path(self, suggested: str) -> str:
        self.asked.append(f"plan path {suggested}")
        return self.plan_path

    def _allow_real_money(self, venue: TradingVenue, what: str) -> bool:
        self.asked.append(f"real money {venue.value}: {what}")
        return self.real_money

    def _ask_arm_strategy(self, question: ArmQuestion) -> TradingVenue | None:
        venue = next(iter(question.forms))
        self.asked.append(f"arm {venue.value}")
        return venue if self.arm_strategy else None

    def _choose_venue(self, choice: VenueQuestion) -> TradingVenue | None:
        venue = choice.options[0][0]
        self.asked.append(f"disarm {venue.value}")
        return venue

    def _ask_new_bot(
        self, kinds: Sequence[str], venues: Sequence[VenueChoice]
    ) -> CreateBotCommand | None:
        self.asked.append(f"new bot {list(kinds)} {[v.venue.value for v in venues]}")
        #: What each venue was offered with, as the dialog's drop-down shows it.
        self.offered = [venue.option_text for venue in venues]
        return self.new_bot

    def _ask_stop(self, bot: BotSnapshot) -> ExposureHandling | None:
        self.asked.append(f"stop {bot.bot_id}")
        return self.stop

    def _confirm_delete(self, bot: BotSnapshot) -> bool:
        self.asked.append(f"delete {bot.bot_id}")
        return self.delete
