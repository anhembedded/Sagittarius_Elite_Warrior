---
description: The format of a standalone task under Tasks/backlog/ or an epic child under its incomplete/ directory (ONBOARDING §3). Copy it, fill every brace, delete this front matter and instructional comments.
---

# BOT-141 — Two sanity/architecture guards still point at the deleted `presentation/ui/screens/` tree

**Status:** 🔵 Backlog
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
- [ ] Guard 3 and Mode 12 both scan the current screen-owning locations (`src/modules/*/ui/`, `src/shell/`, and whichever `src/support/ui_kit`-hosted screen-like widgets still apply) instead of the deleted `src/presentation/ui/screens/`.
- [ ] Guard 3 still excludes `presentation/ui/common/`'s Feeds (or their new address, if that tree has also moved by the time this lands) — a Feed is the one place a subscription is *supposed* to live, and the guard must not flag it.
- [ ] A deliberately introduced duplicate `event_bus.on(SameEvent, ...)` call across two different module Presenters is caught red by the retargeted Guard 3, then the probe is reverted (mutation-verify per `testing-rule.md` §2).
- [ ] A deliberately introduced screen package under a module's `ui/` with no registered route is caught red by the retargeted Mode 12, then the probe is reverted.
- [ ] `tests/unit/architecture/scanned_roots_registry.py` carries the retargeted row(s) for both guard files.

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
{Fill in when done.}
