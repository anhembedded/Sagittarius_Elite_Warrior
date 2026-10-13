"""`EPIC-039A` - the `bots` module decides what a market allows in one place, the venue profile.

Before this task `bots` compared `venue.market_type` with `MarketType.SPOT` in fifteen places
and passed `MarketType.SPOT` to its data reads in a dozen more, so Futures would have meant a
second `if` at each. The question now belongs to `contracts/venue_profile.py`
(`venue_profile_of`); a site that needs the market asks the profile, and a new comparison with a
specific market anywhere else in `src/modules/bots/` turns this red.

The guard reads each file with `ast`, so a word in a docstring does not count. It flags:
a reference to `MarketType.<member>`, a comparison of a `.market_type` attribute with anything
that names a market, and the `SpotHolding` type (the readiness snapshot's Spot balances).
`bot_price_watch.py` and `bot_event_router.py` use `market_type` to *match* an event to an
executor (two attributes compared with each other), which is generic and stays.

`SpotHolding` has one named exception, `exchange_facts_reader.py`, until `EPIC-039E` moves the
readiness read behind `IVenueFacts`; the test fixes that list by name so it can only shrink.

Retire when: `EPIC-039E` has removed the `SpotHolding` exception and nothing else in this
guard's reasoning is left, or `bots` is split so the profile is a shared kernel contract.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BOTS = _REPO_ROOT / "src" / "modules" / "bots"

#: The one file that decides, by name. A directory here would let a second decider hide.
_PROFILE = _BOTS / "contracts" / "venue_profile.py"
#: `EPIC-039E` removes this: the readiness snapshot reads Spot balances until `IVenueFacts`.
_SPOT_HOLDING_UNTIL_039E = (
    _BOTS / "application" / "services" / "exchange_facts_reader.py",
)
#: A stream filter, not a decision: it forwards the ticks whose market equals the market the
#: feed was built for. The market arrives from `BOT_MARKET`; nothing here names one.
_TICK_FILTER = _BOTS / "ui" / "bot_tick_feed.py"


def offences(source: str) -> list[tuple[int, str]]:
    """(line, what) for each hard-coded market decision in `source`."""
    tree = ast.parse(source)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "MarketType"
        ):
            found.append((node.lineno, f"MarketType.{node.attr}"))
        elif isinstance(node, ast.Compare) and _compares_market_type_to_a_market(node):
            found.append((node.lineno, "a .market_type comparison"))
        elif isinstance(node, ast.Name) and node.id == "SpotHolding":
            found.append((node.lineno, "SpotHolding"))
    return found


def _compares_market_type_to_a_market(node: ast.Compare) -> bool:
    operands = [node.left, *node.comparators]
    reads_market_type = [
        isinstance(o, ast.Attribute) and o.attr == "market_type" for o in operands
    ]
    # `a.market_type is b.market_type` matches two things; `x.market_type is <anything else>`
    # decides on a market.
    return any(reads_market_type) and not all(reads_market_type)


def _bots_files() -> list[Path]:
    return sorted(p for p in _BOTS.rglob("*.py") if "__pycache__" not in p.parts)


def test_only_the_venue_profile_decides_the_market() -> None:
    files = _bots_files()
    assert files, "the scan found no bots file"
    stray: list[str] = []
    for path in files:
        if path == _PROFILE:
            continue
        for line, what in offences(path.read_text(encoding="utf-8")):
            if what == "SpotHolding" and path in _SPOT_HOLDING_UNTIL_039E:
                continue
            if what == "a .market_type comparison" and path == _TICK_FILTER:
                continue
            stray.append(f"{path.relative_to(_REPO_ROOT)}:{line} {what}")
    assert not stray, (
        "bots decides a market outside contracts/venue_profile.py - ask the venue "
        "profile (IVenueProfiles / venue_profile_of) instead:\n  " + "\n  ".join(stray)
    )


def test_the_guard_sees_each_kind_of_branch_it_exists_to_forbid() -> None:
    """The mutation, in unit form: plant each shape and it is found."""
    assert offences("x = venue.market_type is not MarketType.SPOT") != []
    assert offences("load(MarketType.FUTURES_USD_M, symbol)") != []
    assert offences("if venue.market_type == market: pass") != []
    assert offences("def f(h: tuple[SpotHolding, ...]): ...") != []


def test_the_guard_leaves_alone_what_it_must() -> None:
    assert offences("matched = executor.venue.market_type is event.market_type") == []
    assert offences("'''the word MarketType.SPOT in prose'''") == []
    assert offences("market = bot.definition.venue.market_type") == []


def test_the_named_exceptions_exist_and_are_exact() -> None:
    for path in (_PROFILE, _TICK_FILTER, *_SPOT_HOLDING_UNTIL_039E):
        assert path.is_file() and path.suffix == ".py", path
