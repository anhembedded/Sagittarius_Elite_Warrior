# BUG-123 — the mocked candle grid moved between two calls, so a gate run could fail on the clock alone

- **Reported:** 2026-09-16 (found by the `EPIC-025` PR 1.6a gate run, not by a user)
- **Severity:** Medium — no shipped behaviour is wrong; the gate itself was unreliable,
  which is worse than it sounds: a suite that fails at random teaches everyone to re-run
  instead of read, and `ci-rule.md` §3 exists because that habit has hidden real defects
  here before.
- **Status:** ✅ Fixed 2026-09-16 — root-caused, reproduced deterministically,
  regression-tested (red before, green after), full gate green.

## Symptom

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full` failed on a tree whose diff touched
nothing near the chart:

```
FAILED tests/integration/presentation/ui/test_dev_board_load_more.py::
       test_scrolling_near_the_left_edge_prepends_older_candles

>       assert len(card._raw_history) == history_before + MOCK_KLINE_COUNT
E       assert 9 == (5 + 5)
E        +  where 9 = len([(1789522260.0, …), (1789522320.0, …), (1789522380.0, …),
E                          (1789522440.0, …), (1789522500.0, …), (1789522560.0, …), ...])
```

Four candles were prepended where the test expects five. The same test had passed in the
immediately preceding run of the same suite on almost the same tree
(`logs/ci-local-20260916-013216.log` — green there,
`logs/ci-local-20260916-013751.log` — red here), five minutes apart.

Read the numbers and the shape is already visible: the four rows that arrived are
`…260`, `…320`, `…380`, `…440`, spaced 60 s, and the oldest row the chart already held is
`…500`. The fifth row the test meant to add was `…500` itself — the one already in the
store.

## Root cause

`tests/integration/presentation/ui/mock_klines.py::build_mock_klines` anchored its series
to the clock **on every call**:

```python
base_time = datetime.now(UTC).replace(second=0, microsecond=0) - timedelta(
    minutes=MOCK_KLINE_COUNT
)
```

Two different callers read that clock at two different moments:

1. `tests/integration/presentation/ui/conftest.py:138` — the `seeded_history` fixture calls
   it once per symbol to seed the store, during setup.
2. `tests/integration/presentation/ui/test_dev_board_load_more.py:47` —
   `_older_mock_klines()` calls it again **in the test body**, to find `oldest_shown` and
   build the page that sits immediately below it.

`.replace(second=0, …)` truncates to the minute, so the two calls agree for most of any
given minute and disagree completely once one rolls over. When it rolls over, call 2's grid
is one minute later than call 1's, `oldest_shown` is one minute later than the row actually
in the store, and the "older" page it derives is shifted with it — its newest row lands
exactly on the row the chart already holds. The store already has that candle, so four of
the five prepend, and the assertion is off by one.

Reproduced deterministically rather than waited for, by handing the module a clock that
jumps a minute per call:

```
first : 2026-09-16 01:34:00+00:00 -> 2026-09-16 01:38:00+00:00
second: 2026-09-16 01:35:00+00:00 -> 2026-09-16 01:39:00+00:00
same grid? False
older page newest: 2026-09-16 01:34:00+00:00   oldest shown: 2026-09-16 01:34:00+00:00
overlaps? True
```

**A second instance of the same defect, which nothing was watching.** `seeded_history`
loops the five `SEEDED_SYMBOLS` in one fixture, one `build_mock_klines` call each — so a
rollover mid-loop leaves two symbols in the same store a minute apart. No test noticed,
because each symbol reads back consistently on its own; the regression test below now
fails on it.

The clock read itself was correct to introduce (`EPIC-025` PR 1.1a: a fixed `2024-01-01`
series fell outside the Data Range picker's default window once `IHistoricalKlines` started
honouring the range, and every history test went quiet). What was wrong is *how often* it
is read.

## Fix

One anchor per process, at import, in the module that owns the series:

```python
_SERIES_ANCHOR = datetime.now(UTC).replace(second=0, microsecond=0) - timedelta(
    minutes=MOCK_KLINE_COUNT
)
```

`build_mock_klines` reads that constant instead of the clock. This is the mechanism, not
the call site: every current and future caller derives the same grid for free, so a test
can build a page adjacent to what another caller stored — which is the property the
load-more tests were relying on without anything guaranteeing it. The alternative shape,
"pass the anchor in at each call site", is the per-caller patch `bug-fix-rule.md` §2
forbids: it would leave the next caller free to read the clock again.

Both reasons the clock was read for survive: the series still sits inside any
recent-window default, and — since a frozen anchor only ever recedes as a session runs —
it still never claims a candle from the future. A third test pins exactly that, so the
freeze cannot quietly become a series in the future in some longer suite.

## Regression test

`tests/integration/presentation/ui/test_mock_klines_is_one_grid.py`, three tests, written
before the fix and confirmed red for the right reason:

| Test | Before the fix | After |
| :--- | :--- | :--- |
| `test_two_calls_in_one_process_return_the_same_grid` | ❌ `first != second` — the two grids are a minute apart | ✅ |
| `test_every_seeded_symbol_lands_on_the_same_grid` | ❌ `assert 5 == 1` — five symbols, five grids | ✅ |
| `test_the_series_still_ends_in_the_past` | ✅ (it guards the fix, not the bug) | ✅ |

The clock is injected by `monkeypatch`-ing the module's `datetime` with a `_RollingClock`
that advances a minute per `now()`, so the failure is deterministic instead of one
sixtieth of the wall clock. Tier: it sits beside its subject in
`tests/integration/presentation/ui/`, which is the package `mock_klines.py` belongs to and
moves with — the assertions themselves are pure-function reads of a builder, and they need
no fixture from that tier's `conftest.py`.
