# CS-001 — A double that could not disagree

`BUG-124` · shipped in PR 1.5a · Start on the Welcome screen did nothing.
[report](../../Tasks/bug_report/completed/BUG-124_welcome_start_called_publish_on_the_engine_event_bus.md)
· follow-up [`BUG-125`](../../Tasks/bug_report/completed/BUG-125_ilogger_has_no_exception_and_printf_args_are_dropped.md): reading this page's own list below found two more, same file

```python
self.event_bus.publish(StartRequested())   # engine's IEventBus has emit(), not publish()
```

## Why nothing caught it

| Net | Why silent | Still open? |
| :--- | :--- | :--- |
| mypy (does gate `src/shell/`) | `IContainer.resolve -> Any`, so every attribute on `event_bus` typechecks | yes — 4 such attrs on `BasePresenter`; `src/presentation/` excluded outright |
| unit test | its `_Bus` double had `publish` + `on` + `subscribe`: two interfaces plus an invented verb. A double written from the caller always passes | yes — nothing checks a double's shape against a real interface |
| sanity tier | imports `use_cases`/`strategies`, not `shell/`; an `AttributeError` in a Qt slot needs the signal to fire | yes |

## The fix

- `self._bus.emit(...)` — also the right design: `publish` takes an `IDomainEvent`, `StartRequested` is a UI intent.
- `self._bus: IEventBus = self.event_bus` — narrows the `Any`; re-adding `publish` now fails mypy.
- `tests/unit/architecture/test_engine_port_calls_are_real.py` — every bus call, and every `self.logger` call in a presenter, vs the port's real methods read off the class. Matched by **name**: immune to the `Any`.
- Double is now `_RecordingBus(MemoryEventBus)` — real bus, real subscription.

## Where else this is still open

- Any `container.resolve()` result is `Any` until named with its type. **Checked:** `logger` found `BUG-125`; `config` and `dispatcher` are clean but name three types each, so no guard can be keyed on them.
- Every hand-written double in `tests/` can be shaped from the caller instead of the interface — and a container fixture returning `Mock()` for an unlisted port is the same thing by default, which is how `BUG-125` stayed green.
- Two publishing verbs coexist by design: `IEventBus.emit` (6 sites), `IEventPublisher.publish` (16).

## Take
Derive a double from the interface, or use the real thing. `Any` at a seam switches off type
checking past it. "Gate is green" describes only what the gate checks.
