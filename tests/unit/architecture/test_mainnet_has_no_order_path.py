"""The read-only mainnet account has no import path to anything that trades
(`EPIC-034E`, decision D4).

**The rule.** A mainnet key is read, never traded. `AccountSource.SPOT_MAINNET_READONLY`
is not a `TradingVenue` (`EPIC-026` D3 keeps `TradingVenue` free of a mainnet
member), and the code that serves it must not be able to reach a trading
session factory, a trading client, an order-submission port or `execute_order`.
A flag on a trading venue would be the "second path" `EPIC-026` forbids; a type
with no such import makes the wrong state unwritable.

**What is checked.** Every module under `modules/trading/adapters/binance/mainnet/`,
plus the credentials and the read-client port it is built from, is a start. The
walk follows every runtime import (not `TYPE_CHECKING`) through the whole of
`src/`, transitively, and fails when it reaches a module in `FORBIDDEN`. The
failure prints the chain that got there. Two more checks lock the other two
legs: `TradingVenue` has no mainnet member, and the read client's port lists
exactly the reads (a new method is a decision someone must make here).

**Three things the walk alone would miss, each checked** (PR #417 review):
1. *Package imports.* Importing `a.b.c` runs `a/__init__.py` and
   `a/b/__init__.py`, and `from pkg import name` may name a submodule. The walk
   follows every ancestor package and expands `from pkg import name` to
   `pkg.name`; this found that `support/binance_gateway/contracts/__init__.py`
   re-exported the trading session port, which is no longer so.
2. *Call sites.* python-binance's `Client` has order methods and the port hides
   them only from the type checker. Every file of the mainnet package is scanned
   for an attribute call that names an order (`create_order`,
   `create_test_order`, `cancel_*`, `order_oco_*` ...) and for any import of
   `binance.client` outside the one session factory.
3. *Scope.* The starts are the mainnet package, its three port files and the
   bots query that serves it. `VenueAccounts` (the registry that also holds the
   testnet readers) and the Mainnet account window are not starts: the first
   legitimately imports the venue contexts, the second shares the Bots screen's
   reads, which reach order ports through other queries. Both only call
   `IVenueAccountReader.read`.

Retire when: the read-only mainnet source is deleted, or mainnet becomes a
trading venue by a reviewed decision that supersedes `EPIC-026` D3.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.tests.unit.architecture.order_path_walk import (
    SESSION_FACTORY_FILE,
    SRC,
    START_FILES,
    file_of,
    order_call_sites,
    path_to_an_order,
    source_in_repo,
    start_modules,
)


def test_the_guard_has_a_subject() -> None:
    starts = start_modules()

    assert len(starts) > len(START_FILES)  # the directory held modules too
    assert all(file_of(module) is not None for module in starts)


def test_the_read_only_mainnet_source_reaches_nothing_that_trades() -> None:
    chain = path_to_an_order(start_modules(), source_in_repo)

    assert chain is None, (
        "the read-only mainnet source reaches an order: " + " -> ".join(chain or [])
    )


def test_no_file_of_the_mainnet_package_calls_an_order() -> None:
    mainnet = SRC / "modules" / "trading" / "adapters" / "binance" / "mainnet"
    found: list[str] = []
    for path in sorted(mainnet.glob("*.py")):
        found += order_call_sites(
            path.read_text(encoding="utf-8"),
            path.name,
            may_build_client=path.name == SESSION_FACTORY_FILE,
        )

    assert found == []
