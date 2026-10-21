"""`CS-009` - a start journey on each venue runs at the owner's caps, not at no spacing at all.

The journeys' configuration sets `min_order_spacing_ms` to 0 (`grid_fake_exchange.app_config`), so
a journey that does not restore the caps never meets the app's own pacing; `BUG-194`, `BUG-238`,
`BUG-241` and `BUG-254` were each a start refused by the bot's own budget, and each was found by
the owner's money, not by a journey. This guard requires, for Spot (`booted`) and for Futures
(`booted_futures_bots`), at least one integration journey that boots with the production pacer
(`pacers=`) and `limits=PRODUCTION_PACING`, the caps read off `DEFAULT_OWNER_BUDGET_CAPS`.

Retire when: every bots journey runs at production pacing by default, and `app_config` carries no
zero spacing.
"""

from __future__ import annotations

import ast
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
)
from Sagittarius_Elite_Warrior.tests.integration.modules.bots.virtual_order_time import (
    PRODUCTION_PACING,
)

#: The two booted worlds a start journey uses, by venue.
WORLDS = {"Spot": "booted", "Futures": "booted_futures_bots"}


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError("no pyproject.toml above this file")


_REPO_ROOT = _repo_root()
_JOURNEYS = _REPO_ROOT / "tests" / "integration" / "modules" / "bots"


def _journeys_at_production_pacing(world: str) -> list[str]:
    found = []
    for path in sorted(_JOURNEYS.glob("test_*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and _name(node.func) == world):
                continue
            keywords = {k.arg: k.value for k in node.keywords}
            limits = keywords.get("limits")
            if "pacers" in keywords and _name(limits) == "PRODUCTION_PACING":
                found.append(path.name)
    return found


def _name(node: ast.expr | None) -> str:
    return node.id if isinstance(node, ast.Name) else ""


def test_each_venues_start_has_a_journey_at_the_production_pacing() -> None:
    missing = {
        venue: world
        for venue, world in WORLDS.items()
        if not _journeys_at_production_pacing(world)
    }

    assert not missing, (
        f"no journey boots {missing} with `pacers=` and `limits=PRODUCTION_PACING` "
        "(tests/integration/modules/bots/virtual_order_time.py): the bot's own budget is never met"
    )


def test_the_production_pacing_is_read_off_the_owners_caps() -> None:
    assert {
        "trading.bot_limits.min_order_spacing_ms": (
            DEFAULT_OWNER_BUDGET_CAPS.min_order_spacing.total_seconds() * 1000
        ),
        "trading.bot_limits.max_orders_per_minute": (
            DEFAULT_OWNER_BUDGET_CAPS.max_orders_per_minute
        ),
    } == PRODUCTION_PACING
