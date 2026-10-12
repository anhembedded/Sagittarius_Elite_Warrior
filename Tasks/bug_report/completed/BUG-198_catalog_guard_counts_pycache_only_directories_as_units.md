# BUG-198 — The capability-catalog guard fails on a checkout that still holds a deleted package's `__pycache__` shell

- **Reported:** 2026-10-12 (a session reading master `d0410c4`; the owner's Windows checkout very likely fails the same way)
- **Severity:** 🟢 P3 — a green CI hides a red local run, so a developer is told a support unit has no `Capability:` block for a package that no longer exists; no product behaviour is affected
- **Status:** ✅ Fixed (2026-10-12)
- **Board:** The capability-catalog guard failed locally on `src/support/ui_kit/embed` and `kit`, directories EPIC-033M deleted whose `__pycache__` survived `git pull`; fixed by counting only directories that hold Python source as units (and as module packages).
- **Context:** Architecture guards (`tests/unit/architecture/`) → `EPIC-037A` capability catalog → support-unit discovery
- **Environment:** Linux developer checkout of master `d0410c4` that had once held `src/support/ui_kit/embed` and `kit`; CI (clean checkout) passes.

## Reproduction
1. Check out a revision that has `src/support/ui_kit/embed/` and `kit/`, run the tests, then update to a revision that deletes them (the bytecode caches are untracked, so git leaves the directories).
2. `pytest tests/unit/architecture/test_every_support_package_is_in_the_catalog.py::test_every_support_unit_is_in_the_catalog`. Expected: pass. Actual: fails. Always reproduces with such a shell; never on a clean clone.

## Symptom
```
AssertionError: a support unit has no `Capability:` block ...
    - src/support/ui_kit/embed
    - src/support/ui_kit/kit
```
Both directories were untracked and held only `__pycache__/` and empty subdirectories.

## Root cause
`tests/unit/architecture/capability_catalog_checks.py::unit_directories` treated every directory at depth 1 or 2 under `src/support/` as a unit (`is_dir()` minus the roll-up names), so a shell with no source was a unit that, having no `Capability:` block, failed the guard. The same pattern, `iterdir()` + `is_dir()` taken as "a package exists", was in `test_module_declarations.py::_packages_on_disk`, which would report a stale `src/modules/<name>` as an undeclared module. `BUG-129`/`CS-005` fixed the same blind spot for other guards by asking git; these two were not on that list. The net that stayed silent is CI itself, which only ever sees a clean checkout.

## Fix
New `tests/unit/architecture/source_presence.py::holds_python_source` (a directory holds at least one `.py` file, directly or below, ignoring `__pycache__`). `unit_directories` and `_packages_on_disk` both call it, so the definition of "a package that exists" has one home. Source-based rather than git-based on purpose: a new, not yet staged package is still counted. The other `iterdir()` sites were read: `test_no_cross_screen_imports.py` goes on to `rglob("*.py")` and finds nothing in a shell; the rest are existence checks of a fixed root.

## Regression test
`tests/unit/architecture/test_source_presence.py::test_a_stale_shell_is_not_a_support_unit` and `::test_a_stale_shell_is_not_a_module_package` build a temporary tree with a real package beside a `__pycache__`-only directory. Both failed before the fix (`gone` counted as a unit / package) and pass after. The two helper tests pin `holds_python_source` itself.

## Verification
- Red before, green after, as above; the guard and its probes (`test_every_support_package_is_in_the_catalog.py`, `test_capability_marker_probes.py`, `test_module_declarations.py`) pass with `src/support/ui_kit/embed/__pycache__` and `kit/sub` recreated on disk.
- Commit tier (`ci-rule.md` §1, "Every Commit"); see the pull request.
- No case study: the net that missed it (CI on a clean checkout) cannot see local leftovers, and the remaining `iterdir()` sites were checked in the same change.
