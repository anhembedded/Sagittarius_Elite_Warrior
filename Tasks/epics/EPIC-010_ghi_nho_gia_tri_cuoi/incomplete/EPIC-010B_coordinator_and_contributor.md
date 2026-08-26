# EPIC-010B — `UiStateCoordinator`, the contributor contract, and the extension

**Status:** 🔵 Not started
**Repo:** **Engine** — design §8 steps 1-2
**Depends on:** `EPIC-010A`

## What

| Symbol | Notes |
| :--- | :--- |
| `IStateContributor` | `typing.Protocol` — `state_scope`, `capture_state()`, `restore_state(data)`. **Protocol, not an ABC**: presenters already inherit `BasePresenter` and `architecture-rule.md` §2 forbids multiple inheritance |
| `IStateDefaultsProvider` | ABC + the §4.3 resolution chain |
| `UiStateCoordinator` | `restore_into(c)`, `mark_dirty(c)`, `discard(c)`, `flush()` |
| `UiStateExtension` | `IExtension` — `register`/`boot`/`shutdown`; `shutdown()` flushes |
| `BasePresenter` additions | `_instance_uid = uuid4()`, a `state_scope` property, and **no-op** `capture_state`/`restore_state` defaults |

## The debounce is not code

Design §5.6.6 row 8, measured: `QTimer.setSingleShot(True)` then calling
`start()` on every change **restarts** the countdown — three rapid `start()`
calls produced exactly one `timeout`. So the coordinator does bookkeeping
(which contributors are dirty), not timing logic. ~800ms.

## Three boundary rules this task must not break

1. **`BasePresenter.__init__` must NOT call `restore_state()`.** Its own
   docstring forbids calling overridable methods there — the Template Method
   Trap. The child calls `self._restore_ui_state()` at the end of its own
   `__init__`, beside `_connect_ui_signals()`.
2. **The store is an OPTIONAL dependency.** `std_container.py:237` raises
   `DependencyResolutionError` when unregistered, so a bare `resolve()` would
   break every app and test that constructs a presenter without the extension.
   Guarded resolve → `NullStateStore`.
3. **`shutdown()`/`flush()` must never raise.** Catch `OSError`/`ValueError`,
   log once, move to `Degraded`. This is the `BUG-048` lesson: the shutdown path
   is not allowed to throw.

## Acceptance

- A presenter with no state extension registered constructs and disposes
  normally — mirroring `test_core_boot_does_not_require_persistence_extension`
- Debounce coalesces N changes into one write
- `flush()` with a failing store logs once and does not raise
- `dispose()` discards a `SESSION` scope; a `PERSISTENT` scope is unaffected
- No second presenter registry exists (design §3.2) — the coordinator learns
  about presenters through `BasePresenter`/`dispose()`, not its own list
