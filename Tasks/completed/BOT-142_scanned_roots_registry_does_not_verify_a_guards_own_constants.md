# BOT-142 — `test_scanned_roots_are_not_empty.py` verifies a registered path exists, never that the guard it describes actually reads it

**Status:** ✅ Done (2026-09-22)
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

- [x] For at least the common case — a guard building its scan root from a literal `Path` expression joined with `/` and string constants (e.g. `_BOT_ROOT / "src" / "support" / "indicators" / "indicator_scripts"`), the shape used by most of the ~30 guards in `scanned_roots_registry.py` — a new check parses the guard file's AST, reconstructs the literal path each `.glob`/`.rglob`/`.iterdir` call's root variable resolves to, and fails when that reconstructed path does not match any row registered for that guard in `GUARDS`. — implemented; measured against all 41 registered guards, 22 resolve and are checked for real (root containment, not exact-pattern equality — see Design).
- [x] The check also fails when a registered row is not reachable from anything the guard's AST actually scans (the inverse direction — a stale row nothing constructs), symmetrically with the first bullet. — `test_every_resolvable_guard_scans_its_registered_root` checks both directions in one pass.
- [x] Guard shapes this task does not attempt to cover (e.g. `test_module_domain_is_qt_free.py`'s `_QT_FREE_GLOBS` tuple of glob strings joined at a shared `_SRC_ROOT`) are named explicitly in the new check's own docstring, along with why, following this repo's `Retire when:` / scope-honesty convention (`.claude/rules/testing-rule.md`) — the check must not silently skip a guard shape and call that success. — 19 guards named individually in `_UNRESOLVABLE_GUARDS`, grouped into 6 measured shape categories in the module docstring; `test_every_guard_is_either_resolved_or_documented` fails loudly if a 20th guard falls through undocumented.
- [x] The new check is itself registered wherever `tests/unit/architecture/test_scanned_roots_are_not_empty.py`'s own conventions require (avoid becoming a second instance of the reflexive trap this task is about). — registered in `GUARDS` next to `test_scanned_roots_are_not_empty.py`'s own row (same shape: it reads `tests/` files, not a glob call of its own).
- [x] Re-running `BUG-131`'s original defect (manually reverting `test_indicator_script_conventions.py`'s `_SCRIPTS_DIR`/`_DOMAIN_DIR` to the deleted `src/domain/indicator_scripts` path while leaving the registry's row correct) makes the new check fail, proving it closes this exact blind spot. — verified live on the real file (reverted, confirmed red naming the guard on both sides, restored, confirmed green); also locked permanently as `test_the_check_can_actually_fail`, a synthetic reproduction that needs no real file mutation to keep proving the mechanism works.

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

**Design decision: root containment, not exact (root, pattern) equality.**
Measured before deciding: an exact-match design flagged 4 false positives on
guards that are actually fine — `test_application_layer_structure.py` scans
`src/modules` with pattern `application/**/*.py` while its row says `*.py`
(same root, a more specific but overlapping pattern); `test_claude_tree_is_
wired.py`, `test_task_board_is_consistent.py`, `test_contract_file_naming.py`
have the same shape. A 5th case, `test_trading_view_contract.py`, resolves to
a genuine *subdirectory* of its registered root (`.../trading/coordinators`
under `.../trading`) because that file also checks two named files directly
via `Path` construction, not a glob — the row is still literally true. None
of these are `BUG-131`'s shape (a tree that no longer exists at all,
unrelated to the registered one). The check therefore compares by directory
containment (registered root confirmed if *something* the guard scans is at
or under it; a resolved scan explained if it falls under *some* registered
row) and ignores the pattern string entirely — documented with the measured
examples in the new file's own docstring, not asserted from theory.

**Scope, measured rather than assumed.** The AST resolver handles: a literal
`/`-chain from a `parents[N]` hop or a same-file landmark function
(`_repo_root()`/`_bot_root()`); simple aliasing (`_DOMAIN_DIR =
_SCRIPTS_DIR`); a tuple of such chains iterated in a `for`/comprehension. Run
against the real tree, this resolves 22 of 41 registered guards; the other 19
fall into 6 named shapes (imported root table, root behind a function
parameter, bare-string tuple joined at the call site, pattern-not-root is the
variable, runtime-discovered subdirectory, no glob/rglob/iterdir call at
all) — each guard named individually in `_UNRESOLVABLE_GUARDS` with its real
reason, not a generic "too complex". `test_every_guard_is_either_resolved_or_
documented` fails if a registered guard resolves to nothing and isn't in that
map, so a 20th unresolvable shape can't slip in silently, and
`test_every_unresolvable_guard_is_a_real_registered_guard` catches a stale
entry the same way `EMPTY_BY_DESIGN`'s own completeness check does.

One row needed a targeted, named exception rather than a whole-guard skip:
`test_credentials_never_reach_a_git_tracked_file.py`'s `src/config` row is
proven by reading `user_config.json` directly (`.read_text()`), never by a
glob — its `src` row (from a real `.rglob("*.py")` call) is still checked for
real. `_ROW_EXCEPTIONS` (mirroring `EMPTY_BY_DESIGN`'s shape) names exactly
that one row, with its own completeness guard.

**Verification.** `pytest tests/unit/architecture -q` — 432 passed (was 431
before this file; +1 test file, and the registry gained one row for it).
`ruff check`/`ruff format --check` clean. Mutation-verified live on the real
file: reverted `test_indicator_script_conventions.py`'s `_SCRIPTS_DIR` to the
exact deleted path `BUG-131` had, ran the new check — failed, naming the
guard from both directions (`scans [...] not under any registered row` +
`registered root [...] nothing scans falls under it`); restored, confirmed
green. `test_the_check_can_actually_fail` locks the same proof permanently
via a synthetic `ast.parse()` string, so the mechanism stays provably able to
fail without needing to mutate a real file again. Full `tests/unit -q` run in
progress at time of writing.
