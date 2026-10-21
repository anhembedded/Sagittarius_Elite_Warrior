"""`EPIC-033K` stage 3, `BOT-219` — a strategy is armed on a venue and disarmed from the Bots menu,
each venue its own, with no panel: Arm strategy… asks what to arm and where, Disarm strategy…
asks which armed venue unless one is armed, and what was armed is told in the Output pane.

Driven through `VenueStrategies` with the strategy module's own fakes behind the production
adapters (`strategy_fakes.py`); the screen-level wiring is
`test_strategy_commands_on_the_bots_screen.py`.
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .strategy_fakes import (
    STRATEGY_KEY,
    Asked,
    Chose,
    Statuses,
    Told,
    VenueArming,
    venue_strategies,
)

FUTURES = TradingVenue.FUTURES_TESTNET
SPOT = TradingVenue.SPOT_TESTNET


class _World:
    def __init__(self) -> None:
        self.futures, self.spot = VenueArming(FUTURES), VenueArming(SPOT)
        self.asked, self.chose, self.told = Asked(), Chose(), Told()
        self.statuses = Statuses()
        self.notifier = RecordingNotifier()
        self.strategies: VenueStrategies = venue_strategies(
            (self.futures, self.spot),
            self.asked,
            self.statuses,
            self.notifier,
            self.chose,
            self.told,
        )

    def arm(self, venue: TradingVenue) -> None:
        self.asked.venue = venue
        self.strategies.arm()


@pytest.fixture
def world(qapp) -> _World:
    return _World()


def test_with_nothing_armed_arm_is_offered_and_disarm_is_not(world) -> None:
    assert world.strategies.can_arm()
    assert not world.strategies.can_disarm()
    assert world.strategies.armed_lines() == ()


def test_arm_asks_what_and_where_then_arms_that_venue_alone(world) -> None:
    world.asked.venue = SPOT
    world.asked.edit = lambda form: form.request_symbol("ethusdt")

    world.strategies.arm()

    assert world.asked.offered == [FUTURES, SPOT]
    armed_with = world.spot.arming.armed_with
    assert armed_with is not None
    assert (armed_with.strategy_key, armed_with.symbol) == (STRATEGY_KEY, "ETHUSDT")
    assert world.futures.arming.armed_with is None
    assert world.strategies.can_disarm()
    assert world.strategies.can_arm()  # Futures has nothing armed yet


def test_a_venue_that_is_armed_is_not_offered_to_arm_again(world) -> None:
    world.arm(SPOT)

    world.arm(FUTURES)

    assert world.asked.questions[-1].forms.keys() == {FUTURES}
    assert not world.strategies.can_arm()  # both are armed now


def test_the_arm_question_lists_what_is_armed_already(world) -> None:
    world.arm(FUTURES)
    world.asked.venue = None

    world.strategies.arm()

    (line,) = world.asked.questions[-1].armed_now
    assert line.startswith("Futures Testnet: ") and "BTCUSDT" in line


def test_cancelling_the_question_arms_nothing(world) -> None:
    world.asked.cancel = True

    world.strategies.arm()

    assert world.asked.offered == [FUTURES, SPOT]
    assert world.futures.arming.armed_with is None
    assert world.spot.arming.armed_with is None
    assert world.told == []


def test_a_venue_armed_while_the_questions_were_open_is_not_armed_again(world) -> None:
    """The dialog and the real-money question run nested event loops: an arm from elsewhere can
    land in them, and the answer then names a venue that is no longer free."""
    world.asked.venue = FUTURES

    def armed_meanwhile(_form: StrategyFormViewModel) -> None:
        world.futures.armed.seed(
            LiveStrategyConfig(
                strategy_key=STRATEGY_KEY, symbol="BNBUSDT", interval="1h"
            )
        )

    world.asked.edit = armed_meanwhile

    world.strategies.arm()

    assert world.futures.arming.armed_with is None


def test_a_refused_arm_is_said_in_words_and_arms_nothing(world) -> None:
    world.futures.arming.script_arm(
        ArmStrategyResult(
            armed=False,
            block_reason=ArmStrategyBlockReason.POSITION_OPEN,
        )
    )

    world.arm(FUTURES)

    notice = world.notifier.last
    assert notice.kind is FailureKind.COMMAND
    assert "position is open" in notice.headline
    assert world.strategies.armed_lines() == ()


def test_with_one_venue_armed_disarm_acts_on_it_without_asking(world) -> None:
    world.arm(FUTURES)

    world.strategies.disarm()

    assert world.chose.choices == []
    assert world.futures.arming.disarm_calls == 1
    assert world.spot.arming.disarm_calls == 0
    assert not world.strategies.can_disarm()


def test_with_two_venues_armed_disarm_asks_which_and_disarms_that_one_only(
    world,
) -> None:
    world.arm(FUTURES)
    world.arm(SPOT)
    world.chose.venue = SPOT

    world.strategies.disarm()

    (choice,) = world.chose.choices
    assert [venue for venue, _words in choice.options] == [FUTURES, SPOT]
    assert world.spot.arming.disarm_calls == 1
    assert world.futures.arming.disarm_calls == 0
    (left,) = world.strategies.armed_lines()
    assert left.startswith("Futures Testnet: ")


def test_cancelling_which_to_disarm_disarms_nothing(world) -> None:
    world.arm(FUTURES)
    world.arm(SPOT)
    world.chose.venue = None

    world.strategies.disarm()

    assert world.futures.arming.disarm_calls == world.spot.arming.disarm_calls == 0


def test_an_arm_and_a_disarm_are_told_in_the_output_pane_by_their_event(world) -> None:
    world.arm(FUTURES)
    world.strategies.on_changed(ArmedStrategyChangedEvent(True, venue=FUTURES))
    world.strategies.disarm()
    world.strategies.on_changed(ArmedStrategyChangedEvent(False, venue=FUTURES))

    armed, disarmed = world.told
    assert armed.startswith("Strategy armed on Futures Testnet: ")
    assert "BTCUSDT" in armed
    assert disarmed == "Strategy disarmed on Futures Testnet."


def test_a_change_from_elsewhere_is_told_when_its_event_arrives(world) -> None:
    """The strategy module's boot restore arms without these commands."""
    world.futures.armed.seed(
        LiveStrategyConfig(strategy_key=STRATEGY_KEY, symbol="BNBUSDT", interval="1h")
    )

    world.strategies.on_changed(ArmedStrategyChangedEvent(True, venue=FUTURES))

    (line,) = world.told
    assert "Futures Testnet" in line and "BNBUSDT 1h" in line
    assert world.strategies.can_disarm()


def test_the_form_opens_on_the_saved_arming_and_never_arms_by_itself(world) -> None:
    world.spot.arming.arm(
        LiveStrategyConfig(strategy_key=STRATEGY_KEY, symbol="SOLUSDT", interval="15m")
    )
    world.spot.arming.armed_with = None
    world.asked.cancel = True

    world.strategies.arm()

    form: StrategyFormViewModel = world.asked.questions[0].forms[SPOT]
    assert (form.selected_symbol, form.live_interval) == ("SOLUSDT", "15m")
    assert form.symbol_options[0] == "SOLUSDT"
    assert world.spot.arming.armed_with is None


def test_arm_is_offered_whether_or_not_the_venue_trades(world) -> None:
    """`EPIC-034C` — the order session stays open once a bot, an arm or an order opened it, so an
    open session no longer waits the commands: only an action in flight does (the session
    refuses by cause)."""
    assert world.strategies.can_arm()

    world.arm(SPOT)

    assert world.strategies.can_disarm()
