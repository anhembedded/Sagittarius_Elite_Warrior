"""`BOT-174` — the capital "Start" suggests passes the rule it was suggested for.

@details A proportional estimate (`capital × available / need`) failed the same rule
for about one plan in five: quantities floor to the exchange's step and small orders
are bumped to the minimum notional. `fitting_capital` re-draws the real plan until
the ladder fits, and these tests re-draw it again from the parameters, not through the
needs' own closure.
"""

from __future__ import annotations

import random
from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.exchange_rules import (
    fitting_capital,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.ladder_needs import (
    start_ladder_needs,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    TERMS,
)

_ETH_TERMS = replace(
    TERMS,
    tick_size=Decimal("0.01"),
    step_size=Decimal("0.0001"),
    min_notional=Decimal(5),
)
_ETH_PRICE = Decimal(2500)


def _random_configs(count: int) -> list[dict[str, str]]:
    rng = random.Random(174)  # noqa: S311 - a seeded test generator, not a secret
    return [
        {
            **CONFIG,
            "lower": str(rng.randrange(1500, 2400)),
            "upper": str(rng.randrange(2600, 4000)),
            "grid_count": str(rng.randrange(3, 60)),
            "capital_quote": str(rng.randrange(150, 20_000)),
        }
        for _ in range(count)
    ]


def test_every_suggested_capital_passes_the_rule_it_was_suggested_for() -> None:
    """A proportional estimate failed the same rule for about one capital in five
    (quantities floor to the step, small orders bump to the minimum notional)."""
    rng = random.Random(7)  # noqa: S311 - a seeded test generator, not a secret
    suggested = 0
    for config in _random_configs(600):
        needs = start_ladder_needs(config, _ETH_TERMS, _ETH_PRICE)
        assert needs is not None
        available = (needs.quote * Decimal(str(rng.uniform(0.5, 0.999)))).quantize(
            Decimal("0.01")
        )
        if needs.quote <= available:
            continue
        fits = fitting_capital(needs, available)
        if fits is None:
            continue
        suggested += 1
        # Re-drawn from the parameters, not through the needs' own closure.
        again = start_ladder_needs(
            {**config, "capital_quote": str(fits)}, _ETH_TERMS, _ETH_PRICE
        )
        assert again is not None and again.quote <= available, (config, fits, available)
    assert suggested > 500


def test_the_suggestion_is_near_the_largest_capital_that_fits() -> None:
    """Checked is not enough: a suggestion of 1 USDT passes everything."""
    for config in _random_configs(100):
        needs = start_ladder_needs(config, _ETH_TERMS, _ETH_PRICE)
        assert needs is not None
        available = (needs.quote * Decimal("0.9")).quantize(Decimal("0.01"))
        fits = fitting_capital(needs, available)
        assert fits is not None
        assert fits >= needs.capital * Decimal("0.9") * Decimal("0.97")
