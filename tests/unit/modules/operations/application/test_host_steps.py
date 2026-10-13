"""What the host does once at start, between the app's boot and its first health line (`EPIC-038D`)."""

from __future__ import annotations

import logging

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    ResumeRecoveringResult,
    VenueResumeOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_steps import (
    ReportRecoveringBots,
    ResumeRecoveringBots,
    StartPlannedBots,
    WarnWhenNoAlertChannel,
    mainnet_resume_refusal,
    mainnet_start_refusal,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_alert_channels import (
    IAlertChannels,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.application.host_steps_world import (
    FixedPlan,
    StepsWorld,
    entry,
    opened,
)

_LOGGER = "App.Operations.Host"


class _Alerts(IAlertChannels):
    def __init__(self, carries: bool) -> None:
        self._carries = carries

    def carries_bot_events(self) -> bool:
        return self._carries


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


# --- the alert warning ---------------------------------------------------------


def test_with_no_alert_channel_the_host_warns_that_nothing_will_say_a_bot_halted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        WarnWhenNoAlertChannel(_Alerts(False)).run()

    assert _warnings(caplog) == [
        "[alerts] no alert channel is configured for bot events; nothing will tell you if a bot halts"
    ]


def test_with_an_alert_channel_the_host_does_not_warn(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        WarnWhenNoAlertChannel(_Alerts(True)).run()

    assert _warnings(caplog) == []


# --- recovering bots (decision O2) --------------------------------------------


def test_recovering_bots_stay_recovering_by_default_and_are_named_in_the_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = StepsWorld(
        entry("aaaaaa", "RECOVERING"),
        entry("bbbbbb", "RUNNING"),
        entry("cccccc", "RECOVERING"),
    )

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        ReportRecoveringBots(world).run()

    warnings = _warnings(caplog)
    assert len(warnings) == 2  # one WARNING per bot
    assert "aaaaaa" in warnings[0] and "bot resume aaaaaa" in warnings[0]
    assert "cccccc" in warnings[1] and "bot resume cccccc" in warnings[1]
    # The headless remedy that exists today is named, with the flag a mainnet venue needs.
    assert all("--resume-recovering" in w and "--confirm-venue" in w for w in warnings)
    assert world.starts == [] and world.resumes == []  # the host resumed nothing


def test_no_recovering_bot_is_no_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        ReportRecoveringBots(StepsWorld(entry("aaaaaa", "RUNNING"))).run()

    assert _warnings(caplog) == []


def test_resume_recovering_asks_for_the_session_the_screen_opens_and_names_the_outcome(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = StepsWorld(
        resume=ResumeRecoveringResult(
            (
                opened("spot_testnet", "aaaaaa"),
                VenueResumeOutcome(
                    "futures_testnet", ("bbbbbb",), opened=False, note="blocked"
                ),
            )
        )
    )

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        ResumeRecoveringBots(world, confirmed_venue="spot_mainnet").run()

    assert [r.confirmed_venue for r in world.resumes] == ["spot_mainnet"]
    assert any(
        "spot_testnet" in r.getMessage() and "aaaaaa" in r.getMessage()
        for r in caplog.records
        if r.levelno == logging.INFO
    )
    assert any("futures_testnet" in m and "blocked" in m for m in _warnings(caplog))


# --- start-planned ---------------------------------------------------------------


def test_start_planned_starts_the_planned_bots_that_are_at_rest_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = StepsWorld(
        entry("aaaaaa", "STOPPED"),  # planned, at rest -> started
        entry("bbbbbb", "DRAFT"),  # planned, at rest -> started
        entry("cccccc", "RUNNING"),  # planned, already active -> left alone
        entry("dddddd", "RECOVERING"),  # planned but a person's (decision O2)
        entry("eeeeee", "STOPPED"),  # at rest but not planned -> left alone
    )
    plan = FixedPlan(frozenset({"aaaaaa", "bbbbbb", "cccccc", "dddddd"}))

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        StartPlannedBots(plan, world, confirmed_venue=None).run()

    assert [c.bot_id for c in world.starts] == ["aaaaaa", "bbbbbb"]
    assert _warnings(caplog) == []


def test_start_planned_says_so_when_there_is_no_plan_and_starts_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = StepsWorld(entry("aaaaaa", "STOPPED"))

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        StartPlannedBots(FixedPlan(None), world, confirmed_venue=None).run()

    assert world.starts == []
    (warning,) = _warnings(caplog)
    assert "no bot plan" in warning
    assert "EPIC-038I" in warning


def test_a_refused_start_is_a_warning_and_the_others_still_start(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = StepsWorld(
        entry("aaaaaa", "STOPPED"),
        entry("bbbbbb", "STOPPED"),
        refuse_start={"aaaaaa": BotRefusal.VENUE_NOT_READY},
    )
    plan = FixedPlan(frozenset({"aaaaaa", "bbbbbb"}))

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        StartPlannedBots(plan, world, confirmed_venue=None).run()

    assert [c.bot_id for c in world.starts] == ["aaaaaa", "bbbbbb"]
    (warning,) = _warnings(caplog)
    assert "aaaaaa" in warning and "VENUE_NOT_READY" in warning


def test_a_planned_bot_nobody_has_is_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = StepsWorld(entry("aaaaaa", "STOPPED"))

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        StartPlannedBots(
            FixedPlan(frozenset({"aaaaaa", "zzzzzz"})), world, confirmed_venue=None
        ).run()

    assert [c.bot_id for c in world.starts] == ["aaaaaa"]
    assert any("zzzzzz" in m for m in _warnings(caplog))


def test_the_venue_the_operator_typed_travels_with_every_start() -> None:
    world = StepsWorld(entry("aaaaaa", "STOPPED", "spot_mainnet"))

    StartPlannedBots(
        FixedPlan(frozenset({"aaaaaa"})), world, confirmed_venue="spot_mainnet"
    ).run()

    assert [c.confirmed_venue for c in world.starts] == ["spot_mainnet"]


# --- decision O8: refuse before anything starts --------------------------------


@pytest.mark.parametrize(
    ("typed", "refused"),
    [
        (None, True),
        ("spot_testnet", True),
        ("futures_mainnet", True),
        ("spot_mainnet", False),
    ],
)
def test_a_planned_mainnet_bot_refuses_the_whole_start_unless_its_venue_was_typed(
    typed: str | None, refused: bool
) -> None:
    bots = (
        entry("aaaaaa", "STOPPED", "spot_testnet"),
        entry("bbbbbb", "STOPPED", "spot_mainnet"),
    )
    message = mainnet_start_refusal(
        bots, FixedPlan(frozenset({"aaaaaa", "bbbbbb"})), typed
    )

    assert (message is not None) is refused
    if refused:
        assert message is not None
        assert "bbbbbb" in message
        assert "--confirm-venue spot_mainnet" in message


def test_a_mainnet_bot_the_plan_does_not_want_running_needs_no_confirmation() -> None:
    bots = (entry("bbbbbb", "STOPPED", "spot_mainnet"),)

    assert mainnet_start_refusal(bots, FixedPlan(frozenset()), None) is None
    assert mainnet_start_refusal(bots, FixedPlan(None), None) is None


def test_a_mainnet_bot_already_running_needs_no_confirmation_to_be_left_alone() -> None:
    bots = (entry("bbbbbb", "RUNNING", "spot_mainnet"),)

    assert mainnet_start_refusal(bots, FixedPlan(frozenset({"bbbbbb"})), None) is None


@pytest.mark.parametrize(
    ("typed", "refused"),
    [
        (None, True),
        ("spot_testnet", True),
        ("futures_mainnet", True),
        ("spot_mainnet", False),
    ],
)
def test_a_recovering_mainnet_bot_refuses_the_whole_resume_unless_its_venue_was_typed(
    typed: str | None, refused: bool
) -> None:
    """Decision O8 says exit 2, not a quiet skip: the host must not serve while it has
    left real-money bots unresumed that the operator thought it had resumed."""
    bots = (
        entry("aaaaaa", "RECOVERING", "spot_testnet"),
        entry("bbbbbb", "RECOVERING", "spot_mainnet"),
    )

    message = mainnet_resume_refusal(bots, typed)

    assert (message is not None) is refused
    if refused:
        assert message is not None
        assert "bbbbbb" in message
        assert "--confirm-venue spot_mainnet" in message
        assert "--resume-recovering" in message


@pytest.mark.parametrize("state", ["RUNNING", "PAUSED", "RECOVERING"])
def test_every_state_a_restart_makes_recovering_is_judged_before_the_boot_makes_it_so(
    state: str,
) -> None:
    """The refusal runs before `app.boot()`, and the boot is what turns a RUNNING or
    PAUSED bot on disk into RECOVERING: a bot left RUNNING by a crash is the common case."""
    message = mainnet_resume_refusal((entry("aaaaaa", state, "spot_mainnet"),), None)

    assert message is not None and "aaaaaa" in message
    assert "--confirm-venue spot_mainnet" in message


def test_a_mainnet_bot_a_restart_does_not_hold_back_needs_no_confirmation_to_resume() -> (
    None
):
    bots = (
        entry("aaaaaa", "STOPPED", "spot_mainnet"),
        entry("bbbbbb", "HALTED", "futures_mainnet"),
        entry("dddddd", "DRAFT", "spot_mainnet"),
        entry("cccccc", "RECOVERING", "spot_testnet"),
    )

    assert mainnet_resume_refusal(bots, None) is None


def test_recovering_bots_on_two_mainnet_venues_name_both_and_say_one_run_confirms_one() -> (
    None
):
    bots = (
        entry("aaaaaa", "RECOVERING", "spot_mainnet"),
        entry("bbbbbb", "RECOVERING", "futures_mainnet"),
    )

    message = mainnet_resume_refusal(bots, None)

    assert message is not None
    assert "aaaaaa" in message and "bbbbbb" in message
    assert "2 venues" in message


def test_a_plan_that_wants_nothing_running_says_so_instead_of_starting_nothing_silently(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = StepsWorld(entry("aaaaaa", "STOPPED"))

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        StartPlannedBots(FixedPlan(frozenset()), world, None).run()

    assert world.starts == []
    assert any("wants no bot running" in r.getMessage() for r in caplog.records)
