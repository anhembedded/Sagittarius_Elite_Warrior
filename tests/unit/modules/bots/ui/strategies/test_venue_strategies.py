"""`EPIC-033K` stage 3 — a strategy armed on a venue is a row of the Bots
mode, armed and disarmed from the Bots menu, each venue its own.

Driven through `VenueStrategies` and its panel with the strategy module's own
fakes behind the production adapters (`strategy_fakes.py`); the screen-level
wiring is `test_strategy_rows_on_the_bots_screen.py`.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import FailureKind
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.strategy_form_view_model import (
    StrategyFormViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.strategy_rows import (
    ARMED_TEXT,
    NOT_ARMED_TEXT,
    StrategiesPanel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.venue_strategies import (
    VenueStrategies,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.arm_strategy_result import (
    ArmStrategyBlockReason,
    ArmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.armed_strategy_changed_event import (
    ArmedStrategyChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
    TradingSwitchChangedEvent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .strategy_fakes import (
    STRATEGY_KEY,
    Asked,
    Statuses,
    VenueArming,
    venue_strategies,
)

FUTURES = TradingVenue.FUTURES_TESTNET
SPOT = TradingVenue.SPOT_TESTNET


class _Rows:
    def __init__(self, qtbot) -> None:
        self.panel = StrategiesPanel()
        qtbot.addWidget(self.panel)
        self.futures, self.spot = VenueArming(FUTURES), VenueArming(SPOT)
        self.asked, self.statuses = Asked(), Statuses()
        self.notifier = RecordingNotifier()
        self.strategies: VenueStrategies = venue_strategies(
            self.panel,
            (self.futures, self.spot),
            self.asked,
            self.statuses,
            self.notifier,
        )

    def select(self, venue: TradingVenue) -> None:
        assert self.panel.table.select_first(lambda row: row.venue is venue)

    def cell(self, venue: TradingVenue, column: str) -> str:
        model = self.panel.model
        row = next(i for i, r in enumerate(model.rows) if r.venue is venue)
        return self.panel.table.text(row, model.column(column))


@pytest.fixture
def rows(qtbot) -> _Rows:
    return _Rows(qtbot)


def test_each_served_venue_is_a_row_and_nothing_is_armed_at_first(rows) -> None:
    assert [row.venue for row in rows.panel.model.rows] == [FUTURES, SPOT]
    assert rows.cell(SPOT, "state") == NOT_ARMED_TEXT
    assert not rows.strategies.can_arm()  # no row selected yet
    assert not rows.strategies.can_disarm()


def test_arm_asks_for_the_selected_venue_then_arms_it_alone(rows) -> None:
    rows.select(SPOT)
    rows.asked.edit = lambda form: form.request_symbol("ethusdt")

    assert rows.strategies.can_arm()
    rows.strategies.arm_selected()

    assert rows.asked.venues == [SPOT]
    armed_with = rows.spot.arming.armed_with
    assert armed_with is not None
    assert (armed_with.strategy_key, armed_with.symbol) == (STRATEGY_KEY, "ETHUSDT")
    assert rows.futures.arming.armed_with is None
    assert rows.cell(SPOT, "state") == ARMED_TEXT
    assert "ETHUSDT" in rows.cell(SPOT, "strategy")
    assert rows.cell(FUTURES, "state") == NOT_ARMED_TEXT
    assert rows.strategies.can_disarm() and not rows.strategies.can_arm()


def test_cancelling_the_question_arms_nothing(rows) -> None:
    rows.select(FUTURES)
    rows.asked.answer = False

    rows.strategies.arm_selected()

    assert rows.asked.venues == [FUTURES]
    assert rows.futures.arming.armed_with is None
    assert rows.cell(FUTURES, "state") == NOT_ARMED_TEXT


def test_a_refused_arm_is_said_in_words_and_leaves_the_row_unarmed(rows) -> None:
    rows.select(FUTURES)
    rows.futures.arming.script_arm(
        ArmStrategyResult(
            armed=False, block_reason=ArmStrategyBlockReason.TRADING_IS_ENABLED
        )
    )

    rows.strategies.arm_selected()

    notice = rows.notifier.last
    assert notice.kind is FailureKind.COMMAND
    assert "turn off trading" in notice.headline
    assert not any(is_error for _, is_error in rows.statuses)
    assert rows.cell(FUTURES, "state") == NOT_ARMED_TEXT


def test_disarm_disarms_the_selected_venue_only(rows) -> None:
    for venue in (FUTURES, SPOT):
        rows.select(venue)
        rows.strategies.arm_selected()
    rows.select(SPOT)

    rows.strategies.disarm_selected()

    assert rows.spot.arming.disarm_calls == 1
    assert rows.futures.arming.disarm_calls == 0
    assert rows.cell(SPOT, "state") == NOT_ARMED_TEXT
    assert rows.cell(FUTURES, "state") == ARMED_TEXT


def test_a_change_from_elsewhere_is_shown_when_its_event_arrives(rows) -> None:
    """The strategy module's boot restore arms without these rows."""
    rows.futures.armed.seed(
        LiveStrategyConfig(strategy_key=STRATEGY_KEY, symbol="BNBUSDT", interval="1h")
    )

    rows.strategies.on_changed(ArmedStrategyChangedEvent(True, venue=FUTURES))

    assert rows.cell(FUTURES, "state") == ARMED_TEXT
    assert "BNBUSDT 1h" in rows.cell(FUTURES, "strategy")


def test_the_form_opens_on_the_saved_arming_and_never_arms_by_itself(rows) -> None:
    rows.select(SPOT)
    rows.spot.arming.arm(
        LiveStrategyConfig(strategy_key=STRATEGY_KEY, symbol="SOLUSDT", interval="15m")
    )
    rows.spot.arming.armed_with = None
    seen: list[StrategyFormViewModel] = []
    rows.asked.answer = False
    rows.asked.edit = seen.append

    rows.strategies.arm_selected()

    form = seen[0]
    assert (form.selected_symbol, form.live_interval) == ("SOLUSDT", "15m")
    assert form.symbol_options[0] == "SOLUSDT"
    assert rows.spot.arming.armed_with is None


def test_arm_and_disarm_wait_while_the_venue_trades(rows) -> None:
    """PR #376 review: the desks' card locked while trading was on
    (`EPIC-023D`); the session refuses either way, but the commands must
    not offer what it will refuse."""
    rows.select(SPOT)
    rows.spot.trading_on = True
    rows.strategies.on_trading_switched(
        TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=SPOT)
    )

    assert not rows.strategies.can_arm()
    rows.spot.trading_on = False
    rows.strategies.arm_selected()
    rows.spot.trading_on = True
    assert not rows.strategies.can_disarm()

    rows.spot.trading_on = False
    assert rows.strategies.can_disarm()


def test_a_venue_reads_as_a_title_and_the_state_comes_before_the_summary(
    rows,
) -> None:
    columns = [spec.key for spec in rows.panel.model.COLUMNS]

    assert columns.index("state") < columns.index("strategy")
    assert rows.cell(FUTURES, "venue") == "Futures Testnet"
