"""`IEquityCurve`'s contract, against both implementations (HLD §10.3 rule 3).

The real one is `EquityCurveRecorder` — in-memory, no I/O — so unlike
`IOrderSubmission` there is nothing here that has to wait for a later pull
request: both run the suite now.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.equity_sample import (
    EquitySample,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.contract_equity_curve import (
    EquityCurveContract,
    Seed,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_equity_curve import (
    FakeEquityCurve,
)


def _sample(minute: int) -> EquitySample:
    return EquitySample(
        captured_at=datetime(2026, 9, 15, 12, minute, tzinfo=UTC),
        wallet_balance=Decimal(1000),
        unrealized_pnl=Decimal(minute),
    )


@pytest.fixture
def two_samples() -> tuple[EquitySample, EquitySample]:
    return _sample(1), _sample(2)


class TestTheFake(EquityCurveContract):
    @pytest.fixture
    def impl(self) -> FakeEquityCurve:
        return FakeEquityCurve()

    @pytest.fixture
    def seed(self, impl: FakeEquityCurve) -> Seed:
        return impl.seed


class TestTheRealRecorder(EquityCurveContract):
    @pytest.fixture
    def impl(self) -> EquityCurveRecorder:
        return EquityCurveRecorder()

    @pytest.fixture
    def seed(self, impl: EquityCurveRecorder) -> Seed:
        def seed(samples: tuple[EquitySample, ...]) -> None:
            for sample in samples:
                impl.record(sample)

        return seed


class TestTheFakesOwnBookkeeping:
    """`BUG-120` — `seed()` and `reads` are the fake's own, so nothing else
    checks them."""

    def test_seed_replaces_the_whole_backlog(self) -> None:
        """Replaces rather than appends, so a test states the situation
        instead of building up to it — and a second `seed()` in the same test
        cannot leave the first one's samples behind."""
        fake = FakeEquityCurve([_sample(1)])

        fake.seed([_sample(2), _sample(3)])

        assert fake.samples() == (_sample(2), _sample(3))

    def test_the_constructor_seeds_too(self) -> None:
        fake = FakeEquityCurve([_sample(1)])

        assert fake.samples() == (_sample(1),)

    def test_it_counts_the_reads(self) -> None:
        """A screen asking once at construction is the design; asking per
        repaint is a defect, and this is what lets a test see the
        difference."""
        fake = FakeEquityCurve()

        fake.samples()
        fake.samples()

        assert fake.reads == 2
