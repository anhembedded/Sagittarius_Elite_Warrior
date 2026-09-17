"""Both implementations of `IStrategyCatalog` against the same contract.

HLD §10.3 rule 2: `FakeStrategyCatalog` and `StrategyCatalogService` inherit
one suite here, so a guarantee a consumer relies on — an unregistered key
raises rather than answering an empty form, validation never raises — cannot
hold in the fake and fail in the real service.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_catalog_service import (
    StrategyCatalogService,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_catalog import (
    IStrategyCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.param_validation import (
    ParamValidation,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.strategy_option import (
    StrategyOption,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.testing import (
    FakeStrategyCatalog,
    StrategyCatalogContract,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)


class TestTheFake(StrategyCatalogContract):
    @pytest.fixture
    def impl(self) -> IStrategyCatalog:
        return FakeStrategyCatalog(
            options=(StrategyOption(key=self.a_key, label="Ema Crossover"),),
            forms={self.a_key: ()},
        )


class TestTheRealService(StrategyCatalogContract):
    @pytest.fixture
    def impl(self) -> IStrategyCatalog:
        registry = StrategyRegistry()
        registry.register(self.a_key, EmaCrossoverStrategy)
        return StrategyCatalogService(registry)


def test_the_fakes_scripted_validation_overrides_the_default_answer() -> None:
    """`script_validation()` is the fake's own extra helper, beside what
    `IStrategyCatalog` declares — `tests/unit/architecture/
    test_fake_helpers_are_verified.py` needs it exercised here, not only
    constructed, or a consumer's assertion through it would prove nothing
    (`BUG-120`)."""
    fake = FakeStrategyCatalog(forms={"ema_crossover": ()})
    fake.script_validation(ParamValidation(error="rejected on purpose"))

    result = fake.validate_params("ema_crossover", {})

    assert result.accepted is False
    assert result.error == "rejected on purpose"
