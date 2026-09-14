# BUG-120 — a verified fake's own helper was verified by nothing

| | |
| :--- | :--- |
| **Reported** | 2026-09-14 (found while reviewing `EPIC-025` PR 0.5 with `.claude/skills/pr-review/`) |
| **Severity** | High — not a runtime defect: a defect in the evidence. Three screens' tests asserted through a helper that could not fail, so the suite reported coverage it did not have. |
| **Status** | ✅ Fixed 2026-09-14 — root-caused / reproduced / regression-tested (guard + seven behaviour tests) / verified by re-breaking the helper |

## Symptom

`EPIC-025` PR 0.5 published `IMarketDataSync` with a verified fake, and the
four screens that used to build `SyncMarketDataCommand` themselves moved onto
it. Three of their tests then made one call their only positive assertion:

```python
assert sync.was_asked_for("BTCUSDT", TimeFrame.ONE_MINUTE)   # test_chart_coordinator.py:81
assert sync.was_asked_for("BTCUSDT", TimeFrame.ONE_HOUR)     # test_sync_coordinator.py:117
assert fake_market_data_sync.was_asked_for("BTCUSDT")        # test_dashboard_presenter.py:683
```

Replacing the body of `FakeMarketDataSync.was_asked_for()` with
`return True  # broken on purpose` and running every test that depends on it:

```
152 passed, 1 warning in 69.90s
```

The commit message for PR 0.5 claimed those tests "went from asserting
plumbing to asserting behaviour". Two of the three were asserting nothing at
all: a helper that can only ever say yes is the `Mock` it was introduced to
replace, with a better name.

`synced_symbols`, the fake's other helper, was worse — no caller, no test.

## Root cause

HLD §10.3 defines a **verified** fake as one the provider's contract suite
runs against alongside the real implementation. That is a real mechanism, and
it verifies exactly one thing: **the surface the port declares.**
`MarketDataSyncContract` therefore covers `sync()` eleven ways, against both
`FakeMarketDataSync` and `MarketDataSyncService`.

Nothing in the design said who verifies what the fake adds *on top* of the
port. `FakeMarketDataSync` declared two such members
(`src/modules/market_data/contracts/testing/fake_market_data_sync.py:62,67`),
and neither `IMarketDataSync` nor the contract suite has any opinion about
them, because neither knows they exist.

The mechanism, not the one helper, is the defect (`bug-fix-rule.md` §2). Three
consumers called `was_asked_for` and none verified it — that is not an
accident of where those tests live. A consumer calls a helper to say something
about *itself*; whether the helper answers truthfully is the provider's
guarantee. With no home for that guarantee, every fake is free to grow the
same hole, and the epic is about to add more: Phase 1 publishes
`IHistoricalKlines` and `IMarketStream`, and three market_data ports
(`IExchangeClient`, `ILiveStreamService`, `ISymbolMarketMetadataCache`) still
have no suite at all.

A second, smaller cause sat on the same line: `interval: object | None`.
`TimeFrame` is a `str` `Enum`, so a caller passing the raw `"1m"` matched by
accident, while a caller passing anything else got a silent `False` rather
than a type error.

## Fix

**The mechanism** — `tests/unit/architecture/test_fake_helpers_are_verified.py`:
every public member a `modules/*/contracts/testing/fake_*.py` class declares
that its port does **not** declare must be exercised by name under
`tests/unit/modules/<module>/contracts/` — beside the contract suite, for the
same reason the contract suite lives there rather than in each consumer. Port
methods are left to the suite; instance state (`requests`) is already read by
the suite through its `observed` fixture. A fake with no extra helpers passes
silently, which is why `FakeMarketDataRepository` and `FakeSymbolCatalog` —
both declaring nothing beyond their ports — needed no change. The reader is
`tests/unit/architecture/fake_helpers.py`, `ast` and never a regex, matching
`mocked_ports.py`; the guard is registered in `scanned_roots_registry.py` so
an empty scan cannot pass quietly (HLD §9.3 rule 4).

The guard's message names the fix and the choice: give the helper a test, or
delete it, because a helper with no consumer and no test is dead published
API. Both outcomes were used here — `was_asked_for` got tests,
`synced_symbols` was deleted.

**The two helpers** — `was_asked_for` keeps its seven-test suite below;
`synced_symbols` is gone (zero callers, zero tests: testing dead API is worse
than removing it). `interval` is now `TimeFrame | None`, which makes a
wrong-typed call a `mypy` error instead of a green test.

Why a guard and not just the tests: the tests fix this fake. The guard is what
stops the next fake — and PR 0.5's own review had already added
`.claude/skills/pr-review/SKILL.md` row **E12** ("break the line the test
names and run") after PR 0.4b shipped a search box whose signal connections
could be deleted with 22 tests still green. This is the same disease in a
different place, found by that row four days later. A checklist row catches it
when somebody reviews; a guard catches it every time the gate runs.

## Regression test

Three pieces, and the order matters (`bug-fix-rule.md` §4). This defect is
"nothing would notice if the code stopped working", so the reproduction is
inverted: the failing evidence is the suite staying **green** while the code
is broken.

1. **Reproduction, before any fix** — break `was_asked_for` to `return True`,
   run the contract test plus all three consumers' files:
   `152 passed`. Captured above.

2. **The mechanism's test, written before the fix** —
   `test_fake_helpers_are_verified.py::test_a_fakes_extra_helpers_are_exercised_by_its_own_modules_tests`
   run against the tree as PR 0.5 left it, red for the right reason:

   ```
   src/.../fake_market_data_sync.py:63  FakeMarketDataSync.synced_symbols() — not on
       IMarketDataSync, and never called under tests/unit/modules/market_data/contracts/
   src/.../fake_market_data_sync.py:67  FakeMarketDataSync.was_asked_for() — not on
       IMarketDataSync, and never called under tests/unit/modules/market_data/contracts/
   1 failed, 14 passed
   ```

3. **The helper's behaviour** —
   `tests/unit/modules/market_data/contracts/test_market_data_sync_contract.py::TestTheFakesOwnQuery`,
   seven tests. Confirmed to reach the failure path by breaking
   `was_asked_for` to `return True` a second time, *after* they existed:

   ```
   FAILED ...::TestTheFakesOwnQuery::test_it_says_no_when_no_sync_was_asked_for_at_all
   FAILED ...::TestTheFakesOwnQuery::test_it_says_no_for_a_symbol_nobody_asked_about
   FAILED ...::TestTheFakesOwnQuery::test_the_interval_narrows_the_answer
   3 failed, 27 passed
   ```

   The two "no" cases are the ones that matter: a helper is only useful if it
   can decline. `test_the_interval_narrows_the_answer` covers the second
   cause — a dropped interval filter would otherwise let "a sync ran for
   BTCUSDT at 1m" pass for a sync of the daily candles.

Nothing temporary was added, so `bug-fix-rule.md` §3's keep-or-discard
decision has nothing to weigh: the evidence here is a test suite's own
pass/fail counts, not log output.
