"""`BUG-257` — a registration refused because the exchange paused says so, in words."""

from __future__ import annotations

from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_housekeeping import (
    refusal_text,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.exchange_pause_behind import (
    exchange_pause_behind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
    OwnerBudgetRegistrationResult,
)

_PAUSE = timedelta(seconds=30)


def _unavailable_because_of(
    cause: BaseException | None,
) -> AccountHistoryUnavailableError:
    error = AccountHistoryUnavailableError("positionRisk: failed")
    error.__cause__ = cause
    return error


def test_the_pause_behind_a_failed_read_is_found_along_its_causes() -> None:
    pause = ExchangeRateLimitedError(_PAUSE, banned=False, raw_message="429")

    assert exchange_pause_behind(_unavailable_because_of(pause)) == _PAUSE


def test_a_read_that_failed_for_another_reason_has_no_pause() -> None:
    assert exchange_pause_behind(_unavailable_because_of(RuntimeError("down"))) is None
    assert exchange_pause_behind(_unavailable_because_of(None)) is None


def test_the_refusal_names_the_pause_first_and_never_the_code() -> None:
    paused = OwnerBudgetRegistrationResult(
        OwnerBudgetRefusal.INVENTORY_UNAVAILABLE, paused_for=_PAUSE
    )
    unread = OwnerBudgetRegistrationResult(OwnerBudgetRefusal.INVENTORY_UNAVAILABLE)

    assert refusal_text(paused).startswith("the exchange asked for a pause of 30 s")
    assert "inventory_unavailable" not in refusal_text(paused)
    assert refusal_text(unread) == "the exchange's records could not be read"
