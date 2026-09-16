"""The contract suite for `ISizingPolicy` (HLD §10.3).

Every guarantee here is one a consumer relies on, which is rule 2 of that
section. They come from the two that exist:

**`PaperExchange` relies on the clamp.** It books `allocation.margin` against a
simulated balance and refuses the entry when nothing is fundable. A sizing the
account cannot afford must therefore *shrink to the free balance*, not overdraw
it and not be refused outright — a backtest that refused every entry above the
balance would silently report a strategy that never traded.

**`LiveTradingCoordinator` relies on "never raises".** A signal arriving on an
empty account, or on a `RISK_PERCENT` sizing with no stop distance, is an
ordinary outcome on the tick path — and that path has no `except` of its own
(see `MarketTickEventHandler`), so an implementation that raised would take
down tick processing for the rest of the session.

**Both rely on the leverage ratio surviving the clamp**, because that ratio is
the difference between the position the exchange opens and the money it costs.

@par There is no `FakeSizingPolicy`, and that is deliberate
Every other port in this module ships one, because every other port reaches
something a test cannot have — a session, an exchange, a socket. This one is
arithmetic: pure, in-memory, instant, with no I/O to stand in for. A double
could only either re-type the formula, which is the drift disease `CLAUDE.md`
records this repository catching twice, or answer canned numbers, which
[`CS-001`](../../../../../Docs/CASE_STUDIES/CS-001_a_double_that_could_not_disagree.md)
is the case study of. A consumer that needs a different allocation gives the
real policy different inputs. If a consumer ever needs to force an allocation
the formula cannot produce, the fake arrives then, with that consumer — the
rule `base_feed.py` states and `BUG-126` applied: promote on the second need,
not in anticipation of it.

So this suite runs against the real implementation, in the unit tier (there is
nothing for an integration tier to add), and its job is the one a second
implementation will need it for: ADR D17's own promise to the user is that
*"changing how size is computed (ATR-based, Kelly, …) is one change in the
strategy module"*, and this is what such a change has to keep true.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.position_sizing import (
    PositionSizing,
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_sizing_policy import (
    ISizingPolicy,
)

#: One account, used by every case here so a number can be read against it.
_EQUITY = 10_000.0
_BALANCE = 10_000.0
_PRICE = 100.0


class SizingPolicyContract:
    """Inherit this and provide `impl`."""

    @pytest.fixture
    def impl(self) -> ISizingPolicy:
        raise NotImplementedError(
            "a SizingPolicyContract subclass must provide an `impl` fixture"
        )

    def test_a_percentage_of_equity_is_that_percentage(
        self, impl: ISizingPolicy
    ) -> None:
        allocation = impl.allocate(
            sizing=PositionSizing(
                type=PositionSizingType.PERCENT_OF_EQUITY, value=20.0
            ),
            effective_price=_PRICE,
            current_equity=_EQUITY,
            available_balance=_BALANCE,
            leverage=1.0,
        )

        assert allocation.margin == pytest.approx(2_000.0)
        assert allocation.notional_capital == pytest.approx(2_000.0)
        assert allocation.is_fundable is True

    def test_leverage_buys_more_than_it_locks(self, impl: ISizingPolicy) -> None:
        """The whole reason the answer is two numbers rather than one."""
        allocation = impl.allocate(
            sizing=PositionSizing(
                type=PositionSizingType.PERCENT_OF_EQUITY, value=20.0
            ),
            effective_price=_PRICE,
            current_equity=_EQUITY,
            available_balance=_BALANCE,
            leverage=5.0,
        )

        assert allocation.margin == pytest.approx(2_000.0)
        assert allocation.notional_capital == pytest.approx(10_000.0)

    def test_margin_is_clamped_to_the_free_balance(self, impl: ISizingPolicy) -> None:
        """`PaperExchange` books the margin against a balance it must not
        overdraw — and a sizing above the balance shrinks rather than being
        refused, so a strategy still trades on a drawn-down account."""
        allocation = impl.allocate(
            sizing=PositionSizing(type=PositionSizingType.FIXED_CASH, value=50_000.0),
            effective_price=_PRICE,
            current_equity=_EQUITY,
            available_balance=1_000.0,
            leverage=1.0,
        )

        assert allocation.margin == pytest.approx(1_000.0)
        assert allocation.is_fundable is True

    def test_the_clamp_keeps_the_leverage_ratio(self, impl: ISizingPolicy) -> None:
        """Clamping the margin without scaling the notional would hand the
        caller a position larger than the margin it was sized for — an order
        the exchange refuses after it has been sent."""
        leverage = 5.0
        allocation = impl.allocate(
            sizing=PositionSizing(type=PositionSizingType.FIXED_CASH, value=50_000.0),
            effective_price=_PRICE,
            current_equity=_EQUITY,
            available_balance=1_000.0,
            leverage=leverage,
        )

        assert allocation.notional_capital == pytest.approx(
            allocation.margin * leverage
        )

    def test_both_numbers_agree_on_fundability_after_the_clamp(
        self, impl: ISizingPolicy
    ) -> None:
        """A sanity pairing for the two above: the clamp must not be able to
        scale a notional to nothing while leaving a positive margin, which is
        why `is_fundable` asks about both numbers."""
        allocation = impl.allocate(
            sizing=PositionSizing(type=PositionSizingType.FIXED_CONTRACTS, value=3.0),
            effective_price=_PRICE,
            current_equity=_EQUITY,
            available_balance=10.0,
            leverage=2.0,
        )

        assert (allocation.margin > 0) is (allocation.notional_capital > 0)
        assert allocation.margin <= 10.0

    @pytest.mark.parametrize(
        ("price", "leverage"),
        [(0.0, 1.0), (-1.0, 1.0), (_PRICE, 0.0), (_PRICE, -1.0)],
    )
    def test_a_price_or_leverage_that_cannot_size_answers_instead_of_raising(
        self, impl: ISizingPolicy, price: float, leverage: float
    ) -> None:
        allocation = impl.allocate(
            sizing=PositionSizing(
                type=PositionSizingType.PERCENT_OF_EQUITY, value=20.0
            ),
            effective_price=price,
            current_equity=_EQUITY,
            available_balance=_BALANCE,
            leverage=leverage,
        )

        assert allocation.is_fundable is False

    def test_an_empty_account_is_not_fundable(self, impl: ISizingPolicy) -> None:
        allocation = impl.allocate(
            sizing=PositionSizing(
                type=PositionSizingType.PERCENT_OF_EQUITY, value=20.0
            ),
            effective_price=_PRICE,
            current_equity=0.0,
            available_balance=0.0,
            leverage=1.0,
        )

        assert allocation.is_fundable is False

    @pytest.mark.parametrize("stop_loss_pct", [None, 0.0, -1.0])
    def test_risk_percent_without_a_stop_distance_is_not_fundable(
        self, impl: ISizingPolicy, stop_loss_pct: float | None
    ) -> None:
        """`RISK_PERCENT` means "a stop-loss hit costs exactly this much of
        equity" (`BOT-041`), and without a stop distance there is no such
        number. Answering with *some* size instead would be the dishonest
        option: it would be a different sizing rule than the one asked for."""
        allocation = impl.allocate(
            sizing=PositionSizing(type=PositionSizingType.RISK_PERCENT, value=1.0),
            effective_price=_PRICE,
            current_equity=_EQUITY,
            available_balance=_BALANCE,
            leverage=1.0,
            stop_loss_pct=stop_loss_pct,
        )

        assert allocation.is_fundable is False

    def test_risk_percent_sizes_so_the_stop_costs_the_risk(
        self, impl: ISizingPolicy
    ) -> None:
        """1% of 10,000 is 100; a 2% stop on a 100 price is a 2.00 distance,
        so the position is 100 / 2.00 = 50 units = 5,000 notional."""
        allocation = impl.allocate(
            sizing=PositionSizing(type=PositionSizingType.RISK_PERCENT, value=1.0),
            effective_price=_PRICE,
            current_equity=_EQUITY,
            available_balance=_BALANCE,
            leverage=1.0,
            stop_loss_pct=2.0,
        )

        assert allocation.notional_capital == pytest.approx(5_000.0)

    def test_the_allocation_is_frozen(self, impl: ISizingPolicy) -> None:
        """It is read by a paper broker's books and by a live order path; one
        must not be able to edit what the other was given."""
        allocation = impl.allocate(
            sizing=PositionSizing(
                type=PositionSizingType.PERCENT_OF_EQUITY, value=20.0
            ),
            effective_price=_PRICE,
            current_equity=_EQUITY,
            available_balance=_BALANCE,
            leverage=1.0,
        )

        with pytest.raises((AttributeError, TypeError)):
            allocation.margin = 1.0  # type: ignore[misc]
