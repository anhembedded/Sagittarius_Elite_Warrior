"""The verified fakes of `strategy`'s ports, and the contract suites both the
fakes and the real implementations must pass (HLD §10.3).

These are **public API**, not test scaffolding: HLD §10.3 rule 1 says a fake
ships with its contract in the provider module, and rule 4 forbids a consumer
mocking a port it does not own. A consumer's test imports the fake from here.
"""

from .contract_armed_strategy import ArmedStrategyContract
from .contract_sizing_policy import SizingPolicyContract
from .contract_strategy_arming import StrategyArmingContract
from .contract_strategy_catalog import StrategyCatalogContract
from .contract_strategy_chart_overlay import StrategyChartOverlayContract
from .fake_armed_strategy import FakeArmedStrategy
from .fake_strategy_arming import FakeStrategyArming
from .fake_strategy_catalog import FakeStrategyCatalog
from .fake_strategy_chart_overlay import FakeStrategyChartOverlay

#: `SizingPolicyContract` has no fake beside it, and the reason is written
#: in its own module docstring: `ISizingPolicy` is pure arithmetic, so a
#: double could only re-type the formula or answer canned numbers. Rule 4
#: above still applies — a consumer uses the real policy with different
#: inputs, never a `Mock`.
__all__ = [
    "ArmedStrategyContract",
    "FakeArmedStrategy",
    "FakeStrategyArming",
    "FakeStrategyCatalog",
    "FakeStrategyChartOverlay",
    "SizingPolicyContract",
    "StrategyArmingContract",
    "StrategyCatalogContract",
    "StrategyChartOverlayContract",
]
