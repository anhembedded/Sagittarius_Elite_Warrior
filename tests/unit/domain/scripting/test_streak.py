"""Tests for Streak — the consecutive-bars-true counter (BOT-032)."""

from Sagittarius_Elite_Warrior.src.domain.scripting import Streak


def test_starts_at_zero():
    assert Streak().current == 0


def test_increments_while_condition_holds():
    streak = Streak()

    assert streak.update(True) == 1
    assert streak.update(True) == 2
    assert streak.update(True) == 3


def test_resets_the_instant_the_condition_fails():
    streak = Streak()
    streak.update(True)
    streak.update(True)

    assert streak.update(False) == 0


def test_can_restart_after_a_reset():
    streak = Streak()
    streak.update(True)
    streak.update(False)

    assert streak.update(True) == 1


def test_current_reflects_the_last_update_without_advancing():
    streak = Streak()
    streak.update(True)
    streak.update(True)

    assert streak.current == 2
    assert streak.current == 2  # reading it again must not itself count as a bar
