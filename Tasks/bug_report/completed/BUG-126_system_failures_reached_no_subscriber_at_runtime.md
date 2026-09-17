# BUG-126 — Every swallowed failure reached no subscriber: `SystemErrorFeed` was never constructed

- **Reported:** 2026-09-16, found while measuring `src/presentation/ui/common/` for the next
  `EPIC-025` extraction — not by a user, because the defect's whole nature is that it produces no
  symptom a user could report.
- **Severity:** 🔴 High — it is `EPIC-008` §1's own P1 finding, still true two epics after that
  epic closed it. A UI slot that raised and a background task that died left no trace anywhere a
  user, a reporter, or the CI log scan could see.
- **Status:** ✅ Fixed 2026-09-16 — root-caused, reproduced against the real object graph,
  regression-tested (red before, green after), mechanism guarded, log line seen to emit through
  the real logging config, case study written
  ([`CS-002`](../../../Docs/CASE_STUDIES/CS-002_the_subscriber_nobody_built.md)).

## Symptom

There is no traceback to paste, and that is the finding. `safe_ui_action` publishes
`UiActionFailedEvent` with a full traceback whenever a UI slot raises; the engine's `TaskManager`
publishes `TaskFailed` whenever a background task dies. Both were published into an empty room:

```
$ grep -rn "UiActionFailedEvent" src scripts --include=*.py
src/presentation/ui/common/system_error_feed.py:57:  self._events.on(UiActionFailedEvent, ...)   # the only subscriber

$ # ... and every code reference to the class that owns that line:
$ #     (none — see the AST measurement below)
```

`BUG-124` is the concrete cost, measured on this same repository a day earlier. Pressing **Start**
on the Welcome screen raised inside a Qt slot, and the user's log carried the traceback only
because `app_bootstrapper._install_exception_handler` happens to catch `sys.excepthook`. Anything
raised inside `safe_ui_action` — which catches the exception rather than letting it reach the
hook — produced nothing at all.

## Root cause

Not a line of logic. `SystemErrorFeed` (`EPIC-008G`) normalised both events correctly and its unit
test file was green. **Nothing ever constructed it.** Its subscriptions live in `BaseFeed.__init__`,
so a class nobody builds subscribes to nothing.

Measured from the AST, not from text — the distinction is the second half of the root cause:

```
9 classes in src/ subscribe to the bus. Code references to each, elsewhere in src/+scripts/:
  BinanceBotModule 1 · DataManagementPresenter 2 · EquityFeed 2 · HealthFeed 1
  MarketTickFeed 2 · OrderFeed 2 · SignalFeed 2 · SyncProgressFeed 3
  SystemErrorFeed 0        <- the bug
```

A text search says `SystemErrorFeed` has two references. Both are **docstrings**:
`system_error_report.py`'s prose, and one Vietnamese line in `order_feed.py`. That is exactly the
measurement that produced HLD §3.5's *"Live, do not delete: `ui/common/system_error_feed`
(imported by `order_feed.py`)"* — a claim that was never true, written in the round that was
explicitly a re-measurement, and which then protected the dead class from two rounds of dead-code
review.

Why the Qt feed was the wrong shape for this job in the first place — three reasons, each of which
also explains how it came to be constructed by nobody:

1. A feed is constructed **by a screen**. Every other feed in the tree is (`OrderFeed` by two
   presenters, `SyncProgressFeed` by three). This one's fact belongs to no screen — it is app-wide
   — so there was no screen whose job it obviously was, and it became nobody's.
2. It needed a **display** to connect its signal to. This application has no app-wide one: every
   log panel belongs to a screen. So even wired, it would have needed N connections for N screens,
   which is the per-Presenter duplication `fix-bug-rule.md` §2 forbids.
3. It is **Qt**, so the CLI entry point — which has no `QApplication` — could never have had it,
   although `TaskFailed` is published just as often headlessly.

## Fix

The mechanism, at the one layer that serves every entry point and every current and future screen
for free.

1. **`src/shell/system_failure_log.py`** — `SystemFailureLog`, constructed once by the composition
   root, **before `boot()`** (an extension that fails during boot is exactly the failure worth
   seeing). No Qt: a logger is thread-safe, so it subscribes directly with no `QtEventBridge`, and
   the headless path gets the same visibility as the GUI. Reports at `ERROR` with the greppable
   `[system-failure]` tag — the sink `--dev`/`--debug` write, a reporter pastes, and
   `ci-local.ps1`'s "Run Log Scan" step greps.
2. **`src/shell/system_error_report.py`** — `SystemErrorReport` and its two normalisers, moved out
   of `presentation/ui/common/` (which the shell may not import) and rewritten to read the two
   engine dataclasses **by field** instead of `getattr(event, "field", default)`: both events have
   only required fields, so every default was unreachable and the type checker could not help.
   `core/contracts/` was tried first and is wrong — it is a Qt-free zone and `UiActionFailedEvent`
   lives under the engine's `pyside_mvc` extension, so `test_module_domain_is_qt_free.py` refused
   it, correctly.
3. **`SystemErrorFeed` deleted.** Nothing displayed its signal, and `base_feed.py`'s own rule is to
   promote a fact to a feed when the **second** consumer appears. Promoting before the first one
   did is what this cost. Re-adding it later is a subscription and a signal over the same report
   type, with a real consumer to justify it.
4. **The guard: `tests/unit/architecture/test_a_bus_subscriber_is_constructed.py`.** A class that
   calls `.on(...)` must be named elsewhere in `src/`+`scripts/`, read from the AST so a docstring
   cannot satisfy it. *Named* rather than *called*, because a screen class is handed to a registry
   as a bare reference; measured against this tree, that threshold separates cleanly — 8 reachable,
   1 orphan, 0 false positives. Its third test feeds it a synthetic orphan mentioned only in prose
   and requires it to fail, then the same orphan with one construction and requires it to pass.

## Regression test

`tests/unit/shell/test_system_failure_log.py::test_the_real_graph_subscribes_somebody_to_both_failure_events`,
written before the wiring and confirmed red for the right reason:

```
assert ['UiActionFailedEvent', 'TaskFailed'] == []
```

Tier: the real object graph from `create_app()`, and that choice is the point. A test that
constructs the subscriber itself **cannot** fail for this bug — it supplies the one step production
was missing, which is how the deleted `test_system_error_feed.py` passed for two epics over a dead
class. "Somebody is listening" is a property of the graph and of nothing smaller.

Three more tests cover what the subscriber does once it exists (a failing slot logged with its
traceback, a failed task logged with its cause, and nothing reported below `ERROR` where the log
scan would not see it), and `tests/unit/shell/test_system_error_report.py` covers the normalisers.
Together they inherit every guarantee the deleted feed test asserted; nothing was dropped.

`logging-rule.md` §9's check, because a diagnostic never seen to emit does not exist — the real
`create_app()` graph, `--dev`, reading `logs/dev-*.log`:

```
2026-09-16 05:10:39,488 - App - ERROR - [system-failure] UI error in _on_start_clicked: AttributeError: 'MemoryEventBus' object has no attribute 'publish'
2026-09-16 05:10:39,488 - App - ERROR - [system-failure] _on_start_clicked detail:
Traceback (most recent call last):
  File 'welcome_presenter.py', line 76
2026-09-16 05:10:39,488 - App - ERROR - [system-failure] Background task 'historical-sync' failed: ValueError: grid drift
```

That is `BUG-124`'s own failure, replayed through the path that had been silent.
