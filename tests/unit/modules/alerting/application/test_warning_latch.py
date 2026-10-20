"""`EPIC-036B1` — one open warning per key, and a cool-down between two raises."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.alerting.application.warning_latch import (
    WarningLatch,
)

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
COOLDOWN = timedelta(minutes=10)


def test_a_key_is_raised_once_while_it_stays_open() -> None:
    latch = WarningLatch(COOLDOWN)

    assert latch.raise_("bot-1", NOW)
    assert not latch.raise_("bot-1", NOW + timedelta(hours=3))


def test_a_cleared_key_is_not_raised_again_inside_the_cooldown() -> None:
    latch = WarningLatch(COOLDOWN)
    latch.raise_("bot-1", NOW)
    assert latch.clear("bot-1", NOW + timedelta(minutes=1))

    assert not latch.raise_("bot-1", NOW + timedelta(minutes=9))
    assert latch.raise_("bot-1", NOW + COOLDOWN)


def test_clearing_a_key_that_never_reached_the_hub_is_silent() -> None:
    latch = WarningLatch(COOLDOWN)
    latch.raise_("bot-1", NOW)
    latch.clear("bot-1", NOW + timedelta(minutes=1))
    latch.raise_("bot-1", NOW + timedelta(minutes=2))  # held back by the cool-down

    assert not latch.clear("bot-1", NOW + timedelta(minutes=3))


def test_keys_are_independent() -> None:
    latch = WarningLatch(COOLDOWN)
    latch.raise_("bot-1", NOW)

    assert latch.raise_("bot-2", NOW)


def test_a_forgotten_key_starts_afresh() -> None:
    latch = WarningLatch(COOLDOWN)
    latch.raise_("bot-1", NOW)
    latch.forget("bot-1")

    assert not latch.is_open("bot-1")
    assert latch.raise_("bot-1", NOW)


def test_a_deferred_clear_inside_the_cooldown_leaves_the_key_open() -> None:
    latch = WarningLatch(COOLDOWN, defer_clear=True)
    latch.raise_("bot-1", NOW)

    assert not latch.clear("bot-1", NOW + timedelta(minutes=9))
    assert latch.is_open("bot-1")
    assert latch.clear("bot-1", NOW + COOLDOWN)


def test_a_deferred_key_still_open_after_the_cooldown_is_raised_again() -> None:
    latch = WarningLatch(COOLDOWN, defer_clear=True)
    latch.raise_("bot-1", NOW)

    assert not latch.raise_("bot-1", NOW + timedelta(minutes=9))
    assert latch.raise_("bot-1", NOW + COOLDOWN)
