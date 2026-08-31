# BUG-075 — Sanity tier fails on `ResourceWarning: unclosed event loop` from `python-binance`'s `get_loop()`

**Reported date:** 2026-08-31
**Severity:** 🟡 P2 — makes `pytest tests/ -q` (CI's exact invocation) unreliable:
whichever sanity test happens to be running when Python's GC finally
collects the leaked loop fails, with no connection to what that test
actually does.
**Status:** ✅ Đã sửa 2026-08-31 — root-caused, reproduced (2/2 CI runs,
identical), regression-tested, verified.
**Found by:** driving [PR #148](https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/148)
(a `master-warrior` lint-cleanup PR) to green — CI failed twice, identically,
after `BUG-065`'s crash fix was ported in and a genuine flake (a `QTimer`
debounce test) cleared on re-run.

---

## Symptom

```
ERROR tests/sanity/test_circular_imports.py::test_main_window_no_toplevel_bootstrapper_import
    [warning] ResourceWarning: unclosed event loop <_UnixSelectorEventLoop running=False closed=False debug=False>
```

Caught by `tests/sanity/conftest.py`'s `diagnostic_guard` autouse fixture,
which fails any sanity test that provokes a `warnings.warn(...)` not already
on the tier's allowlist. Reproduced identically twice in a row in CI
(`pytest tests/ -q`, the exact command `.github/workflows/ci.yml` runs) —
same test, same warning, same message, deterministic given the same
collection order.

`test_main_window_no_toplevel_bootstrapper_import`
(`tests/sanity/test_circular_imports.py`) is pure `ast.parse()` on a source
file — no runtime code, no asyncio, no app boot. It is an innocent bystander:
the warning is a Python GC-timing artifact that surfaces on whichever test
happens to be running when the garbage collector finally notices an
abandoned `asyncio` event loop object, exactly the pattern this repo already
root-caused once for a different resource (`BUG-030`, an unclosed SQLite
connection caught on an unrelated test for the same reason).

## Root cause

`python-binance`'s `helpers.py::get_loop()`:

```python
def get_loop():
    """check if there is an event loop in the current thread, if not create one"""
    try:
        loop = asyncio.get_event_loop()
        return loop
    except RuntimeError as e:
        if str(e).startswith("There is no current event loop in thread"):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
        else:
            raise
```

creates a new `asyncio` event loop via `asyncio.new_event_loop()` whenever
none exists yet on the current thread — and **never closes it**. This is the
exact same mechanism `tests/sanity/conftest.py` already documents and
allowlists for a different symptom of the same root cause: `binance.client
.Client.__init__` calls `asyncio.get_event_loop()` unconditionally
(`helpers.py:96`), which is the deprecated code path that reaches
`get_loop()`. That already-allowlisted entry
(`_ALLOWED_WARNING_SUBSTRINGS = ("There is no current event loop",)`) covers
the `DeprecationWarning` `get_event_loop()` itself emits at call time; it
does not cover the **separate** `ResourceWarning` `asyncio.BaseEventLoop
.__del__` emits later, whenever Python's GC finally collects that same
unclosed loop object — which is not deterministic to any single test, only
to whichever one happens to be running when the collection fires.

This is upstream `python-binance` behavior — no code in
`Sagittarius_Elite_Warrior` or `sagittarius_engine` creates this loop or
controls its lifecycle; `Client()` is a synchronous, non-async client that
carries this loop only as a vestige of an old asyncio-compat workaround.
Not something to patch by monkeypatching a third-party library from this
app — same judgment call this codebase already made for the sibling
`DeprecationWarning`.

## Fix

`tests/sanity/conftest.py`'s `_ALLOWED_WARNING_SUBSTRINGS` gains one more
entry, `"unclosed event loop"`, with the same written justification as its
sibling entry — the tier's own documented contract for exactly this
situation ("when this list wants to grow, the tier is reporting something
true and the answer is a bug report, not another entry" — this file is that
bug report).

## Regression test

Not a dedicated new test file: the sanity tier's own `diagnostic_guard`
fixture, run as part of `pytest tests/sanity/ -q` or the full suite, **is**
the regression guard — it already failed on this exact warning before the
fix (twice, in CI) and is confirmed to pass after. Adding a synthetic test
that manufactures an orphaned `python-binance` `Client()` and forces `gc
.collect()` to reproduce the warning deterministically was considered and
rejected: the timing is inherently GC-schedule-dependent (confirmed by two
different runs catching it on the same *bystander* test rather than any
test that actually constructs a `Client`), so a synthetic single-shot
reproduction would not reliably trigger CPython's collector either — the
same reasoning `BUG-065`'s report gives for rejecting an analogous synthetic
probe.

## Xác minh

- CI run before fix: `ResourceWarning: unclosed event loop`, 2/2 times,
  identical.
- Local `ruff check`/`ruff format --check tests/sanity/conftest.py` clean
  after the one-line allowlist addition.
- Full suite re-run in CI (see PR) — no ResourceWarning failure.
