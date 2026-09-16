# BUG-125 — `ILogger` has no `exception()`, and its second positional argument is silently dropped

- **Reported:** 2026-09-16, found by following [`CS-001`](../../../Docs/CASE_STUDIES/CS-001_a_double_that_could_not_disagree.md)'s
  *"where else this is still open"* list — the first thing that list was used for.
- **Severity:** 🟠 P2 — the crash is on the developer-mode switch's **failure** path, so a user
  only meets it when the config write already failed; the printf half is a log that says less
  than it appears to, on the success path, every time.
- **Status:** ✅ Fixed 2026-09-16 — root-caused, reproduced against the real logger,
  regression-tested (the *existing* test became able to fail), guard extended.

## Symptom

Two defects in `src/shell/welcome/welcome_presenter.py`, both in
`_on_dev_mode_toggled`, neither reached by the suite:

```python
except (OSError, ValueError):
    self.logger.exception(                      # 1. AttributeError
        "[WELCOME] Could not save developer mode = %s. ...", enabled
    )
    ...
self.logger.info("[WELCOME] Developer mode written as %s.", enabled)   # 2. prints "%s"
```

Reproduced against the real `StdLogger`:

```
--- 1. exception() ---
AttributeError: 'StdLogger' object has no attribute 'exception'
--- 2. printf-style positional arg ---
2026-09-16 03:11:40,136 - App - INFO - [WELCOME] Developer mode written as %s.
```

The first one is the worse of the two, and not because it raises: the whole purpose of that
`except` branch — its docstring says so — is to leave the switch honest when the write fails.
Instead the slot died, so a failed write left the toggle showing the value the user clicked.

## Root cause

The engine's `ILogger` declares exactly `info`, `warning`, `error`, `debug`, `critical`, `trace`,
each `(message: str, extra: dict[str, Any] | None = None)`. `StdLogger` implements no more.

1. `exception()` is `logging.Logger`'s method, not the port's. The file was written against the
   stdlib logger's mental model while holding `container.resolve(ILogger)`.
2. `info(msg, value)` has no printf pass-through. The value binds to `extra`, which is typed
   `dict | None`, and the placeholder is emitted verbatim.

Same shape as [`BUG-124`](completed/BUG-124_welcome_start_called_publish_on_the_engine_event_bus.md)
one line above it in the same file, and invisible for the same two reasons: `IContainer.resolve`
returns `Any`, and the test's container fixture answered `Mock()` for every port it did not name —
so `Mock().exception(...)` recorded happily. **The test that drove this exact line
(`test_a_failed_save_offers_no_restart_and_puts_the_switch_back`) was green.**

Blast radius, measured rather than assumed — every `logger.*` call site in `src/` + `scripts/`
split by which logger the name is bound to:

```
241 call sites: 196 stdlib (logging.getLogger — it DOES have exception), 14 ILogger, 31 other
ILogger sites calling a method ILogger lacks:  1   <- this bug
ILogger sites passing printf positional args:  1   <- this bug
```

`backtest_presenter.py`'s nine `self._logger.log_*()` calls are **not** instances: that attribute
is a `BacktestEventLogger`, a different class with its own domain verbs. That is also why the
guard below is keyed on `self.logger` inside a `BasePresenter` subclass and not on the name
`logger`: the name means three different types in this tree.

## Fix

- `self.logger.error(f"... {exc!r}")` — the exception text goes in the message because `ILogger`
  has no `exc_info`; its second parameter is `extra`.
- `self.logger.info(f"[WELCOME] Developer mode written as {enabled}.")`.
- The container fixture in `tests/unit/shell/test_welcome.py` now resolves a **real** `StdLogger`
  instead of falling through to `Mock()`.
- `tests/unit/architecture/test_engine_port_calls_are_real.py` (renamed from
  `test_event_bus_calls_are_real.py`, which `BUG-124` created) gained three tests: a presenter
  may not call a logger method `ILogger` lacks, may not pass a second positional argument, and
  the scan must not go empty. Both new checks were probed by re-introducing each defect.

## Regression test

No new test file. `test_a_failed_save_offers_no_restart_and_puts_the_switch_back` already drove
the failing line — it simply could not fail, because the logger was a `Mock`. Giving the fixture
the real `StdLogger` made it red with the production error
(`AttributeError: 'StdLogger' object has no attribute 'exception'`), and the fix made it green.

That is the shorter lesson of `CS-001` restated: the test tier and the assertion were already
right. Only the double was wrong.
