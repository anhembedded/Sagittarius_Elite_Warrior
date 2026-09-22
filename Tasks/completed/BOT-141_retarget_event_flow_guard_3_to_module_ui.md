---
description: The format of a standalone task under Tasks/backlog/ or an epic child under its incomplete/ directory (ONBOARDING §3). Copy it, fill every brace, delete this front matter and instructional comments.
---

# BOT-141 — Two sanity/architecture guards still point at the deleted `presentation/ui/screens/` tree

**Status:** ✅ Done (2026-09-22)
**Source:** Self-identified while landing `EPIC-025E` PR 4.4e (settings becomes a surface) — the last screen left `src/presentation/ui/screens/`, which made the tree empty for good and surfaced this guard's silent dormancy via `test_scanned_roots_are_not_empty.py`.
**Risk:** 🟡 — a real architectural rule (`EPIC-008G`'s "one event, one Feed, not two presenters guessing the same thing separately") has no live check until this lands.
**Complexity:** M — the scan target is easy; deciding what "screen" means under the module-owned layout, and excluding `presentation/ui/common/`'s Feeds correctly at the new addresses, needs its own look.
**Epic (optional):** None
**SPEC (optional):** None
**Depends on:** None

---

## 1. Context and problem
Two guards hardcode `src/presentation/ui/screens` as a scanned root, and `EPIC-025` Phase 4 has now deleted that tree for good — `trading`/`dashboard` left it in PR 4.4c, `backtest` in PR 4.4d, `settings` (the last screen) in PR 4.4e:

1. `tests/unit/test_event_flow_guards.py::test_one_event_is_not_subscribed_by_two_presenters` (Guard 3) — walks the tree looking for two different screens subscribing the same event class directly instead of going through one Feed. `.rglob()` on a missing path returns an empty iterator rather than raising, so this guard has been passing "vacuously" (checking nothing) since PR 4.4d, and PR 4.4e made it total. Its docstring now says so explicitly.
2. `tests/sanity/test_composition_root.py::test_every_screen_package_has_a_navigable_route` ("Mode 12") — `_screen_packages()` lists the subdirectories under the same now-deleted root and diffs them against the registered navigable routes, to catch a screen that exists on disk but nothing routes to. `.iterdir()` on a missing path raises `FileNotFoundError` outright (PR 4.4e guarded this to return `[]` instead, so the sanity suite does not crash — but the check itself is now dormant the same way Guard 3 is).

Both rules are still worth enforcing — Guard 3 caught a real bug in `EPIC-008G` (`HealthUpdatedEvent` subscribed by two presenters, each normalising it separately, until the Backtest copy drifted and dropped its `Container`); Mode 12 is the derived-from-structure check `test_every_navigable_route_constructs`'s own docstring says was missing before it existed (`BUG-019`, a Database-screen modal that could not construct, was unreachable to every test until this mode existed). They just need to look where screens actually live now. `tests/unit/architecture/scanned_roots_registry.py` retired both stale `("...", "src/presentation/ui/screens", "*.py")` rows in the same commit that made this dormancy total, rather than pretending either guard still checks something.

## 2. Acceptance criteria
- [x] Guard 3 and Mode 12 both scan the current screen-owning locations (`src/modules/*/ui/`, `src/shell/`, and whichever `src/support/ui_kit`-hosted screen-like widgets still apply) instead of the deleted `src/presentation/ui/screens/`. — `src/support/ui_kit` hosts no `*_screen.py` today (only `base_feed.py`/`health_feed.py`), so it is correctly not a scan root; it is exactly the shared-Feed exemption Guard 3 must not flag (see next bullet).
- [x] Guard 3 still excludes `presentation/ui/common/`'s Feeds (or their new address, if that tree has also moved by the time this lands) — a Feed is the one place a subscription is *supposed* to live, and the guard must not flag it. — the new address is `support/ui_kit/health_feed.py` (app-wide) and a per-module root file such as `modules/trading/ui/equity_feed.py` (shared by that module's own screens); `screen_owner()` returns `None` for both, excluding them from the duplicate-detection grouping.
- [x] A deliberately introduced duplicate `event_bus.on(SameEvent, ...)` call across two different module Presenters is caught red by the retargeted Guard 3, then the probe is reverted (mutation-verify per `testing-rule.md` §2). — verified live: appended `_bus_probe.on(BacktestCompletedEvent, print)` to `dashboard_screen.py` (already subscribed in `backtesting/ui/signal_wiring.py`), guard failed naming both owners, reverted, guard green again.
- [x] A deliberately introduced screen package under a module's `ui/` with no registered route is caught red by the retargeted Mode 12, then the probe is reverted. — verified live: added `src/modules/strategy/ui/_probe_screen.py` with an unregistered `route=`, Mode 12 failed naming the file, deleted, green again.
- [x] `tests/unit/architecture/scanned_roots_registry.py` carries the retargeted row(s) for both guard files.

## 3. Design
Decide what "screen" means for both checks under the module-owned layout before writing either scan: is `modules/trading/ui/dashboard/` one screen and `modules/trading/ui/trading/` a separate one (matching the old one-`screens/<name>/`-directory-per-screen shape), or does ownership now group differently now that a bounded-context module can host more than one screen and a contributed section (settings, dev-board probes) is not a "screen" at all? `tests/unit/architecture/ui_trees.py`'s `UI_TREES`/`UI_TREE_PATHS` is the existing "where is the UI" registry several *other* guards already read for the whole-tree question — reuse it if it fits, but check whether its granularity (whole `modules/trading/ui/` as one root) is coarse enough to hide a genuine two-screen duplicate, or a genuinely unrouted package, that used to be visible as a separate `screens/<name>/` directory. The two checks may end up sharing one "list of current screen packages" helper rather than each re-deriving it.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/unit/test_event_flow_guards.py` | Retarget Guard 3's scan; update its docstring to drop the "dormant" note once it scans real ground again. |
| `tests/sanity/test_composition_root.py` | Retarget `_screen_packages()`; drop the `if root.is_dir() else []` guard once it scans real ground again. |
| `tests/unit/architecture/scanned_roots_registry.py` | Add the retargeted root(s) back to both guards' rows. |

## 5. Testing
Mutation-verify per `pr-review` E12 / `testing-rule.md` §2 for both: break each guard on purpose (a cross-module duplicate subscription; an unrouted screen package under a module's `ui/`) and confirm it goes red for the right reason; restore and confirm green. `pytest tests/unit/test_event_flow_guards.py tests/unit/architecture/test_scanned_roots_are_not_empty.py -q` plus the sanity tier's own run for `test_composition_root.py`.

## Implementation notes (written when done)

**Design decision (§3's open question, resolved).** A "screen" is derived from
the file, not the directory: every screen since `EPIC-025E`/`F` is exactly one
`<name>_screen.py` building `ScreenContribution(..., route=<ROUTE>, ...)`, and
its directory depth already varies with how many screens its module owns
(`backtesting/ui/backtest_screen.py` sits at the module's `ui/` root — its only
screen — while `trading/ui/trading/trading_screen.py` and `trading/ui/
dashboard/dashboard_screen.py` each own a subdirectory). A new shared module,
`tests/unit/architecture/screen_files.py`, is the one place both guards read:

- `screen_roots()` — `src/modules/*/ui` (discovered by glob, not a hand-kept
  tuple — the same shape `ui_trees.py`'s own docstring says went stale four
  times) plus `src/shell`.
- `screen_files()` — every `*_screen.py` under those roots, each resolved via
  `ast` to the literal string its own `ScreenContribution(route=...)` passes
  (directly or through the file's own `NAME = "..."` constant). Directory-name
  matching was rejected: measured against the real tree, `database_screen.py`'s
  own route is `"data_management"`, which no name derived from its path or
  filename would produce.
- `screen_owner(path)` — the nearest ancestor directory (up to a screen root)
  that itself hosts a `*_screen.py`, or `None`. `None` is not "unowned", it is
  the shared-Feed exemption: measured against the real tree, every actual
  `.on(...)` call outside a screen's own subdirectory today is a per-module
  Feed (`trading/ui/equity_feed.py` and siblings, serving both `trading/` and
  `dashboard/`) or an app-wide one (`shell/system_failure_log.py`,
  `support/ui_kit/health_feed.py`) — exactly the pattern `architecture-rule.md`
  §6 calls "one normalising Feed and many displayers".

Guard 3 (`tests/unit/test_event_flow_guards.py`) and Mode 12
(`tests/sanity/test_composition_root.py::test_every_screen_package_has_a_navigable_route`)
both now read this module instead of `src/presentation/ui/screens/`.

**Registry.** `scanned_roots_registry.py`'s temporary `EMPTY_BY_DESIGN` row for
Mode 12 is removed (the tree is no longer scanned at all, not scanned-and-
found-empty); its permanent row for `test_no_cross_screen_imports.py` is
untouched (that guard's own ban is unrelated to this task). Both retargeted
guard files gained one row per screen-owning root that exists today
(`src/modules/{backtesting,market_data,strategy,trading}/ui`, `src/shell`) —
a glob cannot sit in this literal registry, so a future module needs its own
row here on the pull request that gives it a screen, the same caveat
`UI_TREE_ROWS` already carries for the five UI-styling guards.

**Verification.** Measured on the real tree before writing the fix: today's
only genuine `.on(...)` call sites under the new roots are in
`backtesting/ui/signal_wiring.py`, `market_data/ui/data_management_presenter.py`
+ `sync_progress_feed.py`, `trading/ui/{equity,market_tick,order,signal}_feed.py`,
and `shell/system_failure_log.py` — zero collisions, guard passes clean.
Mutation-verify (both reverted, see acceptance criteria above) proved Guard 3
and Mode 12 each go red for the right reason and green again.

`pytest tests/unit/architecture tests/unit/test_event_flow_guards.py
tests/sanity -q` — 433 + 3 (already inside the architecture count via the
registry's own parametrization) + 29, all green; full `tests/unit -q` — 4909
passed. `ruff check`/`ruff format --check` clean on all touched and new files.
No production code (`src/`) touched — this is test-infrastructure only.
