"""The contract suite for `IEquityCurve` (HLD §10.3).

One guarantee, because the port has one method and one promise worth stating:
**what comes back cannot be used to change what is stored.** The real
implementation keeps a `deque` it mutates on every `ACCOUNT_UPDATE`; before
this port it defended that by copying into a list on every read, and a
consumer holding the copy could still edit it and hand the edited list to the
next reader. An immutable answer is the guarantee, and it is worth pinning
because it is the one an implementation could quietly drop by returning its
own container.

Ordering is part of it: oldest first, because a chart drawn from the wrong end
looks plausible and is wrong.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.equity_sample import (
    EquitySample,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_equity_curve import (
    IEquityCurve,
)

#: How a subclass puts samples into its implementation — the fake seeds, the
#: real recorder records.
type Seed = Callable[[tuple[EquitySample, ...]], None]


class EquityCurveContract:
    """Inherit this, provide `impl` and `seed`. Both implementations pass it."""

    @pytest.fixture
    def impl(self) -> IEquityCurve:
        raise NotImplementedError(
            "an EquityCurveContract subclass must provide an `impl` fixture"
        )

    @pytest.fixture
    def seed(self) -> Seed:
        raise NotImplementedError(
            "an EquityCurveContract subclass must provide a `seed` fixture"
        )

    def test_an_empty_curve_answers_empty(self, impl: IEquityCurve) -> None:
        assert impl.samples() == ()

    def test_samples_come_back_oldest_first(
        self,
        impl: IEquityCurve,
        seed: Seed,
        two_samples: tuple[EquitySample, EquitySample],
    ) -> None:
        older, newer = two_samples
        seed((older, newer))

        assert impl.samples() == (older, newer)

    def test_the_answer_is_immutable(
        self,
        impl: IEquityCurve,
        seed: Seed,
        two_samples: tuple[EquitySample, EquitySample],
    ) -> None:
        """A caller cannot edit what it was handed, so it cannot pass an
        edited backlog on as if the venue had reported it."""
        older, _ = two_samples
        seed((older,))

        answer = impl.samples()

        assert isinstance(answer, tuple)
        assert not hasattr(answer, "append")
