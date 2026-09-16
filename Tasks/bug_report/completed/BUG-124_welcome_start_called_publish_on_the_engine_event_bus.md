# BUG-124 — Start on the Welcome screen did nothing: `publish()` called on the engine's event bus

- **Reported:** 2026-09-16 by the user, running the real app
- **Severity:** 🔴 High — the app opens on Welcome (ADR D13) and **Start is the only way off it**.
  Nothing crashed visibly: the button logged its intent, raised an uncaught exception on the next
  line, and left the user on the same screen with no message.
- **Status:** ✅ Fixed 2026-09-16 — root-caused, reproduced at the unit tier against the real bus,
  regression-tested (red before, green after), mechanism guarded, case study written
  ([`CS-001`](../../../Docs/CASE_STUDIES/CS-001_a_double_that_could_not_disagree.md)).

## Symptom

The user's own log, pressing **Start**:

```
2026-09-16 09:49:52,772 - App - INFO - [WELCOME] Start requested.
2026-09-16 09:49:52,773 - App - ERROR - Uncaught UI Exception:
    'MemoryEventBus' object has no attribute 'publish'
Traceback (most recent call last):
  File ".../src/shell/welcome/welcome_presenter.py", line 76, in _on_start_requested
    self.event_bus.publish(StartRequested())
    ^^^^^^^^^^^^^^^^^^^^^^
AttributeError: 'MemoryEventBus' object has no attribute 'publish'
```

Read the two lines in order: the Presenter logged `[WELCOME] Start requested.` and then died on
the next statement. So the log said the button worked while the screen did not change — the
worst shape a failure can take, because the diagnostic agrees with the user's intention rather
than with what happened.

Everything before it in the boot log is healthy: 9 modules, 6 screens, the `dev_probe` correctly
dropped because `dev.mode` is off. Nothing about the boot is implicated.

## Root cause

`src/shell/welcome/welcome_presenter.py` called a method that does not exist on the object it
holds.

`BasePresenter.event_bus` is the **engine's** `IEventBus`
(`sagittarius_engine/interfaces/i_event_bus.py`), whose publishing verb is **`emit`**. The
application also has a publishing port of its own, `IEventPublisher`
(`src/core/contracts/i_event_publisher.py`), whose verb is **`publish`** and whose adapter
(`src/infrastructure/engine_adapters/event_publisher_adapter.py`) is the one place that translates
`publish(event)` into `event_bus.emit(event)`. The Presenter mixed the two: the app port's verb,
on the engine's object.

Measured rather than assumed — every bus call in the app, by verb:

```
     20 on
      6 emit
      1 publish      <- the bug, the only one in the tree
```

The two are not interchangeable even in principle: `IEventPublisher.publish` takes an
`IDomainEvent`, and `StartRequested` is deliberately **not** one — it is a UI intent, which is
exactly why the shell raises it on the bus that `app_bootstrapper` subscribes to with
`event_bus.on(StartRequested, ...)`. So `emit` is not merely the working spelling, it is the
correct design; routing this through `IEventPublisher` would have been wrong.

### Why three safety nets were silent

This is the part that generalises, and it is written up in full as
[`CS-001`](../../../Docs/CASE_STUDIES/CS-001_a_double_that_could_not_disagree.md).

1. **mypy.** `IContainer.resolve` is declared `(abstract: type[Any]) -> Any`, so
   `BasePresenter.event_bus` is `Any` and every attribute access on it typechecks. `src/shell/`
   *is* inside the mypy gate — the gate ran on this file and passed.
2. **The unit test.** `tests/unit/shell/test_welcome.py` handed the Presenter a hand-written
   `_Bus` defining `publish`, `on` **and** `subscribe` — the union of two different interfaces
   plus a verb that exists on neither. A double written from the caller's needs cannot disagree
   with the caller.
3. **The sanity tier.** `tests/sanity/test_composition_root.py` imports every module under
   `application/use_cases` and `domain/strategies`; it does not import `src/shell/` wholesale,
   and an `AttributeError` inside a Qt slot needs the signal to fire, not the module to import.

## Fix

Three changes, because the one-character fix would have left all three reasons above intact.

1. **The call, corrected:** `self._bus.emit(StartRequested())`.
2. **The `Any` narrowed where it matters.** The Presenter holds the bus under an annotation —
   `self._bus: IEventBus = self.event_bus` — so the call is back under the type gate. Verified by
   re-introducing `publish` on that line: mypy now reports
   `"IEventBus" has no attribute "publish"`, where before the annotation the same edit was clean.
3. **A guard for the class, not the instance.**
   `tests/unit/architecture/test_event_bus_calls_are_real.py` reads every call on a bus-shaped
   attribute across `src/` and `scripts/` and compares the method name with `IEventBus`'s real
   interface, read off the class at runtime. It matches by **name**, deliberately: that is what
   makes it immune to the `Any` which defeated mypy. Probed by re-introducing the bug — it fails
   naming `src/shell/welcome/welcome_presenter.py:95: _bus.publish()` — and a second test fails
   if its subject count collapses, so it cannot end up reading nothing.

## Regression test

`tests/unit/shell/test_welcome.py::TestThePresenter::test_start_becomes_an_intent_on_the_bus`,
rewritten onto the **real** bus before the fix and confirmed red for the right reason:

```
AttributeError: '_RecordingBus' object has no attribute 'publish'. Did you mean: 'published'?
```

That is the production traceback, reproduced at the unit tier. The hand-written `_Bus` was
replaced by a `_RecordingBus(MemoryEventBus)` that records through a real subscription, so every
method the Presenter reaches for must exist. The assertion got **stronger** as a side effect: it
now also proves the publisher's event key and the subscriber's event key agree — the engine
derives both from `__qualname__` — which the old double could say nothing about.

Tier: unit, and that is the right one here. The failure is in a Presenter slot with a real
collaborator available for free; a sanity-tier boot would also catch it but would say less about
where. What the old test got wrong was not the tier, it was the double.
