"""`SizingPolicyContract` against `ISizingPolicy`'s one implementation.

HLD §10.3 rule 3 has the fake run a suite in unit and the real implementation
run it in integration. There is no fake here — `contract_sizing_policy.py`
explains why, and it is the same reason there is no integration run: the
implementation is pure arithmetic with nothing to reach for, so unit *is* where
the real one runs.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_sizing_policy import (
    ISizingPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.testing import (
    SizingPolicyContract,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.policies.margin_sizing_policy import (
    MarginSizingPolicy,
)


class TestMarginSizingPolicyKeepsTheContract(SizingPolicyContract):
    @pytest.fixture
    def impl(self) -> ISizingPolicy:
        return MarginSizingPolicy()
