# EPIC-037A — A capability catalog the AI receives when it touches UI or application code

**Status:** 🔵 Planned — not started
**Source:** the owner's systems-thinking review, 2026-10-09 (see the epic README for the quote)
**Risk:** 🟢 — documentation and one generator script; a stale catalog is the main risk
**Complexity:** S — one rule file, one script, one guard
**Epic:** [EPIC-037](../README.md)
**Depends on:** None

---

## 1. Context and problem
Class A ("did not reuse; diverging siblings") is 18 of 192 bug reports, and it grew from 4 to 13+ between the first 103 reports and the next 89 (analysis §2). BUG-155 is the owner's example: the New bot dialog used a free-text symbol field although `src/support/ui_kit/symbol_picker/` (`SymbolPickerOverlay`, `ISymbolPickerSource`) existed; BUG-165 hand-built twelve empty-state labels although `EmptyStateStack` existed. Nothing tells a session what shared mechanisms exist at the moment it decides; the HLD exists but is not delivered then. Verify the cited paths when the task starts.

## 2. Acceptance criteria
- [x] `.claude/rules/capabilities.md` exists with `paths:` front matter covering `src/modules/**/ui/**` and `src/modules/**/application/**` (plus `src/shell` and `src/presentation/ui`), so it loads only when a session touches those files; it lists each shared mechanism as *need → use → where → one current user*. Evidence: the file; `test_claude_tree_is_wired.py` (every glob matches a tracked file) green.
- [x] Most rows are generated (all 31 are; the hand-written part holds one pointer to Engine widgets): `scripts/render_capability_index.py` reads a `Capability:` line from module docstrings under `src/support/**` and `src/core/**` and renders the table; a hand-written section may add rows the generator cannot see.
- [x] A guard fails when a package under `src/support/` has no catalog row, or when a catalog path does not exist. Evidence: mutations M2, M7, M9 (units) and `test_every_path_the_catalog_names_exists` (paths), §5.
- [x] `.claude/templates/task.md` gains a required **Reuse** section ("checked X, Y; used Y because…"), and the pr-review rubric checks it.
- [x] The always-loaded line count (`measure_process.py`) does not rise: 285 before, 285 after.

## 3. Design
Leverage point 6 (information flow), delivered just in time (Anthropic, context engineering, 2025) instead of preloaded. Reuse the existing path-scoped rule loading and the reference checker (`scripts/check_skill_prompt_references.py`) rather than inventing a loader. Generating rows from docstrings keeps the catalog next to the code it describes.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `.claude/rules/capabilities.md` | new, path-scoped catalog |
| `scripts/render_capability_index.py` | new generator |
| `src/support/**`, `src/core/**` module docstrings | add `Capability:` lines |
| `tests/unit/architecture/test_every_support_package_is_in_the_catalog.py` | new completeness guard |
| `.claude/templates/task.md`, `.claude/skills/pr-review/references/rubric.md` | Reuse section and its check |
| `CLAUDE.md` navigation table, `.claude/README.md` | rows for the new rule (`test_rule_navigation_is_complete.py`) |

## 5. Testing
Guard file: `tests/unit/architecture/test_every_support_package_is_in_the_catalog.py` (unit tier, stdlib, 22 tests: 10 guards, 12 probes of the parser and the AST helpers). Registered in `scanned_roots_registry.py`.

**Mutation proofs** (each applied to the committed tree, run, restored, run green again; baseline 22 passed):
| # | Mutation | Red test |
| :-- | :--- | :--- |
| M1 | remove the `Deferred` marker | generated block differs; row floor |
| M2 | remove the `symbol_picker` marker (skeleton) | support unit missing; generated block differs |
| M3 | `User:` names a file that does not import the symbol | user really imports |
| M4 | `Use:` names a symbol the module lacks (`Deferrd`) | symbol defined where marked; user imports |
| M5 | hand edit of the generated table | generated block differs |
| M6 | stale baseline entry (skeleton) | baseline stale |
| M7 | drop a baseline line, so a unit is uncatalogued (skeleton) | support unit missing |
| M8 | misspelled head `Capabilty:` | marker well formed (near-miss) |
| M9 | remove the `services` marker (after the baseline was deleted) | support unit missing |
| M10 | `User:` repointed to a file that imports nothing from it | user really imports |

Other: `python3 scripts/check_skill_prompt_references.py` OK (7 checks, 44 documents); `test_claude_tree_is_wired.py`, `test_rule_navigation_is_complete.py`, `test_scanned_roots_are_not_empty.py` green; `ruff check`, `ruff format --check` clean on touched paths; `mypy scripts/render_capability_index.py` clean.

**Not run, and why.** The gate (`ci-local.ps1`) — no `pwsh` and no Engine in this container; the `-Full` run on the PR's head is the authority. The other guards in `tests/unit/architecture` that import Qt did not collect here (identical collection errors before and after this change); `test_ruff_debt_only_shrinks.py` fails identically on the untouched base in this container. The manual check (open a UI file in a fresh session and see the rule listed as loaded) — not run: it needs a second interactive session.

## Implementation notes (written when done)
- **Delivered as a walking skeleton.** Commit `1c48325` design and research; `7f8dffe` skeleton (every part, three entries); `374bbd3` fill (28 more, baseline 16 → 0, deleted, guard is a ban).
- **Marker:** a `Capability:` block in the docstring of the providing module, read with `ast`; five fields (`Also`, `Use`, `User`, `Status`; `Capability:` carries the need). Example: `src/support/ui_kit/symbol_picker/__init__.py`. **Row:** need (+ synonyms) → use → where (derived from the file path) → one current user. 31 rows: 18 support units (all of them), `INotifier`, `Deferred`, `data_root`, and the shared UI helpers a session most often rebuilds.
- **Corrected a cited path:** `EmptyStateStack` is an Engine class. The Elite mechanism is `empty_page` (carries `EmptyStateStack` among its synonyms) and `SpecTable`.
- **Term:** "capability" kept and defined in `Docs/VOCABULARY/README.md` against the Engine-API sense (design §3.1).
- **Always-loaded text did not rise** (285): the rule is path-scoped and its navigation entries were added to existing rows of `CLAUDE.md` and `ONBOARDING.md` §1.
- **Reuse section** is `## 3a` in the task template; rubric check **A7** (total now 109) in `rubric.md`, `SKILL.md`, `reviewer.md` and `ONBOARDING.md` §7.
- **Limits.** Core is judged, not enumerated: three markers there, protected by the generated-block comparison and the row floor, not by a per-file rule. Which modules deserve a row inside the flat `ui_kit` is judgement; the guard guarantees every package has one, not that every reusable module does. A session that never opens a UI or application file never receives the rule (by design).
- **Follow-up for `EPIC-037C`:** the "only one" guards can read this catalog for the canonical symbol of each mechanism.
