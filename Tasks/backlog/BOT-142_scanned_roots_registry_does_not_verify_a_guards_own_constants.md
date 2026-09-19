# BOT-142 — `test_scanned_roots_are_not_empty.py` verifies a registered path exists, never that the guard it describes actually reads it

**Status:** 🔵 Backlog
**Source:** independent reviewer session on PR #246, 2026-09-19 (`BUG-131` review) — quoted: "the same class of bug (registry row correct, guard's own code wrong) can recur on any of the ~30 other registered guards with nothing to catch it." Confirmed and filed by the author session per that review's Should-fix finding; `architecture-rule.md` §7 requires deferred work to exist "as a type or a test, not only as prose."
**Risk:** 🟢 — this is hardening an existing meta-guard, not touching production behavior; a wrong implementation only risks false-positive/false-negative *test* failures, not runtime defects.
**Complexity:** M — real AST work across ~30 guard files, some of which build their scan root in shapes this task explicitly does not need to solve in one pass (see §3).
**Epic (optional):** None — standalone hardening, not part of `EPIC-025`.
**SPEC (optional):** None.
**Depends on:** None.

---

## 1. Context and problem

`BUG-131` (`Tasks/bug_report/completed/BUG-131_indicator_script_convention_guard_scans_a_deleted_directory.md`) found that `tests/unit/support/indicators/test_indicator_script_conventions.py`'s own `_SCRIPTS_DIR`/`_DOMAIN_DIR` constants pointed at a directory `EPIC-025` PR 1.6g deleted on 2026-09-16, while `tests/unit/architecture/scanned_roots_registry.py`'s registered row for that exact guard *already held the correct path* the whole time. `tests/unit/architecture/test_scanned_roots_are_not_empty.py::test_scanned_root_exists_and_is_not_empty` only asserts that a **registered** root exists and is non-empty — it never asserts that the guard file's own source actually constructs and scans that path. So the meta-guard built specifically to catch "a path-scanning guard whose target silently moved or was deleted" (HLD §9.3 rule 4) had a real blind spot: a registry row can be correct while the guard it describes checks something else, or nothing, and the meta-guard has no way to notice — which is exactly how `BUG-131` survived three days undetected by a net built for precisely this failure mode.

## 2. Acceptance criteria

- [ ] For at least the common case — a guard building its scan root from a literal `Path` expression joined with `/` and string constants (e.g. `_BOT_ROOT / "src" / "support" / "indicators" / "indicator_scripts"`), the shape used by most of the ~30 guards in `scanned_roots_registry.py` — a new check parses the guard file's AST, reconstructs the literal path each `.glob`/`.rglob`/`.iterdir` call's root variable resolves to, and fails when that reconstructed path does not match any row registered for that guard in `GUARDS`.
- [ ] The check also fails when a registered row is not reachable from anything the guard's AST actually scans (the inverse direction — a stale row nothing constructs), symmetrically with the first bullet.
- [ ] Guard shapes this task does not attempt to cover (e.g. `test_module_domain_is_qt_free.py`'s `_QT_FREE_GLOBS` tuple of glob strings joined at a shared `_SRC_ROOT`) are named explicitly in the new check's own docstring, along with why, following this repo's `Retire when:` / scope-honesty convention (`.claude/rules/testing-rule.md`) — the check must not silently skip a guard shape and call that success.
- [ ] The new check is itself registered wherever `tests/unit/architecture/test_scanned_roots_are_not_empty.py`'s own conventions require (avoid becoming a second instance of the reflexive trap this task is about).
- [ ] Re-running `BUG-131`'s original defect (manually reverting `test_indicator_script_conventions.py`'s `_SCRIPTS_DIR`/`_DOMAIN_DIR` to the deleted `src/domain/indicator_scripts` path while leaving the registry's row correct) makes the new check fail, proving it closes this exact blind spot.

## 3. Design

Not yet designed in detail — left to whoever picks this up, per `ONBOARDING.md` §7 (routine technical choices are the executing session's to make). The shape sketched in `BUG-131`'s own "Fix" section and the reviewer's finding: parse each registered guard file with `ast`, find the assignment(s) feeding its `.glob`/`.rglob`/`.iterdir` call(s), reconstruct the literal path from the `/`-joined string constants, and compare it against `GUARDS`' registered row(s) for that guard.

Explicitly out of this task's first-pass scope: guards whose scan root is not a single literal `Path` expression (e.g. built from a tuple of glob patterns joined at a shared root variable, or computed conditionally). Document which guards are covered and which are not; do not invent a fully general path-expression evaluator to force 100% coverage in one pass.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `tests/unit/architecture/test_scanned_roots_are_not_empty.py` or a new sibling file | Add the registered-root-vs-guard-source check described above. |
| `tests/unit/architecture/scanned_roots_registry.py` | No structural change expected — the existing `GUARDS` data is what the new check reads against each guard's own AST. |

## 5. Testing

Map to acceptance criteria above. The regression case is `BUG-131` itself: temporarily reintroduce its exact defect (stale constants, correct registry row) and confirm the new check fails naming that guard; restore and confirm it passes. Full architecture-tier run (`pytest tests/unit/architecture -q`) must stay green against the current (correct) state of every registered guard — a false positive here would fail CI for ~30 unrelated files.

## Implementation notes (written when done)
{Written when done.}

## Resume (optional; while unfinished)
{Not started.}
